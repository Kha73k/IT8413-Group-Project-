"""Question answering in the four evaluated configurations (PDF 7.2).

  control   the question exactly as asked: no system prompt, sources, retrieval or tools
  baseline  every source pasted into the prompt as text: no retrieval, no tools
  v1        the tool: data functions (F4), document retrieval (F5), combined (F6),
            refusal (F7) and follow-ups (F8), with the v1 settings from config.json
  v2        v1 plus the single change recorded in config.json

answer() is the one entry point, used by the web app and by evaluation/run_eval.py alike,
so evaluated results come from exactly the code the app runs. Every call is logged (F10).
"""
import csv
import io
import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import llm
import retrieval
import tools

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "logs" / "query_log.jsonl"
MODES = ("control", "baseline", "v1", "v2")
REFUSAL = "Not available in the sources:"
# Any passage id counts, so "[T1-A15, T2-A11]" gives two citations, not none.
CITATION = re.compile(r"\b([A-Z]\d-[A-Z]\w*)\b")

RULES = f"""Rules:
1. Rules and requirements: answer only from the document passages. After each claim put the id of the passage that
   supports it in square brackets, e.g. [T1-A27]. Only cite a passage that supports the claim.
2. If the sources do not contain the answer, start your reply with exactly "{REFUSAL}" and say what is missing.
   This includes predictions (whether a business will succeed, future demand or prices), causes and opinions,
   area statistics below governorate level, individual people, and rules that are not in the documents.
   Never fill a gap from general knowledge.
3. Population and land use are published by governorate only. Business locations are known by governorate and block.
4. Follow-up questions refer to the earlier conversation: resolve words like "that", "there" or "what about" from it.
5. Be brief and plain: the answer first, then the figures and citations that support it. No markdown tables."""

PROMPTS = {
    "v1": f"""You answer questions for advisors at a government business support centre in Bahrain. They use you during
consultations with people planning to open a small business, who want to know where similar businesses already
operate, what each governorate is like (residents, land use), and which registration and licensing rules apply.

Numbers: every number in your answer must come from a function result. Get figures with count_businesses,
get_population and get_land_use, and use calculate for every percentage, rate, difference or growth figure.
Never estimate, and never do arithmetic yourself. Documents: use search_documents, and cite the passage ids it returns.
Questions that need both: use the data functions and search_documents.

{RULES}""",
}

BASELINE = """You answer questions for advisors at a government business support centre in Bahrain, using only the
sources below: three data tables (CSV) and the registration and licensing documents (passages with ids).

{rules}

=== DATA ===
{data}

=== DOCUMENTS ===
{documents}"""

_log_lock = threading.Lock()


def config():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def settings(version):
    """Resolved settings for v1/v2; v2 is v1 plus exactly the recorded change."""
    versions = config()["versions"]
    v = versions[version]
    if "base" in v:
        return {**versions[v["base"]], **v["change"]}
    return dict(v)


def varied_setting():
    v2 = config()["versions"]["v2"]
    base = settings(v2["base"])
    return {"changed": {k: {"v1": base.get(k), "v2": val} for k, val in v2["change"].items()}, "reason": v2["reason"]}


@lru_cache(maxsize=None)
def baseline_sources():
    """Every source as plain text: all data rows (coordinates and ids omitted) and every passage."""
    d = tools.data()
    parts = []
    for name, cols in (("businesses", ["name", "category", "subtype", "block", "governorate"]),
                       ("population", ["period", "governorate", "nationality", "sex", "population"]),
                       ("land_use", ["period", "governorate", "category", "area_m2"])):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        w.writerows([r[c] if r[c] is not None else "" for c in cols] for r in d[name])
        parts.append(f"--- {name}.csv ---\n{buf.getvalue()}")
    docs = "\n\n".join(f"[{p['id']}] {p['document']}{', p.' + str(p['page']) if p['page'] else ''}, {p['title']}\n{p['text']}"
                       for p in retrieval.all_passages("structure"))
    return "\n".join(parts), docs


def _contents(history, question):
    contents = []
    for turn in history:
        contents.append({"role": "user", "parts": [{"text": turn["question"]}]})
        contents.append({"role": "model", "parts": [{"text": turn["answer"]}]})
    contents.append({"role": "user", "parts": [{"text": question}]})
    return contents


def _generation(s):
    return {"temperature": s["temperature"], "maxOutputTokens": s["max_output_tokens"],
            "thinkingConfig": {"thinkingLevel": s["thinking_level"]}}


def _text(response):
    cand = (response.get("candidates") or [{}])[0]
    parts = cand.get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip(), cand, parts


