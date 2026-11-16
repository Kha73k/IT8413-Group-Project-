"""Builds the results spreadsheet from the run files and the test set.

    python evaluation/build_results.py                 trial runs -> evaluation/results/trial/results.xlsx
    python evaluation/build_results.py --label final   final runs -> evaluation/results/final/results.xlsx

One row per question and run. Run this again whenever a run finishes: the columns people fill in
(the scores, and everything on the vendor rows) are read back from the existing file and kept.
Every summary figure is an Excel formula over the Results sheet, so it follows the scores as they
are entered. Close the file in Excel before rebuilding.
"""
import argparse
import sys
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter as letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))
import pipeline  # noqa: E402
import run_eval  # noqa: E402

RUNS = ("control", "baseline", "v1", "v2", "vendor")
CHOICES = {
    "accuracy": ("correct", "partially correct", "incorrect"),
    "groundedness": ("grounded", "ungrounded", "no citation needed"),
    "refusal": ("correct answer", "correct refusal", "declined, should answer", "answered, should decline"),
    "completeness": ("complete", "partial", "not addressed"),
    "failure_category": ("retrieval wrong passage", "retrieval right, model ignored", "ambiguous question",
                         "sources lack the answer", "calculation wrong", "other"),
}
SCORES = (*CHOICES, "failure_notes", "scored_by")
# Typed in by hand on vendor rows, filled by the build on every other row.
VENDOR_ENTRY = ("answer", "citations", "tokens_total", "latency_s")
COLUMNS = ("question_id", "split", "type", "run", "question", "ground_truth", "source_location", "answer", "citations",
           "expected", "tool_outcome", "self_check_issues", "tokens_prompt", "tokens_output", "tokens_thoughts",
           "tokens_total", "est_cost_per_1000_q_usd", "latency_s", "requests", "retries", "error", *SCORES)
AUTO_FILL, HUMAN_FILL = PatternFill("solid", fgColor="E8EEF0"), PatternFill("solid", fgColor="FFF7CC")
HEAD_FONT, BODY_FONT = Font(name="Arial", bold=True, size=10), Font(name="Arial", size=10)


def expected(row):
    return "decline" if row["type"] == "unanswerable" else "answer"


def tool_outcome(row, record):
    """What the code can see. Control has no refusal phrase, so people judge that run by reading it."""
    if record["mode"] == "control":
        return "read it"
    if record["refused"]:
        return "correct refusal" if expected(row) == "decline" else "declined, should answer"
    return "answered, should decline" if expected(row) == "decline" else "answered"


def result_row(row, run, record):
    base = {"question_id": row["id"], "split": row["split"], "type": row["type"], "run": run,
            "question": row["question"], "ground_truth": row["ground_truth"],
            "source_location": row["source_location"], "expected": expected(row)}
    if not record:
        return base
    t = record["tokens"]
    return base | {
        "answer": record["answer"], "citations": ", ".join(c["id"] for c in record["citations"]),
        "tool_outcome": tool_outcome(row, record),
        "self_check_issues": "; ".join(record["verification"]["issues"]),
        "tokens_prompt": t["prompt"], "tokens_output": t["output"], "tokens_thoughts": t["thoughts"],
        "tokens_total": t["total"], "est_cost_per_1000_q_usd": round(record["cost_usd"] * 1000, 2),
        "latency_s": record["latency_s"], "requests": record["requests"], "retries": record["retries"],
        "error": record["error"],
    }


def kept_entries(path):
    """(question id, run) -> what people typed, from the existing workbook."""
    if not path.exists():
        return {}
    sheet = load_workbook(path)["Results"]
    head = [c.value for c in sheet[1]]
    kept = {}
    for values in sheet.iter_rows(min_row=2, values_only=True):
        row = dict(zip(head, values))
        keep = SCORES + (VENDOR_ENTRY if row["run"] == "vendor" else ())
        entries = {k: row[k] for k in keep if row.get(k) not in (None, "")}
        if entries:
            kept[row["question_id"], row["run"]] = entries
    return kept


