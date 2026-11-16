"""Gemini API client: one request at a time, paced under the free-tier limits.

The key is read from the GEMINI_API_KEY environment variable, or else the first line of
api.txt (git-ignored). It is never logged or printed.

Free-tier limits are not guaranteed by Google, so they live in config.json, not in code.
When a request is refused anyway (HTTP 429), the client waits as long as the API says and
retries; when the daily quota is exhausted it stops with QuotaExhausted instead of looping.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class QuotaExhausted(RuntimeError):
    pass


class LLMError(RuntimeError):
    pass


def api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key and (ROOT / "api.txt").exists():
        key = (ROOT / "api.txt").read_text(encoding="utf-8").strip().splitlines()[0].strip()
    if not key:
        raise LLMError("No Gemini API key: set GEMINI_API_KEY or put your key on the first line of api.txt")
    return key


class Limiter:
    """Sliding 60-second window over requests and estimated input tokens."""

    def __init__(self, rpm, tpm):
        self.rpm, self.tpm = rpm, tpm
        self.sent = deque()  # (time, estimated tokens)
        self.lock = threading.Lock()

    def wait(self, tokens):
        with self.lock:
            while True:
                now = time.time()
                while self.sent and now - self.sent[0][0] > 60:
                    self.sent.popleft()
                used = sum(t for _, t in self.sent)
                if len(self.sent) < self.rpm and (not self.sent or used + tokens <= self.tpm):
                    self.sent.append((now, tokens))
                    return
                time.sleep(max(0.5, 60.5 - (now - self.sent[0][0])))


_limiter = None


def generate(model, payload, limits):
    """POST one generateContent request. Returns (response json, seconds, retries)."""
    global _limiter
    if _limiter is None:
        _limiter = Limiter(limits["requests_per_minute"], limits["tokens_per_minute"])
    body = json.dumps(payload).encode()
    # Rough tokens-in, set high on purpose: the baseline measured about 2.4 bytes per token. Real counts
    # come back in usageMetadata.
    estimate = len(body) // 2
    retries = 0
    while True:
        _limiter.wait(estimate)
        req = urllib.request.Request(API.format(model=model), data=body,
                                     headers={"x-goog-api-key": api_key(), "content-type": "application/json"})
        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r), time.time() - start, retries
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code == 429 and "PerDay" in detail:
                raise QuotaExhausted("Daily Gemini free-tier quota used up for this API key. "
                                     "It resets at midnight Pacific time.") from None
            if e.code in (429, 500, 503) and retries < limits["max_retries"]:
                retries += 1
                time.sleep(_retry_delay(detail, retries))
                continue
            raise LLMError(f"Gemini API error {e.code}: {detail[:300]}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if retries < limits["max_retries"]:
                retries += 1
                time.sleep(5 * retries)
                continue
            raise LLMError(f"Cannot reach the Gemini API: {e}") from None


def _retry_delay(detail, attempt):
    try:
        for d in json.loads(detail)["error"].get("details", []):
            if "retryDelay" in d:
                return float(d["retryDelay"].rstrip("s")) + 1
    except (ValueError, KeyError, AttributeError):
        pass
    return min(60, 5 * 2 ** attempt)
