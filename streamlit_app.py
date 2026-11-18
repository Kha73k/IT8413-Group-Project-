"""Web application (Streamlit): dashboard, questions, query log and sources.

    streamlit run streamlit_app.py      ->  http://localhost:8501

The figures and answers come from the same modules as before (analytics, pipeline); this file only lays them out.
Gemini API key: GEMINI_API_KEY (environment variable or Streamlit secret), or the first line of api.txt (git-ignored).
"""
import hashlib
import html
import json
import re
import urllib.request
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

import analytics
import llm
import pipeline
import retrieval

ROOT = Path(__file__).resolve().parent
DESIGN = ROOT / "design"
MAX_QUESTION = 1000
EXAMPLES = ["Which governorate has the most coffee shops?", "What must a business display at its place of business?",
            "How much Agriculture land does the Northern governorate have?", "Will a bakery succeed in Riffa?"]
MODES = {"v1": "v1: the tool (functions + retrieval)", "v2": "v2: v1 plus the intervention",
         "baseline": "baseline: all sources in the prompt (slow)", "control": "control: the model alone"}
GROUPS = [("governorate", "Governorate"), ("category", "Business category"), ("subtype", "Business type"),
          ("land_category", "Land use"), ("nationality", "Nationality"), ("sex", "Sex")]
PANEL = {"trend": "#2563eb", "rates": "#16a34a", "land": "#d97706", "types": "#e8603c", "map": "#0d9488"}
# Documents are not in the repository (the publishers' terms do not allow republishing). When one is missing, as on a
# fresh clone or the online copy, the app fetches it from the publisher, and keeps it only if it is byte for byte the
# file the evaluation used. MOIC's site refuses downloads by programs, so T2, T3 and T4 exist only on the group's PC.
DOWNLOADS = {
    "documents/cr_law_27_2015_consolidated.docx":
        ("https://www.lloc.gov.bh/FullEn/L2715.docx", "34c971a64be7197b9cef0eaf99721058b21c4983ada55cb9340e76bd190f1a2d"),
    "documents/cr_law_amendment_9_2022.docx":
        ("https://www.lloc.gov.bh/FullEn/K0922.docx", "b1dc9b378e1c741cb8dfa6008c18c4872c3c49c7c1e31eae2a32e17dca7e0151"),
    "documents/cr_regulation_amendment_68_2018.docx":
        ("https://www.lloc.gov.bh/FullEn/RICT6818.docx", "7965f1665e2f07c556045e2d5a56fce48010c412cc90e4852ea9e84475d42cdd"),
    "documents/companies_law_amendment_28_2020.docx":
        ("https://www.lloc.gov.bh/FullEn/L2820.docx", "dc9f19eade3857faff41ec21094ff0b0d39f04ca2d376cd0fd9cf484ced5f6a3"),
}

st.set_page_config(page_title="Business Location Advisor", page_icon=":material/storefront:", layout="wide")


# ---- data ---------------------------------------------------------------------------------------------------

@st.cache_resource(show_spinner="Fetching the legal documents from their publishers")
def prepare_documents():
    """Fetch missing documents once per server. Returns the documents still missing."""
    for name, (url, digest) in DOWNLOADS.items():
        path = ROOT / "sources" / name
        if path.exists():
            continue
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                body = r.read(20_000_000)
        except OSError:
            continue
        if hashlib.sha256(body).hexdigest() == digest:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
    missing = [d for d in retrieval.documents() if not (ROOT / "sources" / d["local_file"]).exists()]
    retrieval.ALLOW_MISSING = bool(missing)
    return missing


@st.cache_data(show_spinner=False)
def options():
    return analytics.options()


@st.cache_data(show_spinner=False, max_entries=500)
def dashboard(filters_json):
    return analytics.dashboard(json.loads(filters_json))


def key_configured():
    try:
        llm.api_key()
        return True
    except llm.LLMError:
        return False


# ---- small helpers ------------------------------------------------------------------------------------------

e = html.escape
fmt = lambda n: "n/a" if n is None else f"{n:,}"  # noqa: E731


