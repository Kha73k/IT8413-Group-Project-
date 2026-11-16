"""F4 tool use: functions the model calls so that every number comes from code.

The model never sees raw rows in v1/v2. It asks a question of the data through one of these
functions, and the result (with the filters that produced it) is shown next to the answer.
"""
import ast
import csv
import operator
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

import retrieval

ROOT = Path(__file__).resolve().parent


def _read(name):
    with open(ROOT / "data" / f"{name}.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=None)
def data():
    """Clean tables written by prepare_data.py."""
    biz = _read("businesses")
    for r in biz:
        r["block"] = int(r["block"])
    pop = _read("population")
    for r in pop:
        r["population"] = int(r["population"])
    land = _read("land_use")
    for r in land:
        r["area_m2"] = float(r["area_m2"]) if r["area_m2"] else None
    return {"businesses": biz, "population": pop, "land_use": land}


def values(table, field):
    return sorted({r[field] for r in data()[table]})


GOVERNORATES = ["Capital", "Muharraq", "Northern", "Southern"]


def _match(table, field, wanted, partial=False):
    """Case-insensitive match against the real labels; returns (labels, error)."""
    if wanted in (None, "", []):
        return None, None
    wanted = [wanted] if isinstance(wanted, (str, int)) else wanted
    known, labels = values(table, field), []
    for w in wanted:
        w = str(w).strip().lower()
        hit = [k for k in known if str(k).lower() == w] or \
              ([k for k in known if w in str(k).lower()] if partial else [])
        if not hit:
            return None, f"unknown {field} '{w}'. Valid values: {', '.join(map(str, known))}"
        labels += hit
    return sorted(set(labels)), None


def _filters(table, spec):
    """spec: {field: (value, partial)} -> (row filter, applied labels, error)."""
    chosen = {}
    for field, (wanted, partial) in spec.items():
        labels, err = _match(table, field, wanted, partial)
        if err:
            return None, None, err
        if labels is not None:
            chosen[field] = labels
    keep = lambda r: all(r[f] in v for f, v in chosen.items())
    return keep, chosen, None


def count_businesses(governorate=None, category=None, subtype=None, block=None, name=None, group_by=None):
    keep, applied, err = _filters("businesses", {"governorate": (governorate, False), "category": (category, True),
                                                 "subtype": (subtype, True)})
    if err:
        return {"error": err}
    rows = [r for r in data()["businesses"] if keep(r)
            and (block is None or r["block"] == int(block))
            and (not name or name.strip().lower() in r["name"].lower())]
    if block is not None:
        applied["block"] = int(block)
    if name:
        applied["name contains"] = name
    out = {"dataset": "businesses (restaurants & cafes + other shops, registration snapshot)",
           "filters_applied": applied, "count": len(rows)}
    if group_by:
        if group_by not in ("governorate", "category", "subtype", "block"):
            return {"error": "group_by must be governorate, category, subtype or block"}
        groups = Counter(r[group_by] for r in rows)
        out["groups"] = dict(groups.most_common(25))
        if len(groups) > 25:
            out["note"] = f"{len(groups)} groups; the 25 largest are shown"
    if name or len(rows) <= 10:
        out["rows"] = [{k: r[k] for k in ("name", "category", "subtype", "block", "governorate")} for r in rows[:20]]
    return out


def get_population(period=None, governorate=None, nationality=None, sex=None, group_by=None):
    periods = values("population", "period")
    period = period or periods[-1]
    if group_by != "period" and period not in periods:
        return {"error": f"unknown period '{period}'. Valid periods: {', '.join(periods)}"}
    keep, applied, err = _filters("population", {"governorate": (governorate, False),
                                                 "nationality": (nationality, False), "sex": (sex, False)})
    if err:
        return {"error": err}
    rows = [r for r in data()["population"] if keep(r) and (group_by == "period" or r["period"] == period)]
    out = {"dataset": "population by governorate, nationality and sex", "filters_applied": applied}
    if group_by == "period":
        groups = defaultdict(int)
        for r in rows:
            groups[r["period"]] += r["population"]
        out["groups"] = dict(sorted(groups.items()))
        out["note"] = "Central and Not Stated governorates exist only in 2010-06 and 2011-06; boundaries differ before 2012."
        return out
    out["period"] = period
    out["population"] = sum(r["population"] for r in rows)
    if group_by:
        if group_by not in ("governorate", "nationality", "sex"):
            return {"error": "group_by must be governorate, nationality, sex or period"}
        groups = defaultdict(int)
        for r in rows:
            groups[r[group_by]] += r["population"]
        out["groups"] = dict(sorted(groups.items(), key=lambda kv: -kv[1]))
    return out


def get_land_use(period=None, governorate=None, category=None, group_by=None):
    periods = values("land_use", "period")
    period = period or periods[-1]
    if group_by != "period" and period not in periods:
        return {"error": f"unknown period '{period}'. Valid periods: {', '.join(periods)}"}
    keep, applied, err = _filters("land_use", {"governorate": (governorate, False), "category": (category, True)})
    if err:
        return {"error": err}
    rows = [r for r in data()["land_use"] if keep(r) and (group_by == "period" or r["period"] == period)]
    missing = [f"{r['governorate']} / {r['category']} / {r['period']}" for r in rows if r["area_m2"] is None]
    out = {"dataset": "land use by category and governorate (monthly snapshots)", "unit": "m2",
           "filters_applied": applied}
    if missing:
        out["missing_values"] = missing
        out["note"] = "Missing values are excluded from totals, not estimated."
    if group_by == "period":
        groups = defaultdict(float)
        for r in rows:
            if r["area_m2"] is not None:
                groups[r["period"]] += r["area_m2"]
        out["groups"] = {k: round(v, 1) for k, v in sorted(groups.items())}
        out["note"] = (out.get("note", "") + " Each month is a full snapshot: compare months, never add them.").strip()
        return out
    out["period"] = period
    known = [r["area_m2"] for r in rows if r["area_m2"] is not None]
    if not known:
        out["area_m2"] = out["area_km2"] = None
        out["note"] = "No published value for this selection."
        return out
    out["area_m2"], out["area_km2"] = round(sum(known), 1), round(sum(known) / 1e6, 3)
    if group_by:
        if group_by not in ("governorate", "category"):
            return {"error": "group_by must be governorate, category or period"}
        groups = defaultdict(float)
        for r in rows:
            if r["area_m2"] is not None:
                groups[r[group_by]] += r["area_m2"]
        out["groups_m2"] = {k: round(v, 1) for k, v in sorted(groups.items(), key=lambda kv: -kv[1])}
    return out


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}


