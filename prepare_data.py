"""F1: load the four published datasets and prepare them for analysis.

Reads the raw portal exports in sources/data/ and writes three clean tables to data/,
plus data/preparation_log.md, which records every decision and its effect in counts.

    python prepare_data.py

Raw (sources/data/)                  ->  Clean (data/)
  restaurants_cafes.csv  2,395 rows  ->  businesses.csv   (one table: category column)
  other_shops.csv        1,024 rows  ->
  land_use.csv           1,120 rows  ->  land_use.csv
  population_by_governorate.csv 320  ->  population.csv
"""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW, OUT = ROOT / "sources" / "data", ROOT / "data"

# Category labels: the portal's `type` column, renamed to plain English.
CATEGORY = {"RESTAURANTS": "Restaurants & cafes", "SHOPPING": "Shopping",
            "HEALTH SERVICES": "Health services"}


def read(name):
    with open(RAW / f"{name}.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(name, header, rows):
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def label(s):
    # Restaurants/shops use "CAPITAL", land use/population use "Capital": one spelling.
    return " ".join(s.split()).title()


def businesses(log):
    rows = []
    for source in ("restaurants_cafes", "other_shops"):
        raw = read(source)
        for r in raw:
            rows.append([
                f"{source[0].upper()}{int(float(r['n']))}",   # stable id: R699, O12
                " ".join(r["name"].split()),
                CATEGORY[r["type"].strip()],
                label(r["subtype"]),
                int(float(r["block"])),                       # "346.0" -> 346
                label(r["governorate"]),
                round(float(r["x_longitude"]), 6),
                round(float(r["y_latitude"]), 6),
            ])
        log.append(f"- `{source}.csv`: {len(raw):,} rows read, {len(raw):,} kept.")
    # One exact duplicate exists (same name, block and coordinates). Kept: units in one mall
    # often share a geocode, and the portal publishes them as two registration records.
    key = Counter((r[1].upper(), r[4], r[6], r[7]) for r in rows)
    dups = {k: n for k, n in key.items() if n > 1}
    log.append(f"- Identical name + block + coordinates: {len(dups)} group(s) "
               + ", ".join(f"{k[0]} block {k[1]} (x{n})" for k, n in dups.items())
               + ". **Kept**: units in one building can share coordinates, and they are separate "
                 "registration records. Removing them would change published counts.")
    log.append("- Arabic duplicate columns (`l_sm`, `ltsnyf`, `ltsnyf_lfr_y`, `lmhfzt`) and the "
               "`location` column (a copy of the coordinates) dropped.")
    log.append("- `type` renamed to `category`: " + ", ".join(f"{k} -> {v}" for k, v in CATEGORY.items()) + ".")
    log.append("- Labels: governorate and subtype converted from UPPERCASE to Title Case "
               "(e.g. `CAPITAL` -> `Capital`, `COFFEE SHOPS` -> `Coffee Shops`) so they match the other datasets.")
    log.append("- `block` stored as a whole number (`346.0` -> `346`). No missing values in any column.")
    log.append("- **Limitation:** this is a registration snapshot (portal modified 2026-04-28). It has no "
               "opening or closing dates, so it may include businesses that have since closed.")
    write("businesses", ["id", "name", "category", "subtype", "block", "governorate", "lon", "lat"], rows)
    return rows


def land_use(log):
    raw, rows, missing = read("land_use"), [], []
    for r in raw:
        number = r["area"].replace("m2", "").strip()      # "16398662.168012 m2" -> number
        period = f"{r['year']}-{r['month'][:2]}"            # "2024", "07 July" -> "2024-07"
        if not number:
            missing.append(f"{label(r['governorate'])} / {r['land_use_category']} / {period}")
        rows.append([period, label(r["governorate"]), r["land_use_category"].strip(),
                     round(float(number), 3) if number else ""])
    log.append(f"- {len(raw):,} rows read, {len(raw):,} kept.")
    log.append("- **Units:** `area` is published as text with the unit (`\"16398662.168012 m2\"`). "
               "The unit is stripped and the number stored in `area_m2`. Every row uses m2. "
               "The dashboard shows km2 (m2 / 1,000,000).")
    log.append(f"- **Missing values:** {len(missing)} row(s) have the unit but no number: "
               f"{', '.join(missing)}. Kept with an empty `area_m2`: never filled in or estimated. "
               "Totals that include it say so, and a question about it is answered as not available.")
    log.append("- `year` + `month` (`2024`, `07 July`) combined into one sortable `period` (`2024-07`).")
    log.append("- **Stock, not flow:** each month is a full snapshot of land use. Never add months together; "
               "use one period (the latest, 2026-02, by default).")
    log.append("- Arabic duplicate columns and the `n` row counter dropped.")
    write("land_use", ["period", "governorate", "category", "area_m2"], rows)
    return rows


def population(log):
    raw, rows = read("population_by_governorate"), []
    for r in raw:
        rows.append([r["year"].strip(), label(r["governorate"]), r["nationality"].strip(),
                     r["sex"].strip(), int(float(r["population"]))])
    log.append(f"- {len(raw):,} rows read, {len(raw):,} kept. No missing values.")
    old = sorted({f"{p[1]} ({p[0]})" for p in rows if p[1] in ("Central", "Not Stated")})
    log.append(f"- **Boundary change:** `Central` and `Not Stated` appear only in 2010-06 and 2011-06 "
               f"({', '.join(old)}). From 2012-06 the data has only the four current governorates, so their "
               "boundaries differ before and after. Kept as published; comparisons over time per governorate "
               "should start from 2012-06. (Background, not from these sources: the Central governorate was "
               "abolished in 2014.)")
    log.append("- Periods are mid-year (`YYYY-06`) for 2010-2025, plus year-end (`YYYY-12`) from 2022.")
    log.append("- `population` stored as a whole number. Arabic duplicate columns dropped.")
    write("population", ["period", "governorate", "nationality", "sex", "population"], rows)
    return rows


def main():
    OUT.mkdir(exist_ok=True)
    sections = {}
    for name, fn in (("Businesses (restaurants & cafes + other shops)", businesses),
                     ("Land use", land_use), ("Population", population)):
        log = []
        sections[name] = (fn(log), log)
    total = sum(len(rows) for rows, _ in sections.values())
    text = ["# Data preparation log", "",
            "Generated by `prepare_data.py` from the raw exports in `sources/data/`. Do not edit by hand.", "",
            f"**{total:,} rows** in the working data. All three tables share `governorate`.", ""]
    for name, (rows, log) in sections.items():
        text += [f"## {name} — {len(rows):,} rows", "", *log, ""]
    (OUT / "preparation_log.md").write_text("\n".join(text), encoding="utf-8")
    print("\n".join(text))


if __name__ == "__main__":
    main()