def literal(text):
    """Model output and document text shown as plain text: Markdown characters are escaped, line breaks kept."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>~<$])", r"\\\1", text or "").replace("\n", "  \n")


def card(name, title, subtitle):
    box = st.container(border=True, key=f"card_{name}")
    colour = PANEL.get(name, "#111827")
    box.html(f'<div class="g1-title" style="--card-c:{colour}"><h3>{e(title)}</h3>'
             + (f'<p>{e(subtitle)}</p>' if subtitle else '') + '</div>')
    return box


def chart_base(**extra):
    return {"animationDuration": 900, "animationEasing": "cubicOut",
            "textStyle": {"fontFamily": "Inter, system-ui, sans-serif"},
            "tooltip": {"backgroundColor": "#111827", "borderWidth": 0, "textStyle": {"color": "#fff", "fontSize": 12}},
            "grid": {"left": 8, "right": 28, "top": 16, "bottom": 8, "containLabel": True}, **extra}


def hbar(rows, label, value, colours, unit):
    """Horizontal bars, largest first, with the value written at the end of each bar. The rows go in as a table, so
    the chart's toolbar can show them (Show data)."""
    # Room for the labels is set from their length: ECharts measures them before the web font has loaded.
    room = min(150, max(80, 20 + 6.2 * max(len(str(r[label])) for r in rows)))
    return chart_base(
        dataset={"source": pd.DataFrame(rows)[[label, value]]},
        tooltip={**chart_base()["tooltip"], "valueFormatter": f"%,g{unit}"},
        grid={"left": room, "right": 48, "top": 8, "bottom": 24},
        xAxis={"type": "value", "splitLine": {"lineStyle": {"color": "#eef1f5"}}},
        yAxis={"type": "category", "inverse": True, "axisTick": {"show": False}, "axisLine": {"show": False},
               "axisLabel": {"width": room - 12, "overflow": "truncate", "interval": 0}},
        # One colour per bar, in row order: the governorate bars keep their governorate colours.
        series=[{"type": "bar", "encode": {"x": value, "y": label}, "colorBy": "data", "color": colours, "barMaxWidth": 14,
                 "itemStyle": {"borderRadius": [0, 3, 3, 0]},
                 "label": {"show": True, "position": "right", "formatter": f"{{@{value}}}", "color": "#374151", "fontSize": 11}}])


# ---- page ---------------------------------------------------------------------------------------------------

missing_docs = prepare_documents()
OPTS = options()
COLOURS = OPTS["gov_colours"]
YEARS = OPTS["years"]

st.html(DESIGN / "app.css")
if "seen_intro" not in st.session_state:
    st.session_state.seen_intro = True
    st.html(DESIGN / "curtain.html", unsafe_allow_javascript=True)
st.session_state.setdefault("turns", [])
st.session_state.setdefault("session_id", uuid.uuid4().hex)


def clear_filters():
    # Without their keys the widgets start again from their defaults: nothing chosen, every year.
    for key in [f"f_{k}" for k, _ in GROUPS] + ["f_years"]:
        st.session_state.pop(key, None)


# ---- sidebar: filters ------------------------------------------------------------------------------------------

with st.sidebar:
    st.html('<div class="g1-brand"><b>Business Location Advisor</b><small>Bahrain, IT8413 Group G1</small></div>')
    for key, label in GROUPS:
        values = OPTS[key]
        if key == "subtype" and st.session_state.get("f_category"):
            values = sorted(v for c in st.session_state.f_category for v in OPTS["subtypes_by_category"][c])
            # A business type outside the chosen categories is dropped, as on the old page.
            st.session_state.f_subtype = [v for v in st.session_state.get("f_subtype", []) if v in values]
        st.pills(label, values, selection_mode="multi", key=f"f_{key}")
        if key == "governorate":
            years = st.select_slider("Years", YEARS, value=(YEARS[0], YEARS[-1]), key="f_years")
    st.button("Clear filters", on_click=clear_filters, width="stretch", icon=":material/filter_alt_off:")

filters = {key: st.session_state.get(f"f_{key}") or [] for key, _ in GROUPS}
filters["from_year"], filters["to_year"] = years
d = dashboard(json.dumps(filters, sort_keys=True))
totals = dashboard(json.dumps({}))["kpis"]
turns = st.session_state.turns

