"""Capture proxy with a hard spend cap, for pointing an unmodified agent harness (Claude Code) at the API.

The paper's capture proxy records every model call a harness makes. This one does that for Anthropic's Messages
API and adds three safety properties:
- it holds the real API key; the harness is given a dummy key, so the real one never enters its environment
- every request is pinned to one cheap model, because harnesses also make background calls on other models
- a persistent ledger caps lifetime spend; a request whose worst-case cost would cross the cap is refused

Costs are computed from the usage reported in the responses. The cache price multipliers below are assumptions
(I could not confirm Haiku 5.5's cache prices), set conservatively so the ledger over-counts rather than under-counts."""
import http.client
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PRICES = {  # USD per million tokens; from the model reference dated 2026-10-06. Re-check before relying on it.
    "claude-haiku-5-5": {"in": 0.10, "out": 0.50, "in_long": 0.50, "out_long": 2.50, "long_over": 100_000},
}
CACHE_WRITE_X, CACHE_READ_X = 1.25, 0.10
ALLOWED_PREFIXES = ("/v1/messages", "/v1/models")


def cost_usd(model: str, usage: dict) -> float:
    p = PRICES[model]
    fresh = usage.get("input_tokens", 0)
    c_write = usage.get("cache_creation_input_tokens", 0)
    c_read = usage.get("cache_read_input_tokens", 0)
    out = usage.get("output_tokens", 0)
    long = (fresh + c_write + c_read) > p["long_over"]
    i, o = (p["in_long"], p["out_long"]) if long else (p["in"], p["out"])
    return (fresh * i + c_write * i * CACHE_WRITE_X + c_read * i * CACHE_READ_X + out * o) / 1e6


class SpendLedger:
    """Lifetime spend, persisted to a JSON file so the cap holds across runs."""

    def __init__(self, path: str, cap_usd: float):
        self.path, self.cap = path, cap_usd
        self.lock = threading.Lock()
        try:
            with open(path, encoding="utf-8") as f:
                self.total = float(json.load(f)["total_usd"])
        except (OSError, ValueError, KeyError):
            self.total = 0.0

    def would_exceed(self, extra: float) -> bool:
        with self.lock:
            return self.total + extra > self.cap

    def add(self, amount: float) -> float:
        with self.lock:
            self.total += amount
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"total_usd": round(self.total, 6), "cap_usd": self.cap}, f)
            return self.total


def parse_sse_usage(raw: bytes) -> tuple[dict, bool]:
    """Returns (merged usage, saw_final_delta). message_start carries input/cache usage, message_delta the output."""
    usage, final = {}, False
    for line in raw.decode("utf-8", "replace").splitlines():
        if not line.startswith("data:"):
            continue
        try:
            ev = json.loads(line[5:].strip())
        except ValueError:
            continue
        if ev.get("type") == "message_start":
            usage.update(ev.get("message", {}).get("usage", {}))
        elif ev.get("type") == "message_delta":
            usage.update(ev.get("usage", {}))
            final = True
    return usage, final


class CaptureProxy:
    def __init__(self, api_key: str, ledger: SpendLedger, model: str = "claude-haiku-5-5",
                 upstream: tuple[str, int, bool] = ("api.anthropic.com", 443, True), clock_now=None,
                 log_path: str | None = None):
        if model not in PRICES:
            raise ValueError(f"no price known for {model}")
        self.api_key, self.ledger, self.model = api_key, ledger, model
        self.upstream = upstream
        self.clock_now = clock_now or (lambda: 0.0)
        self.log_path = log_path
        self.calls: list[dict] = []
        self.capped = False
        self.server = None

    def start(self) -> int:
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):  # keep stdout clean
                pass

            def _reply(self, status: int, payload: dict):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.send_header("connection", "close")
                self.end_headers()
                self.wfile.write(body)
                self.close_connection = True

            def _handle(self):
                n = int(self.headers.get("content-length") or 0)
                body = self.rfile.read(n) if n else b""
                path = self.path.split("?")[0]
                if not path.startswith(ALLOWED_PREFIXES):
                    return self._reply(404, {"type": "error", "error": {"type": "not_found_error",
                                                                          "message": "path not allowed by capture proxy"}})
                metered = path == "/v1/messages" and self.command == "POST"
                max_tokens = 0
                if metered:
                    try:
                        req = json.loads(body)
                    except ValueError:
                        return self._reply(400, {"type": "error", "error": {"type": "invalid_request_error",
                                                                              "message": "bad json"}})
                    req["model"] = proxy.model
                    max_tokens = int(req.get("max_tokens", 4096))
                    body = json.dumps(req).encode()
                    p = PRICES[proxy.model]
                    worst = (len(body) / 3 * p["in"] * CACHE_WRITE_X + max_tokens * p["out"]) / 1e6
                    if proxy.ledger.would_exceed(worst):
                        proxy.capped = True
                        return self._reply(400, {"type": "error", "error": {
                            "type": "invalid_request_error",
                            "message": f"mini-sclate spend cap reached (${proxy.ledger.total:.4f} of "
                                       f"${proxy.ledger.cap:.2f}); request refused"}})
                headers = {"x-api-key": proxy.api_key, "accept-encoding": "identity",
                           "anthropic-version": self.headers.get("anthropic-version", "2023-06-01"),
                           "content-type": "application/json", "content-length": str(len(body))}
                if self.headers.get("anthropic-beta"):
                    headers["anthropic-beta"] = self.headers["anthropic-beta"]
                host, port, tls = proxy.upstream
                conn = (http.client.HTTPSConnection if tls else http.client.HTTPConnection)(host, port, timeout=300)
                try:
                    conn.request(self.command, self.path, body=body or None, headers=headers)
                    resp = conn.getresponse()
                    self.send_response(resp.status)
                    self.send_header("content-type", resp.getheader("content-type", "application/json"))
                    self.send_header("connection", "close")
                    self.end_headers()
                    raw = b""
                    while True:
                        chunk = resp.read1(4096) if hasattr(resp, "read1") else resp.read(4096)
                        if not chunk:
                            break
                        raw += chunk
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    status = resp.status
                except (BrokenPipeError, ConnectionResetError):
                    status, raw = 499, locals().get("raw", b"")
                finally:
                    conn.close()
                    self.close_connection = True
                if metered:
                    proxy._meter(status, raw, max_tokens)

            do_GET = do_POST = do_DELETE = do_PUT = _handle

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self.server.server_address[1]

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def _meter(self, status: int, raw: bytes, max_tokens: int) -> None:
        usage, complete = {}, True
        if status == 200:
            if raw.lstrip().startswith(b"event:") or b"\ndata:" in raw or raw.startswith(b"data:"):
                usage, complete = parse_sse_usage(raw)
            else:
                try:
                    usage = json.loads(raw).get("usage", {})
                except ValueError:
                    usage = {}
            if not complete or not usage:
                usage["output_tokens"] = max(usage.get("output_tokens", 0), max_tokens)  # interrupted: charge worst case
        cost = cost_usd(self.model, usage) if usage else 0.0
        total = self.ledger.add(cost) if cost else self.ledger.total
        rec = {"wall": round(time.time(), 3), "sim_time": round(self.clock_now(), 3), "status": status,
               "model": self.model, "usage": usage, "cost_usd": round(cost, 6), "ledger_usd": round(total, 6)}
        self.calls.append(rec)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