def header(sheet, names, row=1):
    for i, name in enumerate(names, 1):
        c = sheet.cell(row, i, name)
        c.font, c.alignment = HEAD_FONT, Alignment(wrap_text=True, vertical="top")
        c.fill = HUMAN_FILL if name in SCORES else AUTO_FILL


def results_sheet(wb, rows, label, kept):
    sheet = wb.active
    sheet.title = "Results"
    header(sheet, COLUMNS)
    n = 1
    for row in rows:
        for run in RUNS:
            records = {} if run == "vendor" else run_eval.read_results(run_eval.RESULTS / label / f"{run}.jsonl")
            values = result_row(row, run, records.get(row["id"])) | kept.get((row["id"], run), {})
            n += 1
            for i, name in enumerate(COLUMNS, 1):
                c = sheet.cell(n, i, values.get(name))
                if isinstance(c.value, str):  # model output is text, even if it starts with "="
                    c.data_type = "s"
                c.font = BODY_FONT
                c.alignment = Alignment(wrap_text=name in ("question", "ground_truth", "answer"), vertical="top")
                if name in SCORES or (run == "vendor" and name in VENDOR_ENTRY):
                    c.fill = HUMAN_FILL
    widths = {"question": 40, "ground_truth": 40, "source_location": 26, "answer": 60, "citations": 14, "tool_outcome": 22,
              "self_check_issues": 30, "error": 20, "failure_notes": 30, **{k: 20 for k in CHOICES}}
    for i, name in enumerate(COLUMNS, 1):
        sheet.column_dimensions[letter(i)].width = widths.get(name, 11)
        if name in CHOICES:
            dv = DataValidation(type="list", formula1='"' + ",".join(CHOICES[name]) + '"', allow_blank=True)
            dv.error, dv.errorTitle = "Pick one of the listed values.", "Not a listed value"
            sheet.add_data_validation(dv)
            dv.add(f"{letter(i)}2:{letter(i)}{n}")
    sheet.freeze_panes = "E2"
    sheet.auto_filter.ref = f"A1:{letter(len(COLUMNS))}{n}"
    # A failure (PDF 7.4) with no category yet stands out, so the failure analysis misses none.
    col = {name: letter(i) for i, name in enumerate(COLUMNS, 1)}
    failed = (f'OR(${col["accuracy"]}2="incorrect",${col["groundedness"]}2="ungrounded",'
              f'${col["refusal"]}2="declined, should answer",${col["refusal"]}2="answered, should decline")')
    sheet.conditional_formatting.add(f'{col["failure_category"]}2:{col["failure_category"]}{n}',
                                     FormulaRule(formula=[f'AND({failed},${col["failure_category"]}2="")'],
                                                 fill=PatternFill("solid", bgColor="F4B6A6")))
    return col, n


