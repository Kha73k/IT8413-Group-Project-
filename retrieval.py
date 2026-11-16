"""F5 retrieval: split the documents into citable passages and rank them with BM25.

Two chunking configurations (compared in evaluation/retrieval_eval.py):
  structure - one passage per law/regulation article, per Procedures Guide section (titles
              taken from the guide's own contents page), and the Sijilat page as one passage.
              Citations then read like "T1-A27" = Law No. 27/2015, Article 27.
  window    - fixed windows of WINDOW words, overlapping by OVERLAP words, per document.

BM25 needs no API calls, so retrieval costs nothing against the free-tier quota and
always returns the same passages for the same question (reproducible results).
"""
import csv
import logging
import math
import re
import zipfile
from collections import Counter
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree

import pypdf

ROOT = Path(__file__).resolve().parent
WINDOW, OVERLAP = 120, 40

# Repeated page furniture that is not document content.
NOISE = re.compile(r"^(moic\.gov\.bh|Registration Directorate|\d{1,2}|\d\d/\d\d/\d{4}, \d\d:\d\d.*|https?://\S+)$")
ARTICLE = re.compile(r"^Article \((\d+(?: bis| ter)?)\)$")
WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
STOP = set("a an and are as at be by can for from has have how i if in is it its of on or shall that the their "
           "then there these this to was what when which who will with within do does my me we our you your".split())


def documents():
    """Document collection from sources/SOURCES.csv (the single register of sources)."""
    with open(ROOT / "sources" / "SOURCES.csv", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["kind"] == "document"]


def _clean(lines):
    lines = [" ".join(line.split()) for line in lines]
    return [line for line in lines if line and not NOISE.match(line)]


def _docx_paragraphs(path):
    """A .docx is a zip of XML, so the standard library can read its paragraphs."""
    with zipfile.ZipFile(path) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    parts = (f"{WORD}t", f"{WORD}tab")
    return ["".join(" " if n.tag == f"{WORD}tab" else n.text or "" for n in p.iter() if n.tag in parts)
            for p in root.iter(f"{WORD}p")]


@lru_cache(maxsize=None)
def pages(local_file):
    """[(page number, lines)]. A Word file has no fixed pages, so its page number is None."""
    path = ROOT / "sources" / local_file
    if not path.exists():
        raise FileNotFoundError(f"{path.name} is missing from sources/documents/. Download it from the page linked in "
                                "sources/SOURCES.csv (see README, step 2).")
    if path.suffix == ".docx":
        return [(None, _clean(_docx_paragraphs(path)))]
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    return [(n, _clean((page.extract_text() or "").splitlines())) for n, page in enumerate(pypdf.PdfReader(path).pages, 1)]


def tokens(text):
    out = []
    for t in re.findall(r"[a-z0-9]+", text.lower().replace("licence", "license").replace("practise", "practice")):
        if t in STOP:
            continue
        if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]  # licenses -> license, restaurants -> restaurant
        out.append(t)
    return out


def _passage(doc, pid, title, page, lines):
    return {"id": pid, "doc": doc["id"], "document": doc["title"], "title": title, "page": page,
            "url": doc["url"], "text": " ".join(lines)}


