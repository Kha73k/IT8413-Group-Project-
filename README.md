# IT8413 Group Project — Business Location and Licensing (Brief D)

Khalifa (Kha73k) · Rashed (rashed914) · Ahmed (dudeeturtle-crypto)

**Status: proposal stage.** This repository shows the work prepared so far for tutor
feedback. The tool itself has not been built yet; building starts after the sources
are approved.

## The scenario

A business support centre advises people opening a small business in Bahrain. The tool
answers their three typical questions from published sources:

1. Where do similar businesses already operate?
2. What is each area like (residents, land use)?
3. Which registration and licensing rules apply?

## Proposed sources

Full register with publisher, URL, licence and retrieval date: [`sources/SOURCES.csv`](sources/SOURCES.csv).

**Datasets** — Bahrain Open Data Portal, under the Bahrain Open Government Data License
v1.0. 4,859 rows in total. All four share **governorate**.

| Dataset | Rows | Publisher |
|---|---|---|
| Restaurants & cafes (25 types, 248 blocks) | 2,395 | Information & eGovernment Authority |
| Other shops (pharmacies, jewellers, furniture, car showrooms, sweets) | 1,024 | Information & eGovernment Authority |
| Land use by category and governorate (monthly, Jul 2024 – Feb 2026) | 1,120 | Urban Planning & Development Authority |
| Population by governorate, nationality and sex (2010 – 2025) | 320 | Information & eGovernment Authority |

**Documents** — Ministry of Industry and Commerce (MOIC), in English:

| Document | Role |
|---|---|
| Legislative Decree No. 27 of 2015, Commercial Register | the law |
| Order No. 126 of 2016, Implementing Regulation | the regulation under that law |
| Procedures Guide for Establishments and Commercial Companies (2022 edition) | official guidance |
| Sijilat activity 5610-1, Food and beverage service activities | restaurant-specific requirements |

The PDFs are **not in this repository yet**: we are still confirming MOIC's terms for
republishing them. Each one can be downloaded from the URL in `SOURCES.csv`.

## Draft test set

[`evaluation/test_set.csv`](evaluation/test_set.csv) holds 30 questions with answers and exact
source locations: 7 document-only, 7 combined, 6 unanswerable, 4 counter-intuitive and
6 direct lookups. They are split into 15 development and 15 held-out questions.

- Data answers are calculated by [`evaluation/build_test_set.py`](evaluation/build_test_set.py)
  from the files in `sources/data/`, so every figure can be reproduced.
- Every document answer carries a word-for-word quote, and the script checks that each
  quote appears in the named PDF.
- **The questions were drafted with AI assistance (Claude) and are not yet verified.**
  Each group member will check rows against the sources and sign them off in the
  `verified_by` column before the proposal is submitted.

To rebuild it, put the PDFs in `sources/documents/` (file names are in `SOURCES.csv`) and run:

```
pip install pypdf
python evaluation/build_test_set.py
```

## Model

`gemini-3.5-flash-lite` on the Gemini API free tier: 15 requests/min, 250K tokens/min,
500 requests/day. A full evaluation (control, baseline, v1 and v2 on 30 questions) needs
about 240 requests.

Measured with Gemini's token counter: pasting every source into one prompt (the baseline
run) takes 144K tokens. With the portal's duplicate Arabic columns it would be 434K,
which is over the per-minute limit. So removing those columns is required, not optional.

**API keys are never committed.** The key goes in `api.txt` (ignored by git) or an
environment variable.

## Earlier prototype

`index.html`, `app.py`, `prepare_data.py` and `data.csv` are a dashboard prototype built
before the brief was released, using a heritage-site visitors dataset. It shows the
planned dashboard style (filters, charts, question box). It will be rebuilt on the Brief D
datasets with the Gemini model.
