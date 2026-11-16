# IT8413 Group Project: Business Location and Licensing (Brief D)

Group G1: Khalifa (Kha73k), Rashed (rashed914), Ahmed (dudeeturtle-crypto)

A web tool for a business support centre in Bahrain. It answers questions about where similar
businesses operate, what each governorate is like, and which registration and licensing rules
apply, from published data and documents only.

## Setup

Built and tested on Python 3.12.

```bash
pip install -r requirements.txt
```

**1. API key.** Create a free key in [Google AI Studio](https://aistudio.google.com/apikey), then put it on
the first line of a file called `api.txt` in this folder, or set the `GEMINI_API_KEY` environment
variable. `api.txt` is ignored by git. Never put a key anywhere else.

**2. Documents.** Download each document from the page linked in
[`sources/SOURCES.csv`](sources/SOURCES.csv) into the path in its `local_file` column, under `sources/`. T4 is a web page,
so print it to PDF from the browser. They are not in this repository because the publishers' terms do not allow
republishing without permission. The dashboard and data questions work without them. The report, and any question that
needs a document, stops with a message naming the missing file.

**3. Prepare the data.** This writes `data/` from the raw files in `sources/data/`. The cleaning decisions
are recorded in [`data/preparation_log.md`](data/preparation_log.md).

```bash
python prepare_data.py
```

## Run

```bash
python app.py
```

Then open http://localhost:8000. The server only accepts connections from this computer.

- **Dashboard:** filters, summary figures, four charts and a map. Every panel has a table view.
- **Ask:** questions in one session, with citations you can open and the functions that computed each figure.
- **Query log:** every question with its answer, citations, latency and tokens, plus the model and settings.
- **Sources:** publishers, links, retrieval dates, limits of use and the licence statement.
- **Download area profile:** a report for the current filters and the questions asked in the session.

## Evaluate

`evaluation/test_set.csv` holds the questions, split into development and held-out.

```bash
python evaluation/run_eval.py --mode control
python evaluation/run_eval.py --mode baseline
python evaluation/run_eval.py --mode v1
python evaluation/build_results.py
```

These run the development questions only and write `evaluation/results/trial/`. A run that stops can be
continued with the same command. `--dry-run` shows the plan and sends nothing. The baseline sends every source
in the prompt, so it runs at about one question a minute.

Held-out questions run only in the final evaluation, and only once every question has been signed in the
`verified_by` column:

```bash
python evaluation/run_eval.py --mode v1 --final --label final
```

`evaluation/retrieval_eval.py` compares retrieval settings on the test set, with no API calls.

## How it works

| File | Role |
|---|---|
| `prepare_data.py` | Cleans the four datasets into `data/` |
| `analytics.py` | Dashboard figures and the report |
| `retrieval.py` | Splits the documents into passages and searches them (BM25) |
| `tools.py` | The functions the model can call. Every data figure comes from here |
| `pipeline.py` | Answers a question in any of the four configurations, checks the answer, writes the log |
| `llm.py` | Gemini client, paced under the limits, stops when the daily quota is used up |
| `config.json` | Model, limits, prices, and the settings for v1 and v2 |
| `app.py`, `index.html` | The web application |
| `evaluation/` | Test set, run script, retrieval comparison, results spreadsheet |

The app and the evaluation call the same `pipeline.answer()`, so results come from the submitted tool.

## Sources and licence

Full register with publisher, URL, licence and retrieval date: [`sources/SOURCES.csv`](sources/SOURCES.csv).

Datasets provided by the Information & eGovernment Authority (iGA) and the Urban Planning and Development
Authority (UPDA) via www.data.gov.bh are governed by the Bahrain Open Government Data License available at
www.nea.gov.bh/Documents/OpenDataLicense.pdf. To the fullest extent permitted by law, the government is not
liable for any damage or loss of any kind caused directly or indirectly by the use or availability of the
datasets or any derived analyses or applications.

All analysis and transformation of the data in this tool is by IT8413 Group G1 and is not attributed to the
Information and eGovernment Authority or any government entity.

## Use of AI

Built with Claude Code, directed by the group. The test questions were first drafted with AI and must be
verified by a member against the sources before use.
