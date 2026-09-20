# Dataset Dashboard

Filterable dashboard + AI Q&A over a CSV. No `pip install` needed — Python stdlib only.

## Run

```
set ANTHROPIC_API_KEY=sk-ant-...
python app.py
```

Open http://localhost:8000. Without the key the dashboard still works; the **Ask** tab won't.

## Dataset

**Number of Visitors to Cultural, Archaeological and Heritage Sites** — published by the
Bahrain Authority for Culture and Antiquities (BACA) on the
[Bahrain Open Data Portal](https://www.data.gov.bh/explore/dataset/number-of-visitors-to-baca-sites/).

4,761 rows · Aug 2023 – Aug 2026 · 33 sites · 6,098,692 visitors.

`python prepare_data.py` re-downloads it. Two things it does to the raw export:
the portal repeats every label in Arabic, so only the English columns are kept;
and 858 rows have no `site_category`, labelled `Uncategorised` rather than dropped
(dropping them would understate totals by ~18%).

## Using a different dataset

Replace `data.csv` and reload. Columns are detected automatically:

| detected as | rule |
|---|---|
| date axis | column named `date`/`month`/`year`/`time`/`period`, or values like `2024-03` |
| measure | first numeric column |
| filters | remaining text columns with ≤ 60 distinct values |

## Files

- `index.html` — UI, filters, charts (Chart.js from CDN)
- `app.py` — static server + `POST /ask` → Claude API
- `prepare_data.py` — downloads and cleans the dataset
- `data.csv` — the data the dashboard reads