def summary_sheet(wb, col, last):
    sheet = wb.create_sheet("Summary")
    rng = lambda name: f"Results!${col[name]}$2:${col[name]}${last}"  # noqa: E731
    measures = [
        ("Questions with an answer", lambda c: f'=COUNTIFS({c},{rng("answer")},"?*")'),
        ("Scored for accuracy", lambda c: f'=COUNTIFS({c},{rng("accuracy")},"?*")'),
        *[(f"Accuracy: {v}", lambda c, v=v: f'=COUNTIFS({c},{rng("accuracy")},"{v}")') for v in CHOICES["accuracy"]],
        ("Accuracy rate (correct / scored)", None),
        *[(f"Groundedness: {v}", lambda c, v=v: f'=COUNTIFS({c},{rng("groundedness")},"{v}")') for v in CHOICES["groundedness"]],
        *[(f"Refusal: {v}", lambda c, v=v: f'=COUNTIFS({c},{rng("refusal")},"{v}")') for v in CHOICES["refusal"]],
        *[(f"Completeness: {v}", lambda c, v=v: f'=COUNTIFS({c},{rng("completeness")},"{v}")') for v in CHOICES["completeness"]],
        *[(f"Failure: {v}", lambda c, v=v: f'=COUNTIFS({c},{rng("failure_category")},"{v}")') for v in CHOICES["failure_category"]],
        ("Average tokens per question", lambda c: f'=IFERROR(AVERAGEIFS({rng("tokens_total")},{c}),"")'),
        ("Average est. cost per 1000 questions (USD)", lambda c: f'=IFERROR(AVERAGEIFS({rng("est_cost_per_1000_q_usd")},{c}),"")'),
        ("Average latency (s)", lambda c: f'=IFERROR(AVERAGEIFS({rng("latency_s")},{c}),"")'),
        ("Average requests per question", lambda c: f'=IFERROR(AVERAGEIFS({rng("requests")},{c}),"")'),
    ]
    sheet["A1"] = "Each column is one run on one part of the test set (PDF 7.1: dev and held-out reported separately)."
    sheet["A1"].font = BODY_FONT
    header(sheet, ["Measure", *[f"{run} {split}" for split in ("dev", "held-out") for run in RUNS]], row=3)
    for r, (name, formula) in enumerate(measures, 4):
        sheet.cell(r, 1, name).font = BODY_FONT
        for i, (split, run) in enumerate(((s, run) for s in ("dev", "held-out") for run in RUNS), 2):
            where = f'{rng("run")},"{run}",{rng("split")},"{split}"'
            if formula is None:  # correct / scored, from the rows just above
                cell = letter(i)
                value = f'=IF({cell}{r - 4}=0,"",{cell}{r - 3}/{cell}{r - 4})'
            else:
                value = formula(where)
            c = sheet.cell(r, i, value)
            c.font = BODY_FONT
            if name.startswith("Accuracy rate"):
                c.number_format = "0.0%"
            elif name.startswith("Average"):
                c.number_format = "#,##0.00" if "tokens" not in name else "#,##0"
    sheet.column_dimensions["A"].width = 44
    for i in range(2, 12):
        sheet.column_dimensions[letter(i)].width = 11
    sheet.freeze_panes = "B4"
    self_check_sheet(sheet, rng, 4 + len(measures) + 2)


def self_check_sheet(sheet, rng, top):
    """Enhancement measure (PDF 10): how often the code's self-check catches what people scored as a problem."""
    sheet.cell(top, 1, "Self-verification, v1 and v2 answers (enhancement, PDF 10)").font = HEAD_FONT
    rows = [
        ("Flagged by the self-check", lambda run: f'=COUNTIFS({rng("run")},"{run}",{rng("self_check_issues")},"?*")'),
        ("Scored ungrounded or incorrect", lambda run: (
            f'=SUMPRODUCT(({rng("run")}="{run}")*((({rng("accuracy")}="incorrect")+({rng("groundedness")}="ungrounded"))>0))')),
        ("...of those, flagged (caught)", lambda run: (
            f'=SUMPRODUCT(({rng("run")}="{run}")*(({rng("self_check_issues")}<>"")*1)*'
            f'((({rng("accuracy")}="incorrect")+({rng("groundedness")}="ungrounded"))>0))')),
    ]
    header(sheet, ["Measure", "v1", "v2"], row=top + 1)
    for r, (name, formula) in enumerate(rows, top + 2):
        sheet.cell(r, 1, name).font = BODY_FONT
        for i, run in enumerate(("v1", "v2"), 2):
            sheet.cell(r, i, formula(run)).font = BODY_FONT
    r = top + 2 + len(rows)
    sheet.cell(r, 1, "Catch rate (caught / scored ungrounded or incorrect)").font = BODY_FONT
    for i in (2, 3):
        c = sheet.cell(r, i, f'=IF({letter(i)}{r - 2}=0,"",{letter(i)}{r - 1}/{letter(i)}{r - 2})')
        c.font, c.number_format = BODY_FONT, "0.0%"


