"""Agent adapter (paper Table 4, agent side): session lifecycle, message delivery, state save/restore, and the
agent's own event sources (session start/end, nightly memory consolidation).

The agent "process" dies at ShutdownAgent: working context and in-process memory are wiped. Durable memory lives
only in the snapshot written by SaveState and reloaded by RestoreState."""
import os
import random

from .events import (DELIVER, RESTORE_STATE, RUN_HOOK, SAVE_STATE, SHUTDOWN_AGENT, START_AGENT, Effect, Fire,
                     ScheduledSource)
from .snapshot import restore_state, save_state

DAY = 86400
SESSION_START, SESSION_STOP, CRON = 9 * 3600, 17 * 3600, 23 * 3600


def start_id(d): return f"agent:start:{d}"
def stop_id(d): return f"agent:stop:{d}"
def cron_id(d): return f"agent:cron:{d}"


class AgentAdapter:
    name = "agent"

    def __init__(self, memory, proxy, days: int, state_dir: str, flaky: float = 0.0, seed: int = 0,
                 context_limit: int = 20, system: str | None = None):
        self.system = system
        self.memory = memory
        if hasattr(memory, "attach"):
            memory.attach(proxy)  # memories that make their own model calls
        self.proxy = proxy
        self.days = days
        self.snapshot_path = os.path.join(state_dir, "memory-state.json")
        self.flaky = flaky
        self.rng = random.Random(seed + 1)
        self.context_limit = context_limit
        self.context: list[str] = []  # working memory, lost at shutdown
        self.reactions: dict[str, str] = {}  # qid -> the agent's reply (the paper's drain())
        self.active = False
        self.cron_runs = 0

    def sources(self) -> list:
        A = "agent"
        starts = [Fire(d * DAY + SESSION_START, start_id(d), "agent.sessions",
                       [Effect(A, START_AGENT), Effect(A, RESTORE_STATE)]) for d in range(self.days)]
        stops = [Fire(d * DAY + SESSION_STOP, stop_id(d), "agent.sessions",
                      [Effect(A, SAVE_STATE), Effect(A, SHUTDOWN_AGENT)]) for d in range(self.days)]
        crons = [Fire(d * DAY + CRON, cron_id(d), "agent.cron",
                      [Effect(A, RESTORE_STATE), Effect(A, RUN_HOOK, {"hook": "consolidate"}),
                       Effect(A, SAVE_STATE), Effect(A, SHUTDOWN_AGENT)]) for d in range(self.days)]
        return [ScheduledSource("agent.sessions", starts + stops), ScheduledSource("agent.cron", crons)]

    def apply(self, eff, sched) -> None:
        k = eff.kind
        if k == START_AGENT:
            self.active = True
        elif k == RESTORE_STATE:
            restore_state(self.memory.store, self.snapshot_path)
        elif k == SAVE_STATE:
            save_state(self.memory.store, self.snapshot_path)
        elif k == SHUTDOWN_AGENT:
            self.active = False
            self.context.clear()
            self.memory.store.wipe_memory()
        elif k == RUN_HOOK and eff.payload["hook"] == "consolidate":
            if self.rng.random() < self.flaky:
                raise RuntimeError("injected consolidation failure")
            self.memory.consolidate()
            self.cron_runs += 1
        elif k == DELIVER:
            self._require_session()
            p = eff.payload
            if "text" in p:
                self.context.append(p["text"])
                self.memory.observe(p["text"])
            else:
                self.reactions[p["qid"]] = self._answer(p["key"], sched.clock.now())
                sched.agent_actions[f"answered:{p['qid']}"] = sched.clock.now()

    def _answer(self, key: str, now: float) -> str:
        date = f"Date: day {int(now // DAY) + 1}"  # simulated date reaches the prompt (paper Fig. 8)
        lines = [date] + self.context[-self.context_limit:] + self.memory.recall(key)
        return self.proxy.complete("\n".join(lines + [f"Q: {key}"]), self.system)

    def _require_session(self) -> None:
        if not self.active:
            raise RuntimeError("no active session")
