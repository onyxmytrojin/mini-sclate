import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mini_sclate.capture_proxy import CaptureProxy, SpendLedger, cost_usd, parse_sse_usage

SSE = (b'event: message_start\ndata: {"type":"message_start","message":{"usage":{"input_tokens":1000,'
       b'"cache_read_input_tokens":4000,"output_tokens":1}}}\n\n'
       b'event: message_delta\ndata: {"type":"message_delta","usage":{"output_tokens":50}}\n\n')


class FakeUpstream:
    """Stands in for api.anthropic.com. Records what it was sent."""

    def __init__(self, stream=True):
        self.seen = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["content-length"])))
                outer.seen.append({"key": self.headers.get("x-api-key"), "model": body["model"], "path": self.path})
                if body.get("stream"):
                    out, ctype = SSE, "text/event-stream"
                else:
                    out = json.dumps({"content": [{"type": "text", "text": "hi"}],
                                      "usage": {"input_tokens": 200, "output_tokens": 10}}).encode()
                    ctype = "application/json"
                self.send_response(200)
                self.send_header("content-type", ctype)
                self.send_header("content-length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def post(port, payload, path="/v1/messages"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(payload).encode(),
                                 headers={"content-type": "application/json", "x-api-key": "dummy"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class CostTests(unittest.TestCase):
    def test_haiku_cost(self):
        # 50K fresh input at $0.10/M = $0.005, plus 10K output at $0.50/M = $0.005
        self.assertAlmostEqual(cost_usd("claude-haiku-5-5", {"input_tokens": 50_000, "output_tokens": 10_000}), 0.01)

    def test_long_prompt_uses_higher_rate(self):
        c = cost_usd("claude-haiku-5-5", {"input_tokens": 200_000, "output_tokens": 0})
        self.assertAlmostEqual(c, 0.10)  # 200K * $0.50/M

    def test_cache_multipliers_are_conservative(self):
        base = cost_usd("claude-haiku-5-5", {"input_tokens": 1000})
        self.assertGreater(cost_usd("claude-haiku-5-5", {"cache_creation_input_tokens": 1000}), base)
        self.assertLess(cost_usd("claude-haiku-5-5", {"cache_read_input_tokens": 1000}), base)

    def test_sse_usage_parsing(self):
        usage, final = parse_sse_usage(SSE)
        self.assertTrue(final)
        self.assertEqual((usage["input_tokens"], usage["cache_read_input_tokens"], usage["output_tokens"]),
                         (1000, 4000, 50))


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.up = FakeUpstream()
        self.ledger = SpendLedger(os.path.join(self.tmp.name, "ledger.json"), cap_usd=1.0)
        self.proxy = CaptureProxy("REAL-KEY", self.ledger, upstream=("127.0.0.1", self.up.port, False))
        self.port = self.proxy.start()

    def tearDown(self):
        self.proxy.stop()
        self.up.stop()
        self.tmp.cleanup()

    def test_swaps_key_pins_model_and_meters_non_streaming(self):
        status, _ = post(self.port, {"model": "claude-opus-5-5", "max_tokens": 100, "messages": []})
        self.assertEqual(status, 200)
        self.assertEqual(self.up.seen[0]["key"], "REAL-KEY")
        self.assertEqual(self.up.seen[0]["model"], "claude-haiku-5-5")
        self.assertEqual(self.proxy.calls[0]["usage"]["output_tokens"], 10)
        self.assertGreater(self.ledger.total, 0)

    def test_meters_streaming(self):
        status, body = post(self.port, {"model": "x", "max_tokens": 100, "stream": True, "messages": []})
        self.assertEqual(status, 200)
        self.assertIn(b"message_delta", body)  # stream passed through to the client
        u = self.proxy.calls[0]["usage"]
        self.assertEqual((u["input_tokens"], u["cache_read_input_tokens"], u["output_tokens"]), (1000, 4000, 50))

    def test_paths_outside_allowlist_are_blocked(self):
        status, _ = post(self.port, {}, path="/api/event_logging/batch")
        self.assertEqual(status, 404)
        self.assertEqual(self.up.seen, [])

    def test_cap_refuses_before_forwarding(self):
        self.ledger.add(0.999999)  # essentially at the cap
        status, body = post(self.port, {"model": "x", "max_tokens": 1000, "messages": []})
        self.assertEqual(status, 400)
        self.assertIn(b"spend cap", body)
        self.assertTrue(self.proxy.capped)
        self.assertEqual(self.up.seen, [])  # never reached the upstream

    def test_ledger_persists_across_instances(self):
        post(self.port, {"model": "x", "max_tokens": 100, "messages": []})
        total = self.ledger.total
        again = SpendLedger(self.ledger.path, cap_usd=1.0)
        self.assertAlmostEqual(again.total, total, places=6)


if __name__ == "__main__":
    unittest.main()
