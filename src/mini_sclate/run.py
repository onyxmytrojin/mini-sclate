"""Run memory configs on the same scenario and print/write a comparison."""
import argparse
import os
import tempfile

from .agent import AgentAdapter
from .benchmark import RecallBenchmark
from .clock import HybridClock
from .memory import CONFIGS, HARD_CONFIGS
from .proxy import HARD_SYSTEM, AnthropicModel, GroqModel, MockModel, ModelProxy
from .scheduler import Scheduler
from .store import Store


def load_env(path: str = ".env") -> None:
    """Minimal .env reader: KEY=value lines. Real environment variables win over the file."""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def run_config(name: str, days: int = 30, seed: int = 0, flaky: float = 0.0, db: str = ":memory:",
               log_path: str | None = None, model=None, mode: str = "daily") -> dict:
    registry = Store(db)       # scheduler's fire registry
    mem_store = Store()        # the agent process's in-memory state; wiped at every ShutdownAgent
    clock = HybridClock()
    proxy = ModelProxy(model or MockModel(), clock, tag=name, log_path=log_path)
    with tempfile.TemporaryDirectory() as state_dir:
        cfgs = HARD_CONFIGS if mode == "hard" else CONFIGS
        agent = AgentAdapter(cfgs[name](mem_store), proxy, days, state_dir, flaky=flaky, seed=seed,
                             system=HARD_SYSTEM if mode == "hard" else None)
        bench = RecallBenchmark(agent, days, seed=seed, mode=mode)
        sched = Scheduler(registry, clock)
        sched.register(agent)
        sched.register(bench)
        for s in agent.sources() + bench.sources():
            sched.add_source(s)
        sched.run()
        snapshot_lines = []
        if os.path.exists(agent.snapshot_path):
            import json
            snapshot_lines = json.loads(json.load(open(agent.snapshot_path, encoding="utf-8"))["payload"])["notes"]
    details = {"graded": {q: {"expected": e, "got": g} for q, (e, g) in bench.graded.items()},
               "asks": {qid: key for qid, _, _, key in bench.asks}, "memory_lines": snapshot_lines}
    counts = registry.counts()
    wall = max(clock.wall_elapsed(), 1e-9)
    late_p50, late_max = sched.lateness_stats()
    return {
        "config": name, "details": details,
        "accuracy": bench.accuracy(),
        "probe_acc": bench.probe_accuracy(),
        "probes": f"{bench.probes_asked()}/{len(bench.probes)}",
        "model_calls": len(proxy.calls),
        "tokens_in": proxy.tokens_in(),
        "retries": sched.retries,
        "first_error": sched.first_error,
        "dead": counts.get("dead", 0),
        "late_p50": late_p50,
        "late_max": late_max,
        "sim_days": clock.sim_elapsed() / 86400,
        "wall_s": wall,
        "speedup": clock.sim_elapsed() / wall,
    }


def render(rows: list[dict], days: int, seed: int, flaky: float, model: str, mode: str) -> str:
    out = [f"Scenario: {mode} mode, {days} simulated days, seed {seed}, flaky cron rate {flaky}, model {model}", "",
           "| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead "
           "| lateness p50/max (s) | sim days | wall s | speedup |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['config']} | {r['accuracy']:.2f} | {r['probe_acc']:.2f} | {r['probes']} | {r['model_calls']} "
                   f"| {r['tokens_in']} | {r['retries']} | {r['dead']} | {r['late_p50']:.2f}/{r['late_max']:.1f} "
                   f"| {r['sim_days']:.1f} | {r['wall_s']:.2f} | {r['speedup']:,.0f}x |")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--flaky", type=float, default=0.0)
    ap.add_argument("--mode", choices=["daily", "history", "hard"], default="daily")
    ap.add_argument("--configs", default=None, help="comma-separated subset of: " + ", ".join(CONFIGS))
    ap.add_argument("--model", choices=["mock", "anthropic", "groq", "claudecode"], default="mock")
    ap.add_argument("--model-id", default=None, help="default: claude-haiku-5-5 (anthropic), openai/gpt-oss-20b (groq)")
    ap.add_argument("--max-tokens", type=int, default=1024, help="output budget per call for --model groq (reasoning tokens count)")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    if a.configs is None:
        a.configs = ",".join(HARD_CONFIGS if a.mode == "hard" else CONFIGS)
    load_env()
    os.makedirs(a.out, exist_ok=True)
    log = os.path.join(a.out, "calls.jsonl")
    if os.path.exists(log):
        os.remove(log)
    defaults = {"claudecode": "claude-haiku-5-5 via Claude Code", "anthropic": "claude-haiku-5-5", "groq": "openai/gpt-oss-20b"}
    model_id = a.model_id or defaults.get(a.model, "mock")

    def make_model():
        if a.model == "anthropic":
            return AnthropicModel(model_id)
        if a.model == "groq":
            return GroqModel(model_id, max_tokens=a.max_tokens)
        if a.model == "claudecode":
            from .claude_code_model import ClaudeCodeModel
            return ClaudeCodeModel("spend_ledger.json", 2.0, log_path=os.path.join(a.out, "proxy-calls.jsonl"))
        return MockModel()

    rows = [run_config(n, a.days, a.seed, a.flaky, log_path=log, model=make_model(), mode=a.mode)
            for n in a.configs.split(",")]
    import json
    for r in rows:
        with open(os.path.join(a.out, f"details-{r['config']}.json"), "w", encoding="utf-8") as f:
            json.dump(r["details"], f, indent=1)
    text = render(rows, a.days, a.seed, a.flaky, model_id, a.mode)
    errs = [r["first_error"] for r in rows if r["first_error"]]
    if errs and a.flaky == 0.0:
        text += "\n\nWARNING: fires failed without fault injection. First error: " + errs[0]
    print(text)
    with open(os.path.join(a.out, "report.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