with st.sidebar:
    st.download_button("Download area profile", data=lambda: analytics.report_html(filters, turns),
                       file_name="area_profile.html", mime="text/html", type="primary", on_click="ignore",
                       width="stretch", icon=":material/download:",
                       help="Figures, charts and cited passages for the current selection, as one HTML file.")

# ---- banner ---------------------------------------------------------------------------------------------------

cfg = pipeline.config()
n_docs = len(retrieval.documents())   # only the documents this copy has
st.html(f"""<header class="g1-banner">
  <div><p class="crumbs">Bahrain &rsaquo; IT8413 Group 1</p><h1>Business Location Advisor</h1></div>
  <div class="meta"><span class="g1-pill"><i class="dot"></i>4 datasets &middot; {n_docs} documents</span>
    <span class="g1-pill mono">{e(cfg['model'])}</span></div>
</header>""")

# A key keeps the open tab across reruns, so asking a question does not jump back to the dashboard.
tab_dash, tab_ask, tab_log, tab_src = st.tabs(["Dashboard", "Ask", "Query log", "Sources"], key="tab", on_change="rerun")

# ---- dashboard ------------------------------------------------------------------------------------------------

def kpi_cards(d):
    k, f = d["kpis"], d["filters"]
    said = lambda key, every: ", ".join(f[key]) or every  # noqa: E731
    people = ", ".join(filter(None, [said("nationality", ""), said("sex", "")]))
    biz = ", ".join(f["subtype"]) or said("category", "all businesses")
    cards = [("Businesses in selection", k["businesses"], "", biz, k["businesses"] / totals["businesses"]),
             ("Residents", k["residents"] or None, "", (people or "all residents") + (f", {k['residents_period']}" if k["residents_period"] else ""),
              (k["residents"] or 0) / totals["residents"]),
             ("Businesses per 10,000 residents", k["per_10k"], "", said("governorate", "all governorates"), None),
             ("Land", k["land_km2"], "km²", said("land_category", "all uses") + (f", {k['land_period']}" if k["land_period"] else ", none in these years"),
              (k["land_km2"] or 0) / totals["land_km2"])]
    out = []
    for i, (label, value, unit, note, share) in enumerate(cards):
        if i == 2:   # businesses per 10,000 residents: one small bar per governorate
            rates = [x for x in d["rates"] if x["per_10k"] is not None]
            top = max([x["per_10k"] for x in rates] + [1])
            viz = '<div class="bars">' + "".join(
                f'<i style="height:{max(8, 40 * x["per_10k"] / top):.0f}px;background:{COLOURS[x["governorate"]]}" '
                f'title="{e(x["governorate"])}: {x["per_10k"]} per 10,000"></i>' for x in rates) + "</div><em>by governorate</em>"
        else:
            s = min(share or 0, 1)
            viz = (f'<div class="ring" style="--s:{s * 100:.1f}" title="{s:.0%} of the whole data set">'
                   f'<i class="ico ico-{i}"></i></div><em>{s:.0%} of all</em>')
        shown = "n/a" if value is None else f"{value:,}"
        out.append(f'<div class="kpi k{i}"><span>{e(label)}</span><b><span class="num">{shown}</span>'
                   f'<span class="unit">{e(unit) if value is not None else ""}</span></b><small title="{e(note)}">{e(note)}</small><div class="kpi-viz">{viz}</div></div>')
    return '<div class="g1-kpis">' + "".join(out) + "</div>"