def answer(question, history=(), mode="v1", session_id=None, run=None):
    """Answer one question. history: earlier [{'question', 'answer'}] turns of the same session."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    cfg, start = config(), time.time()
    s = settings(mode) if mode in ("v1", "v2") else settings("v1")
    usage = {"prompt": 0, "output": 0, "thoughts": 0, "total": 0}
    calls, requests, retries, text, error, quota_exhausted = [], 0, 0, "", None, False
    working = 0.0  # seconds in the model and tools, without waiting for the rate limit: that is the latency metric
    contents = _contents(list(history), question)

    if mode == "control":
        payload = {"contents": contents, "generationConfig": _generation(s)}
        shown_settings = {k: s[k] for k in ("temperature", "thinking_level", "max_output_tokens")}
    elif mode == "baseline":
        data, docs = baseline_sources()
        payload = {"contents": contents, "generationConfig": _generation(s), "systemInstruction":
                   {"parts": [{"text": BASELINE.format(rules=RULES, data=data, documents=docs)}]}}
        shown_settings = {k: s[k] for k in ("prompt", "temperature", "thinking_level", "max_output_tokens")}
    else:
        payload = {"contents": contents, "generationConfig": _generation(s),
                   "systemInstruction": {"parts": [{"text": PROMPTS[s["prompt"]]}]},
                   "tools": [{"functionDeclarations": tools.declarations()}]}
        shown_settings = s

    try:
        for _ in range(s["max_model_calls"] if mode in ("v1", "v2") else 1):
            response, seconds, r = llm.generate(cfg["model"], payload, cfg["limits"])
            requests, retries, working = requests + 1, retries + r, working + seconds
            meta = response.get("usageMetadata", {})
            usage["prompt"] += meta.get("promptTokenCount", 0)
            usage["output"] += meta.get("candidatesTokenCount", 0)
            usage["thoughts"] += meta.get("thoughtsTokenCount", 0)
            usage["total"] += meta.get("totalTokenCount", 0)
            text, cand, parts = _text(response)
            fcalls = [p["functionCall"] for p in parts if "functionCall" in p]
            if not fcalls:
                if not text:
                    error = f"empty answer (finishReason={cand.get('finishReason')})"
                break
            # Send the model's turn back unchanged (it carries thought signatures), then the results.
            payload["contents"].append(cand["content"])
            results = []
            for fc in fcalls:
                tool_start = time.time()
                result = tools.call(fc["name"], fc.get("args", {}), s)
                working += time.time() - tool_start
                calls.append({"name": fc["name"], "args": fc.get("args", {}), "result": result})
                results.append({"functionResponse": {"name": fc["name"], "response": result,
                                                     **({"id": fc["id"]} if "id" in fc else {})}})
            payload["contents"].append({"role": "user", "parts": results})
        else:
            error = f"stopped after {s['max_model_calls']} model calls without a final answer"
    except llm.QuotaExhausted as e:
        error, quota_exhausted = str(e), True
    except llm.LLMError as e:
        error = str(e)

    chunking = s["chunking"] if mode in ("v1", "v2") else "structure"
    ids = list(dict.fromkeys(CITATION.findall(text)))
    citations = [p for p in (retrieval.passage(i, chunking) for i in ids) if p]
    retrieved = {p["id"] for c in calls if c["name"] == "search_documents" for p in c["result"].get("passages", [])}
    price = cfg["pricing"]
    cost = (usage["prompt"] * price["input_usd_per_million_tokens"]
            + (usage["output"] + usage["thoughts"]) * price["output_usd_per_million_tokens"]) / 1e6
    invalid = [i for i in ids if i not in {p["id"] for p in citations}]
    unsupported = unsupported_numbers(text, question, list(history), calls, citations) if mode in ("v1", "v2") else None
    record = {
        "verification": verify(mode, text, calls, citations, retrieved, invalid, unsupported),
        "id": uuid.uuid4().hex[:12], "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run": run, "session_id": session_id, "turn": len(history) + 1, "mode": mode,
        "model": cfg["model"], "settings": shown_settings, "question": question, "answer": text,
        "refused": text.startswith(REFUSAL) if mode != "control" else None,
        "citations": [{"id": p["id"], "document": p["document"], "title": p["title"], "page": p["page"],
                       "url": p["url"], "text": p["text"], "retrieved": p["id"] in retrieved} for p in citations],
        "invalid_citations": invalid, "unsupported_numbers": unsupported,
        "tool_calls": calls, "latency_s": round(working, 2), "waited_s": round(time.time() - start - working, 2), "requests": requests,
        "retries": retries, "tokens": usage, "cost_usd": round(cost, 6), "error": error,
        "quota_exhausted": quota_exhausted,
    }
    write_log(record)
    return record


def verify(mode, text, calls, citations, retrieved, invalid, unsupported):
    """Enhancement: the tool checks its own answer, in code, at no API cost. Flags, never edits.

    Evaluated by how often it catches answers people scored as ungrounded or wrong.
    """
    if mode == "control":
        return {"checked": False, "issues": []}
    issues = [f"Cites a passage that does not exist: {i}" for i in invalid]
    if mode in ("v1", "v2"):
        issues += [f"Cites {p['id']}, which the search did not return for this question"
                   for p in citations if p["id"] not in retrieved]
        issues += [f"Number not computed by a function or found in a cited passage: {n}" for n in unsupported or []]
        searched = any(c["name"] == "search_documents" for c in calls)
        if searched and text and not citations and not text.startswith(REFUSAL) and \
                not any(c["name"] != "search_documents" for c in calls):
            issues.append("Answers from the documents but cites no passage")
    return {"checked": True, "issues": issues}


NUMBER = re.compile(r"(?<![\w.])\d(?:[\d,]*\d)?(?:\.\d+)?")


_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                       "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_UNITS.update({w: 10 * i for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split(), 2)})
_SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000}


def _word_numbers(text):
    """Numbers written in words, as the law writes them: 'Twenty Thousand' -> 20000."""
    found, total, current, seen = [], 0, 0, False
    for word in re.findall(r"[a-z]+|[.,;:()]", text.lower()) + ["."]:
        if word in _UNITS:
            current, seen = current + _UNITS[word], True
        elif word in _SCALES and seen:
            if word == "hundred":
                current *= 100
            else:
                total, current = total + current * _SCALES[word], 0
        elif word != "and" or not seen:
            if seen:
                found.append(float(total + current))
            total, current, seen = 0, 0, False
    return found


def _numbers(value, out):
    """Every number inside a tool result (nested dicts/lists, numbers and numeric text)."""
    if isinstance(value, bool):
        return out
    if isinstance(value, (int, float)):
        out.add(float(value))
    elif isinstance(value, str):
        out.update(float(n.replace(",", "")) for n in NUMBER.findall(value))
        out.update(_word_numbers(value))
    elif isinstance(value, dict):
        for k, v in value.items():
            _numbers(k, out)
            _numbers(v, out)
    elif isinstance(value, list):
        for v in value:
            _numbers(v, out)
    return out


# Unit conversions a calculation may use without a source: percentages, per 10,000 residents, m2 to km2.
_CONVERSIONS = {1.0, 100.0, 1_000.0, 10_000.0, 1_000_000.0}


def _supported(raw, known):
    """A source number supports what is written if it rounds to it at the precision written (17.30 from 17.298188)."""
    value = float(raw.replace(",", ""))
    places = len(raw.split(".")[1]) if "." in raw else 0
    return any(abs(round(k, places) - value) < 1e-9 or abs(k - value) < 1e-9 for k in known)


def unsupported_numbers(text, question, history, calls, citations):
    """Numbers in the answer that no tool result, cited passage, question or earlier turn contains.

    A number also counts when it equals a source number divided by 1e6 (m2 -> km2). A calculate
    result counts only if its own inputs are supported, so a sum over invented figures is caught.
    Citation ids such as [T1-A27] are ignored. Costs no API requests.
    """
    known = _numbers([question] + [t["question"] + " " + t["answer"] for t in history] + [p["text"] for p in citations], set())
    for call in calls:
        if call["name"] != "calculate":
            _numbers(call["result"], known)
        elif all(_supported(n, known | _CONVERSIONS) for n in NUMBER.findall(str(call["args"].get("expression", "")))):
            if "result" in call["result"]:
                known.add(float(call["result"]["result"]))
    known |= {k / 1e6 for k in known}
    bad = [raw for raw in NUMBER.findall(CITATION.sub(" ", text)) if not _supported(raw, known)]
    return list(dict.fromkeys(bad))


def write_log(record):
    LOG.parent.mkdir(exist_ok=True)
    with _log_lock, open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_log(limit=200):
    if not LOG.exists():
        return []
    with open(LOG, encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(line) for line in lines[-limit:]][::-1]


def requests_today():
    """Model requests logged since midnight Pacific (when the free-tier daily quota resets)."""
    from zoneinfo import ZoneInfo
    pacific = ZoneInfo("America/Los_Angeles")
    today = datetime.now(pacific).date()
    if not LOG.exists():
        return 0
    total = 0
    with open(LOG, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if datetime.fromisoformat(r["time"]).astimezone(pacific).date() == today:
                total += r.get("requests", 0)
    return total


if __name__ == "__main__":
    count = {"name": "count_businesses", "args": {}, "result": {"count": 39}}
    total = {"name": "count_businesses", "args": {}, "result": {"count": 315}}
    calc = lambda e, r: {"name": "calculate", "args": {"expression": e}, "result": {"expression": e, "result": r}}  # noqa: E731
    assert unsupported_numbers("39 of 315, 12.38%", "", [], [count, total, calc("39 / 315 * 100", 12.380952)], []) == []
    assert unsupported_numbers("136 of 774, 17.57%", "", [], [count, total, calc("136 / 774 * 100", 17.571059)], [])         == ["136", "774", "17.57"]
    assert unsupported_numbers("39 of 315, 12.38%", "", [], [count, total], []) == ["12.38"]
    assert unsupported_numbers("2.5 km2", "", [], [{"name": "get_land_use", "args": {}, "result": {"area_m2": 2500000}}], []) == []
    assert CITATION.findall("[T1-A15, T2-A11] and [T1-W03]") == ["T1-A15", "T2-A11", "T1-W03"]
    print("pipeline self-checks passed")