def _structure(doc):
    flat = [(n, line) for n, ls in pages(doc["local_file"]) for line in ls]
    if doc["id"] in ("T1", "T2"):
        # Law and regulation: a heading line "Article (n)" starts each article.
        starts = [(i, "A" + ARTICLE.match(l).group(1).replace(" ", "")) for i, (_, l) in enumerate(flat) if ARTICLE.match(l)]
        starts = [(0, "A0")] + starts  # preamble before Article (1)
        titles = {"A0": "Preamble"}
    elif doc["id"] == "T3":
        # Guide: section titles come from its contents page ("Title ........ 5").
        key = lambda text: re.sub(r"\W", "", text).lower()
        toc = {key(l.split("..")[0]) for n, l in flat if n <= 3 and ".." in l}
        starts, titles, skip = [(0, "S00")], {"S00": "Title page and contents"}, -1
        for i, (n, l) in enumerate(flat):
            if n <= 3 or i == skip:
                continue
            two = l + " " + flat[i + 1][1] if i + 1 < len(flat) else ""   # titles that wrap onto 2 lines
            for title in (l, two):
                if title and key(title) in toc:
                    sid = f"S{len(starts):02d}"
                    starts.append((i, sid))
                    titles[sid] = title
                    skip = i + 1 if title is two else -1
                    break
    else:
        return [_passage(doc, f"{doc['id']}-P", "Whole document", flat[0][0], [l for _, l in flat])]
    out, carry = [], []
    for (i, key), (j, _) in zip(starts, starts[1:] + [(len(flat), None)]):
        chunk = carry + flat[i:j]
        if len(" ".join(l for _, l in chunk).split()) < 8:   # heading with no body ("Legal Rules")
            carry, carried = chunk, titles.get(key, "")
            continue
        if key.startswith("A") and key != "A0":
            # The heading comes first. In a PDF it can wrap; the body starts with a full-width line.
            head = [chunk[1][1]]
            for _, line in chunk[2:4]:
                if len(line) >= 70 or line.endswith((".", ":")):
                    break
                head.append(line)
            title = f"Article {key[1:]}: {' '.join(head)}"
        else:
            title = titles[key]
        if carry:
            title, carry = f"{carried}: {title}", []
        out.append(_passage(doc, f"{doc['id']}-{key}", title, chunk[0][0], [l for _, l in chunk]))
    return out


def _window(doc):
    words = [(n, w) for n, ls in pages(doc["local_file"]) for line in ls for w in line.split()]
    out, step = [], WINDOW - OVERLAP
    for k, start in enumerate(range(0, max(len(words) - OVERLAP, 1), step)):
        chunk = words[start:start + WINDOW]
        out.append(_passage(doc, f"{doc['id']}-W{k:02d}", f"Words {start + 1}-{start + len(chunk)}",
                            chunk[0][0], [w for _, w in chunk]))
    return out


@lru_cache(maxsize=None)
def index(chunking):
    split = {"structure": _structure, "window": _window}[chunking]
    passages = [p for doc in documents() for p in split(doc)]
    docs = [Counter(tokens(p["title"] + " " + p["text"])) for p in passages]
    df = Counter(t for d in docs for t in d)
    avg = sum(sum(d.values()) for d in docs) / len(docs)
    return passages, docs, df, avg


def search(query, k=4, chunking="structure"):
    """Top-k passages by BM25 (k1=1.5, b=0.75). Each result carries its score."""
    passages, docs, df, avg = index(chunking)
    n, q = len(passages), tokens(query)
    scored = []
    for p, d in zip(passages, docs):
        length = sum(d.values())
        s = sum(math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) * d[t] * 2.5 / (d[t] + 1.5 * (0.25 + 0.75 * length / avg))
                for t in q if t in d)
        if s > 0:
            scored.append((s, p))
    scored.sort(key=lambda x: -x[0])
    return [dict(p, score=round(s, 2)) for s, p in scored[:k]]


def passage(pid, chunking="structure"):
    return next((p for p in index(chunking)[0] if p["id"] == pid), None)


def all_passages(chunking="structure"):
    return index(chunking)[0]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for c in ("structure", "window"):
        ps = all_passages(c)
        print(f"{c}: {len(ps)} passages", Counter(p["doc"] for p in ps))
    for p in all_passages():
        print(f"  {p['id']:9} p.{str(p['page'] or '-'):<3} {len(p['text'].split()):>4}w  {p['title'][:70]}")
    # The law must be the amended text: these figures are only in the 2018 amendment.
    assert "BD 100,000" in passage("T1-A27")["text"]
    assert "fifty thousand" in passage("T1-A20")["text"] and "six months" in passage("T1-A20")["text"]
    assert passage("T1-A18bis") and passage("T1-A18ter")
    assert "Bahrain Clear" in passage("T5-P")["text"]
    print("retrieval self-checks passed")