with tab_dash:
    k, f = d["kpis"], d["filters"]
    said = lambda key, every: ", ".join(f[key]) or every  # noqa: E731
    govs = said("governorate", "all governorates")
    people = ", ".join(filter(None, [said("nationality", ""), said("sex", "")]))
    biz = ", ".join(f["subtype"]) or said("category", "all businesses")
    st.html('<p class="g1-notice">Business locations go down to block level. Residents and land use are published '
            '<b>by governorate only</b>. Use this to compare governorates and see where similar businesses are registered. '
            'It cannot say whether a new business will succeed.</p>')
    st.html(kpi_cards(d))

    with card("trend", "Residents over time", f"{govs}{', ' + people if people else ''}, {f['from_year']} to {f['to_year']}. "
              "Starts at 2012-06: earlier years used different governorates."):
        series = d["trend"]["series"]
        if series:
            df = pd.DataFrame({"period": d["trend"]["periods"], **{s["governorate"]: s["values"] for s in series}})
            st.echarts_chart(chart_base(
                dataset={"source": df}, legend={"top": 0, "left": 0, "icon": "circle", "itemWidth": 8, "itemHeight": 8},
                tooltip={**chart_base()["tooltip"], "trigger": "axis", "valueFormatter": "localized"},
                grid={"left": 8, "right": 84, "top": 36, "bottom": 8, "containLabel": True},
                xAxis={"type": "category", "boundaryGap": False},
                yAxis={"type": "value", "splitLine": {"lineStyle": {"color": "#eef1f5"}}},
                series=[{"type": "line", "name": s["governorate"], "encode": {"x": "period", "y": s["governorate"]},
                         "smooth": 0.35, "showSymbol": False, "lineStyle": {"width": 2.5, "color": COLOURS[s["governorate"]]},
                         "itemStyle": {"color": COLOURS[s["governorate"]]}, "emphasis": {"focus": "series"},
                         "endLabel": {"show": True, "formatter": "{a}", "color": "#374151", "fontSize": 11},
                         "labelLayout": {"moveOverlap": "shiftY"}} for s in series]),
                height=300, key="chart_trend", alt=f"Residents over time for {govs}")
        else:
            st.caption("No data for this selection.")

    left, right = st.columns(2)
    with left, card("rates", "Businesses per 10,000 residents", f"{biz}, against {people or 'all residents'} "
                    f"({k['residents_period'] or 'no period'})."):
        rates = [r for r in d["rates"] if r["per_10k"] is not None]
        if rates:
            st.echarts_chart(hbar(rates, "governorate", "per_10k", [COLOURS[r["governorate"]] for r in rates], " per 10,000"),
                             height=270, key="chart_rates", alt="Businesses per 10,000 residents by governorate")
        else:
            st.caption("No data for this selection.")
    with right, card("land", "Land use", f"{govs}, {said('land_category', 'all uses')}, "
                     + (f"{d['land']['period']} (one monthly snapshot)." if d["land"]["period"] else "no snapshot in these years.")
                     + (f" Missing from source: {'; '.join(d['land']['missing'])}." if d["land"]["missing"] else "")):
        land = d["land"]["rows"]
        if land:
            st.echarts_chart(hbar(land, "category", "km2", ["#d97706"] * len(land), " km²"),
                             height=270, key="chart_land", alt="Land area by use category, in square kilometres")
        else:
            st.caption("No data for this selection.")

    left, right = st.columns(2)
    with left, card("types", "Business types", f"{govs}, {biz}. Registration snapshot: some may have closed."):
        types = list(d["types"]["rows"])
        if d["types"]["other"]:
            types.append({"subtype": f"{d['types']['other_types']} other types", "count": d["types"]["other"]})
        if types:
            st.echarts_chart(hbar(types, "subtype", "count", ["#e8603c"] * len(types), " businesses"),
                             height=380, key="chart_types", alt="Number of businesses by type")
        else:
            st.caption("No data for this selection.")
    with right, card("map", "Where these businesses are", f"{govs}, {biz}. Busiest blocks: "
                     + (", ".join(f"{b['block']} ({b['count']})" for b in d["blocks"][:3]) or "none") + "."):
        if d["points"]:
            pts = pd.DataFrame(d["points"])[["lon", "lat", "name", "subtype", "block", "governorate"]]
            present = [g for g in COLOURS if g in set(pts["governorate"])]
            st.echarts_chart(chart_base(
                dataset=[{"source": pts}] + [{"transform": {"type": "filter", "config": {"dimension": "governorate", "=": g}}}
                                             for g in present],
                legend={"top": 0, "left": 0, "icon": "circle", "itemWidth": 8, "itemHeight": 8},
                grid={"left": 64, "right": 16, "top": 36, "bottom": 44},
                xAxis={"type": "value", "min": 50.43, "max": 50.70, "name": "Longitude", "nameLocation": "middle", "nameGap": 28,
                       "splitLine": {"lineStyle": {"color": "#eef1f5"}}},
                yAxis={"type": "value", "min": 25.80, "max": 26.33, "name": "Latitude", "nameLocation": "middle", "nameGap": 46,
                       "splitLine": {"lineStyle": {"color": "#eef1f5"}}},
                series=[{"type": "scatter", "name": g, "datasetIndex": i + 1, "symbolSize": 6,
                         "encode": {"x": "lon", "y": "lat", "tooltip": ["name", "subtype", "block"]},
                         "itemStyle": {"color": COLOURS[g], "borderColor": "#ffffff", "borderWidth": 0.8}}
                        for i, g in enumerate(present)]),
                height=380, key="chart_map", alt="Business locations by longitude and latitude, coloured by governorate")
        else:
            st.caption("No data for this selection.")

    a = d["attribution"]
    st.caption(f"{a['licence']} {a['analysis']} Data extracted {', '.join(a['extracted'])}.")