def calculate(expression):
    """Arithmetic only (+ - * / ** and brackets): no names, calls or attributes."""
    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("exponent too large")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("only numbers and + - * / ** ( ) are allowed")
    try:
        if len(expression) > 200:
            raise ValueError("expression too long")
        value = ev(ast.parse(expression.replace(",", ""), mode="eval").body)
        return {"expression": expression, "result": round(value, 6)}
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as e:
        return {"error": f"cannot calculate '{expression}': {e}"}


def search_documents(query, k=4, chunking="structure"):
    hits = retrieval.search(query, k, chunking)
    return {"query": query, "passages": [{"id": p["id"], "document": p["document"], "title": p["title"],
                                          "page": p["page"], "text": p["text"], **({"note": p["note"]} if p["note"] else {})}
                                         for p in hits]}


FUNCTIONS = {f.__name__: f for f in (count_businesses, get_population, get_land_use, calculate, search_documents)}


def declarations():
    """Gemini function declarations, with the real labels so the model can pick valid values."""
    gov = {"type": "string", "enum": GOVERNORATES, "description": "One governorate. Omit for all of Bahrain."}
    s = lambda d: {"type": "string", "description": d}
    pop_periods, land_periods = values("population", "period"), values("land_use", "period")
    return [
        {"name": "count_businesses",
         "description": "Count registered businesses (restaurants, cafes and other shops) by location and type. "
                        "Location is known by governorate and block only. Returns the count, optional groups, "
                        "and the matching rows when there are 10 or fewer.",
         "parameters": {"type": "object", "properties": {
             "governorate": gov,
             "category": s("One of: " + ", ".join(values("businesses", "category"))),
             "subtype": s("Business type, partial match allowed. Values: " + ", ".join(values("businesses", "subtype"))),
             "block": {"type": "integer", "description": "Block number, e.g. 346"},
             "name": s("Part of a business name, e.g. 'Frangipani'"),
             "group_by": {"type": "string", "enum": ["governorate", "category", "subtype", "block"]}}}},
        {"name": "get_population",
         "description": "Population totals. Published by governorate only (not by block or area). "
                        f"Periods: {pop_periods[0]} to {pop_periods[-1]} (mid-year YYYY-06, plus year-end YYYY-12 "
                        f"from 2022). Default period: {pop_periods[-1]}. group_by=period gives a time series.",
         "parameters": {"type": "object", "properties": {
             "period": s("YYYY-MM, e.g. 2025-06"), "governorate": gov,
             "nationality": {"type": "string", "enum": values("population", "nationality")},
             "sex": {"type": "string", "enum": values("population", "sex")},
             "group_by": {"type": "string", "enum": ["governorate", "nationality", "sex", "period"]}}}},
        {"name": "get_land_use",
         "description": "Land area (m2) by land use category and governorate, from monthly snapshots "
                        f"{land_periods[0]} to {land_periods[-1]} (default {land_periods[-1]}). "
                        "Categories: " + ", ".join(values("land_use", "category")) + ".",
         "parameters": {"type": "object", "properties": {
             "period": s("YYYY-MM"), "governorate": gov, "category": s("Land use category"),
             "group_by": {"type": "string", "enum": ["governorate", "category", "period"]}}}},
        {"name": "calculate",
         "description": "Evaluate arithmetic on numbers returned by the other functions (percentages, rates, "
                        "differences, growth). Use this for every calculation.",
         "parameters": {"type": "object", "properties": {"expression": s("e.g. (431075 - 375648) / 375648 * 100")},
                        "required": ["expression"]}},
        {"name": "search_documents",
         "description": "Search the registration and licensing documents (Commercial Register Law No. 27/2015 as "
                        "amended, Law No. 9/2022, the Implementing Regulation No. 126/2016 and Decision No. 68/2018 amending "
                        "it, the MOIC Procedures Guide, Legislative Decree No. 28/2020 amending the Commercial Companies "
                        "Law, and the Sijilat page for food and beverage activities). Returns passages with ids to cite.",
         "parameters": {"type": "object", "properties": {"query": s("What to look for, in plain words")},
                        "required": ["query"]}},
    ]


def call(name, args, settings):
    if name not in FUNCTIONS:
        return {"error": f"unknown function {name}"}
    if name == "search_documents":
        args = dict(args, k=settings["top_k"], chunking=settings["chunking"])
    try:
        return FUNCTIONS[name](**args)
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}


if __name__ == "__main__":
    import json
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    checks = [
        count_businesses(governorate="Muharraq", subtype="fast food"),
        count_businesses(name="Frangipani"),
        get_population(period="2025-06", governorate="Muharraq", nationality="Bahraini", sex="Female"),
        get_land_use(period="2025-09", governorate="Southern", category="Other"),
        calculate("105 / 607 * 100"),
        calculate("__import__('os')"),
        count_businesses(governorate="Central"),
    ]
    for c in checks:
        print(json.dumps(c, ensure_ascii=False)[:300])
    assert checks[0]["count"] == 105 and checks[2]["population"] == 72477
    assert checks[3]["area_m2"] is None and checks[3]["missing_values"]
    assert "error" in calculate("9 ** 9 ** 9")
    assert "error" in checks[5] and "error" in checks[6]
    print("tool self-checks passed")
