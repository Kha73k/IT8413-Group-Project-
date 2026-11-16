"""Web application: serves the page and the JSON API on this computer only.

    python app.py     ->  http://localhost:8000

Put your Gemini API key in the GEMINI_API_KEY environment variable or on the first line of
api.txt (git-ignored). See README.md.
"""
import http.server
import json
import threading
import urllib.parse
import uuid
from pathlib import Path

import analytics
import llm
import pipeline

ROOT = Path(__file__).resolve().parent
MAX_BODY, MAX_QUESTION = 256_000, 1000
# Only these files are served. The project folder also holds api.txt, so it must never be served as a directory.
STATIC = {"/": ("index.html", "text/html; charset=utf-8")}

_sessions, _sessions_lock = {}, threading.Lock()


def session_turns(session_id):
    with _sessions_lock:
        return list(_sessions.get(session_id, []))


def api_config():
    cfg = pipeline.config()
    return {"model": cfg["model"], "limits": cfg["limits"], "pricing": cfg["pricing"], "notes": cfg["notes"],
            "versions": {"v1": pipeline.settings("v1"), "v2": pipeline.settings("v2")},
            "varied": pipeline.varied_setting(), "requests_today": pipeline.requests_today(),
            "key_configured": _key_configured()}


def _key_configured():
    try:
        llm.api_key()
        return True
    except llm.LLMError:
        return False


def api_ask(body):
    question = str(body.get("question", "")).strip()
    mode = body.get("mode", "v1")
    if not question or len(question) > MAX_QUESTION:
        raise ValueError(f"question must be 1 to {MAX_QUESTION} characters")
    if mode not in pipeline.MODES:
        raise ValueError("unknown mode")
    if mode == "v2" and not pipeline.varied_setting()["changed"]:
        raise ValueError("v2 is not defined yet: it is set after the v1 failure analysis")
    session_id = str(body.get("session_id") or uuid.uuid4().hex)[:64]
    record = pipeline.answer(question, session_turns(session_id), mode, session_id, run="app")
    if record["answer"]:
        with _sessions_lock:
            _sessions.setdefault(session_id, []).append(record)
    return record


class Handler(http.server.BaseHTTPRequestHandler):
    def send(self, body, status=200, ctype="application/json; charset=utf-8", filename=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(url.query)
        try:
            if url.path in STATIC:
                name, ctype = STATIC[url.path]
                return self.send((ROOT / name).read_bytes(), ctype=ctype)
            if url.path == "/api/options":
                return self.send(analytics.options())
            if url.path == "/api/config":
                return self.send(api_config())
            if url.path == "/api/log":
                return self.send(pipeline.read_log(int(query.get("limit", ["200"])[0])))
            if url.path == "/api/log/download":
                data = pipeline.LOG.read_bytes() if pipeline.LOG.exists() else b""
                return self.send(data, ctype="application/x-ndjson", filename="query_log.jsonl")
            self.send({"error": "not found"}, 404)
        except (ValueError, KeyError) as e:
            self.send({"error": str(e)}, 400)
        except Exception as e:  # as in do_POST: report the reason, do not drop the connection
            self.send({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_POST(self):
        # A web page on another site cannot send application/json here without a preflight this server refuses.
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self.send({"error": "send application/json"}, 415)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 <= length <= MAX_BODY:
                return self.send({"error": "request too large"}, 413)
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("send a JSON object")
            if self.path == "/api/dashboard":
                return self.send(analytics.dashboard(body.get("filters")))
            if self.path == "/api/ask":
                return self.send(api_ask(body))
            if self.path == "/api/report":
                turns = session_turns(str(body.get("session_id", "")))
                page = analytics.report_html(body.get("filters"), turns)
                return self.send(page.encode(), ctype="text/html; charset=utf-8", filename="area_profile.html")
            self.send({"error": "not found"}, 404)
        except ValueError as e:
            self.send({"error": str(e)}, 400)
        except Exception as e:  # keep the demo alive and show the reason in the page
            self.send({"error": f"{type(e).__name__}: {e}"}, 500)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("http://localhost:8000  (Ctrl+C to stop)")
    if not _key_configured():
        print("note: no Gemini API key found. The dashboard works; the Ask tab needs a key (see README.md).")
    http.server.ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
