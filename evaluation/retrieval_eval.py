"""Enhancement: compares retrieval configurations on the test set. No API calls, so no cost or limits.

    python evaluation/retrieval_eval.py            development questions
    python evaluation/retrieval_eval.py --final    all questions, final evaluation only

A question counts if its ground truth has verbatim document quotes. Searching with the question text,
a quote is found when one of the top k passages contains it. Unanswerable questions have no quotes,
so they are left out. Prints a table and writes evaluation/results/retrieval_comparison.csv.
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))
import retrieval  # noqa: E402
import run_eval  # noqa: E402

CONFIGS = [(chunking, k) for chunking in ("structure", "window") for k in (2, 4, 6)]


def squash(text):
    """PDF extraction breaks words at random ("cir cumstances"), so compare without any spaces."""
    return "".join(text.lower().split())


def quotes(row):
    """'[T1] text | [T3] text' -> [('T1', 'text'), ...]"""
    return [(q.split("]", 1)[0].strip(" ["), q.split("]", 1)[1].strip())
            for q in row["verbatim_quotes"].split(" | ") if q.strip()]


def score(rows, chunking, k):
    found = total = complete = 0
    questions = [r for r in rows if quotes(r)]
    for row in questions:
        hits = [squash(p["text"]) for p in retrieval.search(row["question"], k, chunking)]
        wanted = [squash(text) for _, text in quotes(row)]
        got = sum(any(q in h for h in hits) for q in wanted)
        found, total, complete = found + got, total + len(wanted), complete + (got == len(wanted))
    return {"chunking": chunking, "k": k, "questions": len(questions), "quotes": total, "quotes_found": found,
            "quote_recall": round(found / total, 3), "questions_complete": complete,
            "question_recall": round(complete / len(questions), 3)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--final", action="store_true", help="include the held-out questions (final evaluation only)")
    args = ap.parse_args()

    results = [score(run_eval.select(run_eval.load_test_set(), args.final), c, k) for c, k in CONFIGS]
    path = run_eval.RESULTS / ("retrieval_comparison_final.csv" if args.final else "retrieval_comparison.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    print(f"{'chunking':10} {'k':>2} {'quotes found':>13} {'recall':>7} {'questions complete':>19}")
    for r in results:
        print(f"{r['chunking']:10} {r['k']:>2} {r['quotes_found']:>6}/{r['quotes']:<6} {r['quote_recall']:>7} "
              f"{r['questions_complete']:>12}/{r['questions']:<6}")
    print("Written:", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
