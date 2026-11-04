"""Every model call goes through the proxy, which records usage on the simulated timeline.
Models may expose `last_usage = {"input": n, "output": n}`; otherwise word counts are used."""
import json
import os
import re
import time
import urllib.error
import urllib.request

from .extract_memory import CONSOLIDATE_SYSTEM, EXTRACT_SYSTEM


HARD_SYSTEM = ("You answer from the notes above the final 'Q:' line. They are sentences told to you in order; "
               "if a fact was set more than once, the latest sentence is correct. Different people and different "
               "attributes are different facts, so match both. Reply with only the 4-digit number, or 'unknown'.")


class MockModel:
    """Deterministic stand-in for an LLM: answers 'Q: <key>' from the last '<key> is <value>' line in context."""

    def complete(self, prompt: str, system: str | None = None) -> str:
        lines = prompt.splitlines()
        question = lines[-1].removeprefix("Q: ").strip()
        if system == CONSOLIDATE_SYSTEM:  # offline stand-in: canonical attribute by keyword, newest value wins
            keep: dict = {}
            for line in prompt.splitlines()[1:]:
                parts = [x.strip() for x in line.split("|")]
                if len(parts) != 3:
                    continue
                a = parts[1].lower()
                attr = next((v for k, v in (("locker", "gym locker code"), ("park", "parking space"),
                                            ("badge", "badge number"), ("ext", "phone extension"),
                                            ("phone", "phone extension")) if k in a), a)
                keep.pop((parts[0].lower(), attr), None)
                keep[(parts[0].lower(), attr)] = f"{parts[0].title()} | {attr} | {parts[2]}"
            return chr(10).join(keep.values())
        if system == EXTRACT_SYSTEM:  # offline stand-in: keyword rules, only for exercising the pipeline
            s = prompt.removeprefix("Sentence: ")
            attr = next((a for k, a in (("locker", "gym locker code"), ("park", "parking space"),
                                        ("badge", "badge number"), ("extension", "phone extension")) if k in s), "")
            nums = re.findall(r"\d{4}", s)
            return f"{s.split()[0].removesuffix(chr(39) + 's')} | {attr} | {nums[-1]}" if attr and nums else s
        if system == HARD_SYSTEM:  # offline stand-in for hard mode: value in the best word-overlap sentence
            q = {t for t in re.findall(r"[a-z]+", question.lower()) if len(t) > 2}
            best, answer = 0, "unknown"
            for line in lines[:-1]:
                nums = re.findall(r"\d{4}", line)
                score = len(q & set(re.findall(r"[a-z]+", line.lower())))
                if nums and score and score >= best:
                    best, answer = score, nums[-1]
            return answer
        answer = "unknown"
        for line in lines[:-1]:
            m = re.fullmatch(r"(.+?) is (.+)", line.strip())
            if m and m.group(1) == question:
                answer = m.group(2)  # later lines win
        return answer


class AnthropicModel:
    """Messages API client using only the standard library. NOT run in this repo's tests against the live API:
    it needs ANTHROPIC_API_KEY. The request/response handling is covered with an injected stub."""
    SYSTEM = ("You answer from the notes above the final 'Q:' line, where each note reads '<key> is <value>'. "
              "If a key appears more than once, use the last one. Reply with only the value, or 'unknown'.")

    def __init__(self, model: str = "claude-haiku-5-5", api_key: str | None = None, post=None):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._post = post or self._http_post
        self.last_usage: dict = {}
        if post is None and not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")

    def _http_post(self, body: dict) -> dict:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())

    def complete(self, prompt: str, system: str | None = None) -> str:
        resp = self._post({"model": self.model, "max_tokens": 64, "system": system or self.SYSTEM,
                           "messages": [{"role": "user", "content": prompt}]})
        usage = resp.get("usage", {})
        self.last_usage = {"input": usage.get("input_tokens", 0), "output": usage.get("output_tokens", 0)}
        return "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text").strip()


class GroqModel:
    """Groq's OpenAI-compatible chat completions endpoint, standard library only. Reads GROQ_API_KEY.
    Waits and retries on HTTP 429 (free-tier rate limits). Parsing is covered with an injected stub."""
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, model: str = "openai/gpt-oss-20b", api_key: str | None = None, post=None,
                 max_429_retries: int = 6, max_tokens: int = 1024):
        self.model = model
        self.max_tokens = max_tokens
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self._post = post or self._http_post
        self.max_429_retries = max_429_retries
        self.last_usage: dict = {}
        if post is None and not self.api_key:
            raise RuntimeError("GROQ_API_KEY is not set")

    def _http_post(self, body: dict) -> dict:
        for attempt in range(self.max_429_retries + 1):
            req = urllib.request.Request(
                self.URL, data=json.dumps(body).encode(),
                headers={"Authorization": f"Bearer {self.api_key}", "content-type": "application/json",
                         "user-agent": "mini-sclate/0.1"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == self.max_429_retries:
                    raise
                time.sleep(min(float(e.headers.get("retry-after") or 2 ** attempt), 30))

    def complete(self, prompt: str, system: str | None = None) -> str:
        resp = self._post({"model": self.model, "temperature": 0, "max_tokens": self.max_tokens,
                           "reasoning_effort": "low",
                           "messages": [{"role": "system", "content": system or AnthropicModel.SYSTEM},
                                        {"role": "user", "content": prompt}]})
        usage = resp.get("usage", {})
        self.last_usage = {"input": usage.get("prompt_tokens", 0), "output": usage.get("completion_tokens", 0)}
        return resp["choices"][0]["message"]["content"].strip()


class ModelProxy:
    def __init__(self, model, clock, tag: str = "", log_path: str | None = None):
        self.model = model
        self.clock = clock
        self.tag = tag
        self.log_path = log_path
        self.calls: list[dict] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        out = self.model.complete(prompt) if system is None else self.model.complete(prompt, system=system)
        usage = getattr(self.model, "last_usage", None) or {}
        rec = {
            "tag": self.tag,
            "sim_time": round(self.clock.now(), 3),
            "tokens_in": usage.get("input", len(prompt.split())),
            "tokens_out": usage.get("output", len(out.split())),
        }
        self.calls.append(rec)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        return out

    def tokens_in(self) -> int:
        return sum(c["tokens_in"] for c in self.calls)
