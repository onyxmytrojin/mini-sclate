"""Model backend that runs an unmodified Claude Code (`claude -p --bare`) for every call, through the capture proxy.

Each call is a fresh, tool-less, non-persistent Claude Code process, so the harness holds no memory between calls;
memory lives in the prompt the agent adapter builds, as with the other backends. What this adds over the plain API
client is the real harness around the call: its own system prompt and request format. It does not use the harness's
native memory, tools or multi-turn loop."""
import json
import os
import shutil
import subprocess
import time

from .capture_proxy import CaptureProxy, SpendLedger
from .proxy import AnthropicModel

MODEL = "claude-haiku-5-5"


class ClaudeCodeModel:
    def __init__(self, ledger_path: str, cap_usd: float = 2.0, api_key: str | None = None, log_path: str | None = None,
                 per_call_budget: float = 0.02, timeout: int = 180):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.claude = shutil.which("claude")
        if not self.claude:
            raise RuntimeError("claude CLI not found on PATH")
        self.ledger = SpendLedger(ledger_path, cap_usd)
        self.proxy = CaptureProxy(key, self.ledger, model=MODEL, log_path=log_path)
        self.port = self.proxy.start()
        self.per_call_budget, self.timeout = per_call_budget, timeout
        self.last_usage: dict = {}
        self.cwd = os.path.join(os.path.dirname(os.path.abspath(ledger_path)), ".cc-scratch")
        os.makedirs(self.cwd, exist_ok=True)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC", "CLAUDE"))}
        self.env.update(ANTHROPIC_BASE_URL=f"http://127.0.0.1:{self.port}", ANTHROPIC_API_KEY="dummy-not-a-real-key")

    def complete(self, prompt: str, system: str | None = None) -> str:
        before = len(self.proxy.calls)
        cmd = [self.claude, "-p", "--bare", "--model", MODEL, "--tools", "", "--no-session-persistence",
               "--output-format", "json", "--max-budget-usd", str(self.per_call_budget),
               "--append-system-prompt", system or AnthropicModel.SYSTEM]
        for attempt in range(4):  # a launch can fail transiently on Windows (observed: FileNotFoundError once)
            try:
                os.makedirs(self.cwd, exist_ok=True)
                r = subprocess.run(cmd, input=prompt, cwd=self.cwd, env=self.env, capture_output=True, text=True,
                                   timeout=self.timeout, encoding="utf-8")
                break
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(3)
        new = self.proxy.calls[before:]
        self.last_usage = {"input": sum(c["usage"].get("input_tokens", 0) + c["usage"].get("cache_creation_input_tokens", 0)
                                        + c["usage"].get("cache_read_input_tokens", 0) for c in new),
                           "output": sum(c["usage"].get("output_tokens", 0) for c in new)}
        try:
            out = json.loads(r.stdout)
        except ValueError:
            raise RuntimeError(f"claude exit {r.returncode}: {(r.stdout or r.stderr)[:300]}")
        if out.get("is_error"):
            raise RuntimeError(f"claude error: {str(out.get('result'))[:300]}")
        return str(out.get("result", "")).strip()

    def stop(self) -> None:
        self.proxy.stop()
