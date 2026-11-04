"""One-request smoke test: can an unmodified `claude -p` be pointed at the capture proxy and driven
non-interactively? Spends a fraction of a cent. The real key stays in this process; Claude Code gets a dummy."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from mini_sclate.capture_proxy import CaptureProxy, SpendLedger
from mini_sclate.run import load_env

CAP_USD = 2.0
LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spend_ledger.json")


def main() -> int:
    load_env()
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("ANTHROPIC_API_KEY missing (put it in .env)")
        return 2
    claude = shutil.which("claude")
    ledger = SpendLedger(LEDGER, CAP_USD)
    proxy = CaptureProxy(key, ledger)
    port = proxy.start()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC", "CLAUDE"))}
    env.update(ANTHROPIC_BASE_URL=f"http://127.0.0.1:{port}", ANTHROPIC_API_KEY="dummy-not-a-real-key")
    cmd = [claude, "-p", "--bare", "--model", "claude-haiku-5-5", "--tools", "", "--no-session-persistence",
           "--output-format", "json", "--max-budget-usd", "0.05", "Reply with exactly the single word: PONG"]
    with tempfile.TemporaryDirectory() as cwd:
        try:
            r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            print("TIMEOUT")
            proxy.stop()
            return 3
    proxy.stop()
    print("exit code:", r.returncode)
    print("stdout:", r.stdout[:1500])
    print("stderr:", r.stderr[:800])
    print("proxy saw", len(proxy.calls), "metered call(s):")
    for c in proxy.calls:
        print(" ", json.dumps(c))
    print(f"lifetime ledger: ${ledger.total:.6f} of ${ledger.cap:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
