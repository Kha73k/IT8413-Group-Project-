"""Runs the test set through one configuration, using the same pipeline as the web app.

    python evaluation/run_eval.py --mode v1                    development questions, label "trial"
    python evaluation/run_eval.py --mode v1 --dry-run          show the plan, send nothing
    python evaluation/run_eval.py --mode v1 --final --label final    the full set, final evaluation only

Results go to evaluation/results/<label>/<mode>.jsonl, one line per answer. A run can be stopped and
started again: questions already answered without an error are skipped. It stops by itself when the
daily quota is used up, so run the same command again after midnight Pacific.

The held-out questions (PDF 7.1) only run with --final, and --final refuses to start until every
question has been checked and signed by a member (PDF 13).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pipeline  # noqa: E402

TEST_SET = ROOT / "evaluation" / "test_set.csv"
RESULTS = ROOT / "evaluation" / "results"
# Requests per question: control and baseline send one. v1 and v2 use whatever the log has measured.
ASSUMED_TOOL_REQUESTS = 3


def load_test_set():
    with open(TEST_SET, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def select(rows, final):
    """Development questions unless this is the final evaluation."""
    return rows if final else [r for r in rows if r["split"] == "dev"]


def require_verified(rows):
    missing = [r["id"] for r in rows if not r["verified_by"].strip()]
    if missing:
        sys.exit(f"--final refused: not yet verified by a member: {', '.join(missing)}")


def read_results(path):
    """question id -> latest record. A later line for the same question replaces an earlier one."""
    done = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                done[record["question_id"]] = record
    return done


def requests_per_question(mode):
    if mode in ("control", "baseline"):
        return 1, "one request per question, by design"
    seen = [r["requests"] for r in pipeline.read_log(100000) if r["mode"] == mode and r["requests"]]
    if not seen:
        return ASSUMED_TOOL_REQUESTS, f"assumed {ASSUMED_TOOL_REQUESTS}: no {mode} questions in the log yet"
    return sum(seen) / len(seen), f"measured from {len(seen)} logged {mode} questions"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", required=True, choices=pipeline.MODES)
    ap.add_argument("--final", action="store_true", help="include the held-out questions (final evaluation only)")
    ap.add_argument("--label", default="trial", help="results folder name, default: trial")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.mode == "v2" and not pipeline.varied_setting()["changed"]:
        sys.exit("v2 is not defined yet: set the change in config.json after the v1 failure analysis")
    if args.final and args.label == "trial":
        sys.exit("--final needs a --label such as final, so it cannot mix with trial results")

    rows = load_test_set()
    if args.final and not args.dry_run:
        require_verified(rows)
    todo_rows = select(rows, args.final)
    path = RESULTS / args.label / f"{args.mode}.jsonl"
    done = read_results(path)
    todo = [r for r in todo_rows if r["id"] not in done or done[r["id"]]["error"]]

    per_question, basis = requests_per_question(args.mode)
    planned = round(len(todo) * per_question)
    limit = pipeline.config()["limits"]["requests_per_day"]
    today = pipeline.requests_today()
    print(f"{args.mode}: {len(todo)} of {len(todo_rows)} questions to run, about {planned} requests ({basis}).")
    print(f"Requests logged today: {today} of {limit}. Results: {path.relative_to(ROOT)}")
    if today + planned > limit:
        print("This will not finish today on one key. It will stop at the limit; run it again after midnight Pacific.")
    if args.dry_run:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    session = f"{args.label}-{args.mode}"
    by_id = {r["id"]: r for r in rows}
    with open(path, "a", encoding="utf-8") as out:
        for n, row in enumerate(todo, 1):
            # Each question starts a new session, except a follow-up, which continues its parent's.
            history = []
            parent = row["follow_up_of"]
            if parent:
                earlier = done.get(parent)
                if not earlier or earlier["error"]:
                    print(f"{row['id']}: skipped, its first question {parent} has no answer yet")
                    continue
                history = [earlier]
            record = pipeline.answer(row["question"], history, args.mode, session, run=args.label)
            record.update(question_id=row["id"], split=row["split"], type=row["type"])
            if record["quota_exhausted"]:
                print(f"\nStopped at {row['id']}: {record['error']}\nRun the same command to continue.")
                sys.exit(2)
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            done[row["id"]] = record
            state = "ERROR " + record["error"] if record["error"] else f"{record['latency_s']} s, {record['requests']} req"
            print(f"[{n}/{len(todo)}] {row['id']} {by_id[row['id']]['type']}: {state}", flush=True)

    failed = [q for q, r in read_results(path).items() if r["error"]]
    print(f"Finished. {len(failed)} with errors{': ' + ', '.join(failed) + ' (run again to retry)' if failed else ''}.")


if __name__ == "__main__":
    main()