def test_set_sheet(wb, rows):
    sheet = wb.create_sheet("Test set")
    names = list(rows[0])
    header(sheet, names)
    for r, row in enumerate(rows, 2):
        for i, name in enumerate(names, 1):
            c = sheet.cell(r, i, row[name])
            c.data_type = "s"
            c.font, c.alignment = BODY_FONT, Alignment(wrap_text=True, vertical="top")
    for i, name in enumerate(names, 1):
        sheet.column_dimensions[letter(i)].width = {"question": 50, "ground_truth": 50, "source_location": 35,
                                                    "verbatim_quotes": 50, "notes": 30}.get(name, 12)
    sheet.freeze_panes = "B2"


def guide_sheet(wb, label):
    sheet = wb.create_sheet("Guide")
    cfg = pipeline.config()
    lines = [
        (f"Results spreadsheet, run label: {label}", True),
        ("Yellow columns are filled in by a member. Grey-headed columns come from the run files; do not edit them.", False),
        ("Vendor rows: type the vendor's answer, citations and latency in the yellow cells. Tokens if the vendor shows them.", False),
        ("", False),
        ("How to score (PDF 7.3)", True),
        ("accuracy: compare the answer with ground_truth. correct / partially correct / incorrect.", False),
        ("groundedness: read the cited passage. Does it support the claim? Correct but unsupported = ungrounded. "
         "A figure from a function needs no citation: use 'no citation needed'.", False),
        ("refusal: tool_outcome is the code's reading of it. Confirm it, and judge control answers by reading them.", False),
        ("completeness: does it address every part of the question? complete / partial / not addressed.", False),
        ("", False),
        ("Failure analysis (PDF 7.4)", True),
        ("A failure is: incorrect, ungrounded, or a wrong refusal either way. The failure_category cell turns red until one is chosen.", False),
        ("Trace each one using logs/query_log.jsonl, which holds the passages and function calls behind every answer.", False),
        ("The intervention (PDF 7.5) targets the category with the most failures on the Summary sheet.", False),
        ("", False),
        ("Example of a scored row", True),
        ("accuracy=correct, groundedness=grounded, refusal=correct answer, completeness=complete, failure_category empty, "
         "failure_notes empty, scored_by=Rashed", False),
        ("", False),
        ("Latency", True),
        ("latency_s is time in the model and the tools. It leaves out waiting for the free-tier rate limit, which is logged "
         "separately as waited_s. Vendor rows: time the answer with a stopwatch.", False),
        ("", False),
        ("Cost", True),
        (f"Model {cfg['model']}. Estimated at published paid rates, ${cfg['pricing']['input_usd_per_million_tokens']:.2f} per 1M "
         f"input tokens and ${cfg['pricing']['output_usd_per_million_tokens']:.2f} per 1M output tokens including thinking. "
         f"Source: {cfg['pricing']['source']}", False),
    ]
    for r, (text, bold) in enumerate(lines, 1):
        c = sheet.cell(r, 1, text)
        c.font, c.alignment = HEAD_FONT if bold else BODY_FONT, Alignment(wrap_text=True, vertical="top")
    sheet.column_dimensions["A"].width = 110


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", default="trial")
    args = ap.parse_args()

    rows = run_eval.load_test_set()
    path = run_eval.RESULTS / args.label / "results.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = kept_entries(path)
    selected = run_eval.select(rows, args.label != "trial")
    wb = Workbook()
    col, last = results_sheet(wb, selected, args.label, kept)
    summary_sheet(wb, col, last)
    test_set_sheet(wb, rows)
    guide_sheet(wb, args.label)
    wb.calculation.fullCalcOnLoad = True
    wb.save(path)
    print(f"Written {path.relative_to(ROOT)}: {last - 1} rows, {len(kept)} rows of people's entries kept.")


if __name__ == "__main__":
    main()
