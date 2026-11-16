"""F2, F3, F9: dashboard figures and the downloadable area profile, for the active filters.

Both are computed here from the clean tables, so the screen and the report cannot disagree.
"""
import csv
import html
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import retrieval
import tools

ROOT = Path(__file__).resolve().parent
GOVS = tools.GOVERNORATES
# Fixed per governorate, so a filter never repaints the survivors. Validated for dark mode
# and colour-blind readers; lines also carry direct labels as the second cue.
GOV_COLOURS = {"Capital": "#2fa66a", "Muharraq": "#4a8bdc", "Northern": "#c9832a", "Southern": "#c95f9c"}
FILTERS = ("governorate", "category", "subtype", "land_category", "nationality", "sex")
# From this period the data has only the four current governorates (see preparation log).
TREND_START = "2012-06"
DATA_LICENCE = ("Datasets provided by the {entities} via www.data.gov.bh are governed by the Bahrain Open Government "
                "Data License available at www.nea.gov.bh/Documents/OpenDataLicense.pdf. To the fullest extent "
                "permitted by law, the government is not liable for any damage or loss of any kind caused directly "
                "or indirectly by the use or availability of the datasets or any derived analyses or applications.")
ANALYSIS_NOTE = ("All analysis and transformation of the data in this tool is by IT8413 Group G1 and is not attributed "
                 "to the Information and eGovernment Authority or any government entity.")
LIMITS = ("Figures describe what is registered and published. They do not show whether a business will succeed. "
          "Businesses are from a registration snapshot, so some may have closed. Residents and land use are published "
          "by governorate only, so they cannot describe a block or neighbourhood. Legal documents are English translations for "
          "guidance: the Arabic text in the Official Gazette is official, and the Implementing Regulation and Procedures "
          "Guide copies do not include every later change. Confirm licensing requirements with the Ministry of Industry "
          "and Commerce before acting on them.")