# ---- ask --------------------------------------------------------------------------------------------------------


def show_turn(r):
    with st.chat_message("user"):
        st.markdown(literal(r["question"]))
    with st.chat_message("assistant"):
        if r["error"]:
            st.error(r["error"])
        if r["answer"]:
            st.markdown(literal(r["answer"]))
        if r.get("refused"):
            st.badge("Declined: the sources do not contain this answer", color="orange", icon=":material/block:")
        issues = (r.get("verification") or {}).get("issues") or []
        if issues:
            st.warning("\n".join(f"- {literal(i)}" for i in issues), title="Check this answer")
        if r["citations"]:
            with st.expander(f"Cited passages ({len(r['citations'])})", icon=":material/format_quote:"):
                for c in r["citations"]:
                    st.markdown(f"**[{literal(c['id'])}] {literal(c['document'])}**"
                                + (f", page {c['page']}" if c["page"] else "") + f", {literal(c['title'])}")
                    st.markdown("> " + literal(c["text"]).replace("  \n", "  \n> "))
                    if c.get("note"):
                        st.caption("Note: " + literal(c["note"]))
                    st.markdown(f"[Open the source]({c['url']})")
        searches = [c for c in r["tool_calls"] if c["name"] == "search_documents"]
        if searches:
            with st.expander("All retrieved passages", icon=":material/search:"):
                cited = {c["id"] for c in r["citations"]}
                for s in searches:
                    st.caption("Search: " + literal(s["args"].get("query", "")))
                    for p in s["result"].get("passages", []):
                        mark = "**cited** · " if p["id"] in cited else ""
                        st.markdown(f"{mark}[{literal(p['id'])}] {literal(p['title'])}"
                                    + (f" (page {p['page']})" if p.get("page") else "") + ": " + literal(p["text"]))
        computed = [c for c in r["tool_calls"] if c["name"] != "search_documents"]
        if computed:
            with st.expander(f"Computed figures ({len(computed)})", icon=":material/calculate:"):
                for c in computed:
                    st.code(f"{c['name']}({json.dumps(c['args'])})\n{json.dumps(c['result'], indent=1)}", language="text")
        st.caption(f"{r['model']}, {r['mode']}, {r['latency_s']} s, {r['tokens']['total']:,} tokens, "
                   f"{r['requests']} request{'' if r['requests'] == 1 else 's'}")


def take_example():
    st.session_state.pending = st.session_state.example
    st.session_state.example = None


def new_session():
    st.session_state.turns = []
    st.session_state.session_id = uuid.uuid4().hex


