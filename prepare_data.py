"""Downloads the real dataset from the Bahrain Open Data Portal into data.csv.

Source: Number of Visitors to Cultural, Archaeological and Heritage Sites
        Bahrain Authority for Culture and Antiquities (BACA)
        https://www.data.gov.bh/explore/dataset/number-of-visitors-to-baca-sites/

Re-run it to refresh the data:  python prepare_data.py
"""
import csv, io, urllib.request

DATASET = "number-of-visitors-to-baca-sites"
URL = (f"https://www.data.gov.bh/api/explore/v2.1/catalog/datasets/{DATASET}"
       "/exports/csv?delimiter=%2C&with_bom=false")

# The portal ships every label twice (English + Arabic) plus a row counter.
# Keep the English columns only, so each one becomes a usable filter.
KEEP = ["date", "location", "location_category",
        "visitors_category", "visitors_subcategory", "total_visitors"]
HEADERS = ["month", "site", "site_category",
           "visitor_type", "visitor_origin", "visitors"]

print("downloading...")
with urllib.request.urlopen(URL, timeout=180) as r:
    raw = r.read().decode("utf-8")

rows = list(csv.DictReader(io.StringIO(raw)))
if not rows:
    raise SystemExit("portal returned no rows - check the dataset id")

out = []
for r in rows:
    row = [r[c].strip() for c in KEEP]
    # 858 rows have no site_category in the source; label rather than drop them,
    # dropping would understate the visitor totals by ~18%.
    row[2] = row[2] or "Uncategorised"
    if not row[5]:
        continue
    out.append(row)

with open("data.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(HEADERS)
    w.writerows(out)

months = sorted({r[0] for r in out})
print(f"wrote data.csv: {len(out)} rows, {months[0]} to {months[-1]}, "
      f"{len({r[1] for r in out})} sites, "
      f"{sum(int(r[5]) for r in out):,} visitors")
