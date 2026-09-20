"""Dashboard server. Stdlib only - no pip install needed.

  set ANTHROPIC_API_KEY=sk-ant-...
  python app.py            ->  http://localhost:8000
"""
import http.server, json, os, urllib.request, urllib.error

MODEL = "claude-sonnet-5"
API_URL = "https://api.anthropic.com/v1/messages"
MAX_ROWS = 400  # rows of filtered data sent to the model


def ask_claude(question, schema, summary, rows):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return "ANTHROPIC_API_KEY is not set. Set it and restart the server."

    truncated = len(rows) > MAX_ROWS
    table = "\n".join(",".join(map(str, r)) for r in rows[:MAX_ROWS])
    prompt = (
        f"You answer questions about a dataset shown on a dashboard.\n\n"
        f"Columns: {schema}\n"
        f"Totals for the current filter selection: {summary}\n"
        f"{'First ' + str(MAX_ROWS) + ' of ' if truncated else ''}{len(rows)} "
        f"currently-filtered rows (CSV):\n{table}\n\n"
        f"Question: {question}\n\n"
        "Answer in at most 4 sentences using only the data above. "
        "Cite the numbers you used. If the data cannot answer it, say so."
    )
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 600,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)["content"][0]["text"]
    except urllib.error.HTTPError as e:
        return f"API error {e.code}: {e.read().decode()[:300]}"
    except Exception as e:
        return f"Request failed: {e}"


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/ask":
            return self.send_error(404)
        try:
            n = int(self.headers.get("content-length", 0))
            if n > 2_000_000:
                raise ValueError("payload too large")
            p = json.loads(self.rfile.read(n))
            question = str(p.get("question", "")).strip()
            if not question:
                raise ValueError("question is required")
            answer = ask_claude(question, p.get("schema", ""),
                                p.get("summary", ""), p.get("rows", []))
        except Exception as e:
            answer = f"Bad request: {e}"
        out = json.dumps({"answer": answer}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("http://localhost:8000  (Ctrl+C to stop)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("note: ANTHROPIC_API_KEY not set - dashboard works, Ask tab won't")
    http.server.ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