with tab_ask:
    v2_ready = bool(pipeline.varied_setting()["changed"])
    modes = [m for m in MODES if m != "v2" or v2_ready]
    with st.container(horizontal=True, vertical_alignment="bottom"):
        mode = st.selectbox("Configuration", modes, format_func=MODES.get, key="mode", width=320,
                            help=None if v2_ready else "v2 is set after the v1 failure analysis.")
        st.button("New session", on_click=new_session, icon=":material/restart_alt:")
    if not key_configured():
        st.error("No Gemini API key found, so questions cannot be answered. See README.md.", icon=":material/key_off:")
    if missing_docs:
        st.info("This copy could not download " + ", ".join(f"{m['id']} ({m['title']})" for m in missing_docs)
                + ". The publisher does not allow downloads by programs, so questions that need them are answered from "
                "the other documents only. The full tool runs on the group's computer.", icon=":material/info:")

    history, suggestions = st.container(), st.empty()
    if not turns:
        suggestions.pills("Try asking", EXAMPLES, key="example", on_change=take_example, label_visibility="collapsed")
    prompt = st.chat_input("Ask about businesses, governorates or licensing rules", max_chars=MAX_QUESTION,
                           submit_mode="disable", key="question") or st.session_state.pop("pending", None)
    with history:
        for r in turns:
            show_turn(r)
        if prompt and prompt.strip():
            suggestions.empty()
            wait = "Working. Baseline is paced to the free-tier limit and can take over a minute." \
                if mode == "baseline" else "Working..."
            with st.spinner(wait):
                record = pipeline.answer(prompt.strip(), turns, mode, st.session_state.session_id,
                                         run="app" if not missing_docs else "app-online")
            show_turn(record)
            if record["answer"]:
                turns.append(record)

# ---- query log and configuration --------------------------------------------------------------------------------

with tab_log:
    left, right = st.columns(2)
    with left, card("model", "Model and settings", f"Requests logged today: {pipeline.requests_today()} of "
                    f"{cfg['limits']['requests_per_day']} (free-tier daily limit, resets midnight Pacific)."):
        st.table({"setting": ["model", *pipeline.settings("v1")],
                  "value": [cfg["model"], *map(str, pipeline.settings("v1").values())]}, hide_index=True)
        st.caption(cfg["limits"]["source"])
    with right, card("varied", "Setting varied between v1 and v2", pipeline.varied_setting()["reason"]):
        changed = pipeline.varied_setting()["changed"]
        if changed:
            st.table([{"setting": s, "v1": str(v["v1"]), "v2": str(v["v2"])} for s, v in changed.items()], hide_index=True)
        else:
            st.markdown("None yet: v2 is identical to v1 until the intervention is chosen.")

    with card("log", "Every question asked", "Newest first. Each row is one record in logs/query_log.jsonl."):
        rows = pipeline.read_log()
        if rows:
            st.dataframe(pd.DataFrame([{
                "time (UTC)": r["time"][:19].replace("T", " "), "mode": r["mode"], "question": r["question"],
                "answer": "ERROR: " + r["error"] if r["error"] else r["answer"],
                "citations": ", ".join(c["id"] for c in r["citations"]), "latency (s)": r["latency_s"],
                "tokens": r["tokens"]["total"], "checks": f"{len(r['verification']['issues'])} flagged"
                if (r.get("verification") or {}).get("issues") else ""} for r in rows]),
                hide_index=True, height=420, alt="Query log: every question with its answer, citations, latency and tokens")
            st.download_button("Download log (JSONL)", data=pipeline.LOG.read_bytes(), file_name="query_log.jsonl",
                               mime="application/x-ndjson", on_click="ignore", icon=":material/download:")
        else:
            st.caption("No questions yet.")

# ---- sources ----------------------------------------------------------------------------------------------------

with tab_src:
    a = d["attribution"]
    gone = {m["id"] for m in missing_docs}
    with card("sources", "Sources", "Every dataset and document the tool uses, with where it was published."):
        st.dataframe(pd.DataFrame([{"ID": s["id"], "Source": s["title"], "Publisher": s["publisher"], "Link": s["url"],
                                    "Retrieved": s["retrieved"], "In this copy": "no" if s["id"] in gone else "yes"}
                                   for s in a["sources"]]),
                     hide_index=True, column_config={"Link": st.column_config.LinkColumn(display_text="Open")},
                     alt="Sources: datasets and documents with publisher, link and retrieval date")
    with card("limits", "Limits of use", ""):
        st.markdown(literal(a["limits"]))
    with card("licence", "Licence and attribution", ""):
        st.markdown(f"{literal(a['licence'])}\n\n{literal(a['analysis'])}\n\nData extracted: {', '.join(a['extracted'])}")