def sources():
    with open(ROOT / "sources" / "SOURCES.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def attribution():
    data = [s for s in sources() if s["kind"] == "dataset"]
    entities = " and the ".join(sorted({s["publisher"] for s in data}))
    return {"licence": DATA_LICENCE.format(entities=entities), "analysis": ANALYSIS_NOTE, "limits": LIMITS,
            "extracted": sorted({s["retrieved"] for s in data}),
            "sources": [{k: s[k] for k in ("id", "kind", "title", "publisher", "url", "retrieved")} for s in sources()
                        if s["kind"] in ("dataset", "document")]}


def options():
    years = sorted({r["period"][:4] for r in tools.data()["population"] if r["period"] >= TREND_START}
                   | {r["period"][:4] for r in tools.data()["land_use"]})
    biz = tools.data()["businesses"]
    return {"governorate": GOVS, "category": tools.values("businesses", "category"),
            "subtype": tools.values("businesses", "subtype"),
            "subtypes_by_category": {c: sorted({r["subtype"] for r in biz if r["category"] == c})
                                     for c in tools.values("businesses", "category")},
            "land_category": tools.values("land_use", "category"),
            "nationality": tools.values("population", "nationality"), "sex": tools.values("population", "sex"),
            "years": years, "gov_colours": GOV_COLOURS}


def clean_filters(raw):
    """Validate filters from the browser against the real labels. Raises ValueError."""
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ValueError("filters must be an object")
    opts, out = options(), {}
    for key in FILTERS:
        wanted = raw.get(key) or []
        if not isinstance(wanted, list) or any(v not in opts[key] for v in wanted):
            raise ValueError(f"unknown value for filter '{key}'")
        out[key] = wanted
    for key, default in (("from_year", opts["years"][0]), ("to_year", opts["years"][-1])):
        out[key] = str(raw.get(key) or default)
        if out[key] not in opts["years"]:
            raise ValueError(f"unknown year for '{key}'")
    if out["from_year"] > out["to_year"]:
        raise ValueError("'from' year is after the 'to' year")
    return out


def dashboard(raw_filters=None):
    f = clean_filters(raw_filters)
    d = tools.data()
    govs = f["governorate"] or GOVS
    inside = lambda field, r, key: not f[key] or r[field] in f[key]

    biz = [r for r in d["businesses"] if r["governorate"] in govs
           and inside("category", r, "category") and inside("subtype", r, "subtype")]

    # Population: the latest period inside the selected years, and the trend across them.
    pop = [r for r in d["population"] if r["governorate"] in govs and inside("nationality", r, "nationality")
           and inside("sex", r, "sex") and TREND_START <= r["period"] and f["from_year"] <= r["period"][:4] <= f["to_year"]]
    pop_period = max((r["period"] for r in pop), default=None)
    residents = defaultdict(int)
    trend = defaultdict(dict)
    for r in pop:
        trend[r["governorate"]][r["period"]] = trend[r["governorate"]].get(r["period"], 0) + r["population"]
        if r["period"] == pop_period:
            residents[r["governorate"]] += r["population"]
    periods = sorted({r["period"] for r in pop})

    # Land use: one monthly snapshot (months are never added together).
    land = [r for r in d["land_use"] if r["governorate"] in govs and inside("category", r, "land_category")
            and f["from_year"] <= r["period"][:4] <= f["to_year"]]
    land_period = max((r["period"] for r in land), default=None)
    land_now = [r for r in land if r["period"] == land_period]
    by_land = defaultdict(float)
    for r in land_now:
        if r["area_m2"] is not None:
            by_land[r["category"]] += r["area_m2"]
    land_total = sum(by_land.values())
    missing = [f"{r['governorate']} / {r['category']} / {r['period']}" for r in land_now if r["area_m2"] is None]

    biz_gov = Counter(r["governorate"] for r in biz)
    rates = [{"governorate": g, "businesses": biz_gov[g], "residents": residents[g],
              "per_10k": round(biz_gov[g] / residents[g] * 10_000, 2) if residents[g] else None} for g in govs]
    total_residents = sum(residents.values())
    types = Counter(r["subtype"] for r in biz).most_common()
    blocks = Counter((r["block"], r["governorate"]) for r in biz).most_common(8)

    return {
        "filters": f,
        "kpis": {"businesses": len(biz), "residents": total_residents, "residents_period": pop_period,
                 "per_10k": round(len(biz) / total_residents * 10_000, 2) if total_residents else None,
                 "land_km2": round(land_total / 1e6, 2) if land_now else None, "land_period": land_period},
        "trend": {"periods": periods, "series": [{"governorate": g, "values": [trend[g].get(p) for p in periods]}
                                                 for g in govs if g in trend]},
        "rates": rates,
        "land": {"period": land_period, "missing": missing, "total_m2": round(land_total, 1),
                 "rows": [{"category": k, "km2": round(v / 1e6, 3),
                           "share": round(v / land_total * 100, 1) if land_total else 0}
                          for k, v in sorted(by_land.items(), key=lambda kv: -kv[1])]},
        "types": {"rows": [{"subtype": k, "count": v} for k, v in types[:10]],
                  "other": sum(v for _, v in types[10:]), "other_types": max(0, len(types) - 10)},
        "blocks": [{"block": b, "governorate": g, "count": n} for (b, g), n in blocks],
        "points": [{"lon": float(r["lon"]), "lat": float(r["lat"]), "name": r["name"], "subtype": r["subtype"],
                    "block": r["block"], "governorate": r["governorate"]} for r in biz],
        "attribution": attribution(),
    }


# ---- F9: downloadable report -----------------------------------------------------------

def _bars(rows, width=620, unit=""):
    """Horizontal bars as inline SVG, so the report is one self-contained file."""
    if not rows:
        return "<p>No data for this selection.</p>"
    top = max(v for _, v in rows) or 1
    gap, h, label = 28, 18, 210
    svg = [f'<svg role="img" viewBox="0 0 {width} {gap * len(rows)}" width="100%" style="max-width:{width}px">']
    for i, (name, value) in enumerate(rows):
        w = max(2, (width - label - 90) * value / top)
        svg.append(f'<text x="{label - 8}" y="{i * gap + 14}" text-anchor="end" font-size="12" fill="#333">{html.escape(str(name))}</text>'
                   f'<rect x="{label}" y="{i * gap + 2}" width="{w:.1f}" height="{h}" rx="3" fill="#2fa66a"/>'
                   f'<text x="{label + w + 6:.1f}" y="{i * gap + 15}" font-size="12" fill="#333">{value:,}{unit}</text>')
    return "".join(svg) + "</svg>"


def _describe(f):
    parts = [("Governorate", f["governorate"] or ["All four"]), ("Business category", f["category"] or ["All"]),
             ("Business type", f["subtype"] or ["All"]), ("Land use", f["land_category"] or ["All"]),
             ("Nationality", f["nationality"] or ["All"]), ("Sex", f["sex"] or ["All"]),
             ("Years", [f"{f['from_year']} to {f['to_year']}"])]
    return "".join(f"<tr><th>{k}</th><td>{html.escape(', '.join(v))}</td></tr>" for k, v in parts)


def _passages_for(f, turns):
    """Passages cited in this session's answers, then the rules that apply to the selected businesses."""
    chosen = {}
    for t in turns:
        for c in t.get("citations", []):
            chosen.setdefault(c["id"], c)
    wanted = f["subtype"] or f["category"] or ["business"]
    queries = [f"requirements approvals licenses to register {w}" for w in wanted[:3]] + \
              ["obtaining approvals and licenses from competent bodies after registration",
               "penalty practicing commercial activity without license"]
    for q in queries:
        for p in retrieval.search(q, 2):
            chosen.setdefault(p["id"], p)
    return list(chosen.values())[:8]


def report_html(raw_filters=None, turns=()):
    d = dashboard(raw_filters)
    f, k, e = d["filters"], d["kpis"], html.escape
    fmt = lambda v, suffix="": "not available" if v is None else f"{v:,}{suffix}"
    rate_rows = [(r["governorate"], r["per_10k"]) for r in d["rates"] if r["per_10k"] is not None]
    land_rows = [(r["category"], r["km2"]) for r in d["land"]["rows"][:8]]
    type_rows = [(r["subtype"], r["count"]) for r in d["types"]["rows"]]
    a = d["attribution"]
    passages = _passages_for(f, turns)
    qa = "".join(f"<div class='qa'><p><b>Q: {e(t['question'])}</b></p><p>{e(t['answer'] or 'No answer')}</p>"
                 f"<p class='meta'>Model {e(t['model'])}, mode {e(t['mode'])}</p></div>" for t in turns if t.get("answer"))
    missing = f"<p class='meta'>Missing from the source and left out of the total: {e('; '.join(d['land']['missing']))}.</p>" \
        if d["land"]["missing"] else ""
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Area profile, {date.today()}</title>
<style>body{{font:14px/1.5 system-ui,'Segoe UI',sans-serif;color:#222;max-width:820px;margin:32px auto;padding:0 16px}}
h1{{font-size:24px;margin:0 0 4px}}h2{{font-size:16px;margin:28px 0 8px;border-bottom:1px solid #ccc;padding-bottom:4px}}
table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:4px 8px;border-bottom:1px solid #e3e3e3;vertical-align:top}}
td.n,th.n{{text-align:right}}.kpis{{display:flex;flex-wrap:wrap;gap:12px}}.kpi{{flex:1;min-width:150px;border:1px solid #ccc;border-radius:4px;padding:10px}}
.kpi b{{display:block;font-size:22px}}.meta{{color:#666;font-size:12px}}blockquote{{margin:6px 0;padding:6px 12px;border-left:3px solid #2fa66a;background:#f5f7f6}}
.qa{{margin-bottom:12px}}@media print{{body{{margin:0}}h2{{break-after:avoid}}.kpi,svg{{break-inside:avoid}}}}</style>
<h1>Area profile</h1><p class="meta">Business support centre, generated {date.today()} by the IT8413 Group G1 tool.</p>
<h2>Current selection</h2><table>{_describe(f)}</table>
<h2>Summary figures</h2><div class="kpis">
<div class="kpi"><b>{k['businesses']:,}</b>registered businesses</div>
<div class="kpi"><b>{fmt(k['residents'] or None)}</b>residents ({e(k['residents_period'] or 'no period')})</div>
<div class="kpi"><b>{fmt(k['per_10k'])}</b>businesses per 10,000 residents</div>
<div class="kpi"><b>{fmt(k['land_km2'], ' km²')}</b>land ({e(k['land_period'] or 'no period')})</div></div>
<h2>Businesses per 10,000 residents</h2>{_bars(rate_rows)}
<table><tr><th>Governorate</th><th class="n">Businesses</th><th class="n">Residents</th><th class="n">Per 10,000</th></tr>
{''.join(f"<tr><td>{e(r['governorate'])}</td><td class='n'>{r['businesses']:,}</td><td class='n'>{r['residents']:,}</td><td class='n'>{fmt(r['per_10k'])}</td></tr>" for r in d['rates'])}</table>
<h2>Business types</h2>{_bars(type_rows)}{f"<p class='meta'>Plus {d['types']['other']:,} businesses in {d['types']['other_types']} other types.</p>" if d['types']['other'] else ''}
<h2>Land use, {e(d['land']['period'] or 'no data in these years')}</h2>{_bars(land_rows, unit=' km²')}{missing}
{f'<h2>Questions asked in this session</h2>{qa}' if qa else ''}
<h2>Rules that may apply: cited passages</h2>
{''.join(f"<p><b>[{e(p['id'])}] {e(p['document'])}</b>{', page ' + str(p['page']) if p['page'] else ''}, {e(p['title'])}</p><blockquote>{e(p['text'][:900])}{'...' if len(p['text']) > 900 else ''}</blockquote>" for p in passages) or '<p>No passages.</p>'}
<p class="meta">Passages are chosen by keyword search and may not be complete. Read the full document before relying on them.</p>
<h2>Limits of use</h2><p>{e(a['limits'])}</p>
<h2>Sources</h2><table><tr><th>Source</th><th>Publisher</th><th>Retrieved</th></tr>
{''.join(f"<tr><td>{e(s['title'])}</td><td>{e(s['publisher'])}</td><td>{e(s['retrieved'])}</td></tr>" for s in a['sources'])}</table>
<p class="meta">{e(a['licence'])}</p><p class="meta">{e(a['analysis'])}</p></html>"""


if __name__ == "__main__":
    # Filters must change the figures, and the totals must match the source tables.
    everything = dashboard()
    assert everything["kpis"]["businesses"] == 3419, everything["kpis"]
    assert everything["kpis"]["residents"] == 1603260 and everything["kpis"]["residents_period"] == "2025-06"
    one = dashboard({"governorate": ["Muharraq"], "subtype": ["Fast Food Restaurants"]})
    assert one["kpis"]["businesses"] == 105 and len(one["points"]) == 105
    assert one["kpis"]["residents"] == 297211
    women = dashboard({"governorate": ["Muharraq"], "nationality": ["Bahraini"], "sex": ["Female"]})
    assert women["kpis"]["residents"] == 72477
    past = dashboard({"to_year": "2020"})
    assert past["kpis"]["residents_period"] == "2020-06" and past["kpis"]["land_km2"] is None
    gap = dashboard({"governorate": ["Southern"], "land_category": ["Other"], "from_year": "2024", "to_year": "2026"})
    assert gap["land"]["period"] == "2026-02" and not gap["land"]["missing"]
    assert round(sum(r["share"] for r in everything["land"]["rows"])) == 100
    for bad in ({"governorate": ["Atlantis"]}, {"from_year": "2030"}, {"from_year": "2025", "to_year": "2020"}):
        try:
            dashboard(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted bad filter {bad}")
    page = report_html({"governorate": ["Capital"]},
                       [{"question": "<b>x</b>", "answer": "<script>", "model": "m", "mode": "v1", "citations": []}])
    assert "<script>" not in page and "&lt;script&gt;" in page and "<svg" in page
    print("analytics self-checks passed")
