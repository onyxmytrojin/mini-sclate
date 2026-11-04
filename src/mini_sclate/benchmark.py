"""Multi-session recall benchmark adapter (paper Table 4, benchmark side). Facts are told across days, some
facts change value, and the latest told value is the expected answer. Grading is an independent step: a
GradingSource (AgentActionGatedSource) fires once the agent has answered, then a RunHook compares reply to truth,
so the scheduler holds no grading logic.

Two modes:
- "daily": asks during each day's session, plus a post-consolidation probe per night (EventChainSource on the
  cron fire; it never runs if that cron is dead-lettered).
- "history": the protocol the paper uses to convert LongMemEval/PersonaMem. History is split into sessions on
  consecutive simulated days, the agent process stops between sessions, and every question is asked in the last
  session, so earlier facts must be carried by memory. The facts here are synthetic, not those datasets."""
import random

from .agent import DAY, SESSION_START, cron_id
from .events import (DELIVER, RUN_HOOK, RESTORE_STATE, SHUTDOWN_AGENT, START_AGENT, AgentActionGatedSource,
                     Effect, EventChainSource, Fire, ScheduledSource)

PEOPLE = ["Maya", "Mia", "Noah", "Nora", "Liam", "Lena", "Owen", "Omar"]
ATTRS = [
    {"tell": ["{p}'s gym locker code is now {v}.", "{p} set the combination on the gym locker to {v}."],
     "ask": ["What combination opens {p}'s gym locker?", "What is {p}'s gym locker code?"]},
    {"tell": ["{p} parks in spot {v}.", "{p} was moved to parking space {v}."],
     "ask": ["Which parking space does {p} use?", "Where does {p} park?"]},
    {"tell": ["{p}'s office badge number is {v}.", "{p} was issued badge {v}."],
     "ask": ["What number is on {p}'s badge?", "What is {p}'s badge ID?"]},
    {"tell": ["{p} can be reached on extension {v}.", "{p}'s desk phone extension changed to {v}."],
     "ask": ["What extension reaches {p}?", "Which phone extension is {p}'s desk on?"]},
]

TELL_AT = SESSION_START + 60
ASK_AT = SESSION_START + 3600
PROBE_DELAY = 600


class RecallBenchmark:
    name = "bench"

    def __init__(self, agent, days: int, seed: int = 0, mode: str = "daily", facts_per_day: int = 4,
                 asks_per_day: int = 3, final_questions: int = 20):
        if mode not in ("daily", "history", "hard"):
            raise ValueError(mode)
        self.agent = agent
        self.days = days
        self.mode = mode
        self.rng = random.Random(seed)
        self.expected: dict[str, str] = {}
        self.graded: dict[str, tuple[str, str]] = {}  # qid -> (expected, got)
        self.tells: list[tuple[int, int, str]] = []  # (day, slot, sentence told to the agent)
        self.asks: list[tuple[str, int, int, str]] = []    # (qid, day, slot, key)
        self.probes: list[tuple[str, int, str]] = []       # (qid, day, key)
        if mode == "hard":
            self._build_hard(facts_per_day, final_questions)
        else:
            self._build(facts_per_day, asks_per_day, final_questions)

    def _build(self, facts_per_day: int, asks_per_day: int, final_questions: int) -> None:
        truth: dict[str, str] = {}
        last_day: dict[str, int] = {}
        for d in range(self.days):
            for i in range(facts_per_day):
                if truth and self.rng.random() < 0.25:
                    key = self.rng.choice(sorted(truth))  # an update to an older fact
                else:
                    key = f"code for item{d}x{i}"
                val = str(self.rng.randint(1000, 9999))
                truth[key], last_day[key] = val, d
                self.tells.append((d, i, f"{key} is {val}"))
            if self.mode == "daily":
                known = sorted(truth)
                for j in range(asks_per_day):
                    key = self.rng.choice(known)
                    qid = f"ask:{d}:{j}"
                    self.expected[qid] = truth[key]
                    self.asks.append((qid, d, j, key))
                pk = self.rng.choice(known)
                self.expected[f"probe:{d}"] = truth[pk]
                self.probes.append((f"probe:{d}", d, pk))
        if self.mode == "history":
            # questions about facts not touched on the final day, so they cannot be answered from that day's context
            pool = sorted(k for k, d in last_day.items() if d < self.days - 1) or sorted(truth)
            keys = self.rng.sample(pool, min(final_questions, len(pool)))
            for j, key in enumerate(keys):
                qid = f"ask:{self.days - 1}:{j}"
                self.expected[qid] = truth[key]
                self.asks.append((qid, self.days - 1, j, key))

    def _build_hard(self, facts_per_day: int, final_questions: int) -> None:
        """Hard mode, history protocol. 8 people with near-identical names x 4 attributes whose values are all
        4-digit numbers. Each fact is told with one of several phrasings and re-set several times over the run;
        questions are paraphrases of how the fact was told, so word overlap with the stored sentence is partial."""
        slots = [(p, a) for p in PEOPLE for a in range(len(ATTRS))]
        truth: dict[tuple, str] = {}
        last_day: dict[tuple, int] = {}
        for d in range(self.days):
            for i in range(facts_per_day):
                slot = self.rng.choice(slots)
                val = str(self.rng.randint(1000, 9999))
                tell = self.rng.choice(ATTRS[slot[1]]["tell"])
                truth[slot], last_day[slot] = val, d
                self.tells.append((d, i, tell.format(p=slot[0], v=val)))
        pool = sorted(k for k, d in last_day.items() if d < self.days - 1) or sorted(truth)
        for j, slot in enumerate(self.rng.sample(pool, min(final_questions, len(pool)))):
            qid = f"ask:{self.days - 1}:{j}"
            self.expected[qid] = truth[slot]
            self.asks.append((qid, self.days - 1, j, self.rng.choice(ATTRS[slot[1]]["ask"]).format(p=slot[0])))

    def sources(self) -> list:
        A, B = "agent", "bench"
        tells = [Fire(d * DAY + TELL_AT + i, f"bench:tell:{d}:{i}", "bench.tasks",
                      [Effect(A, DELIVER, {"text": t})]) for d, i, t in self.tells]
        asks = [Fire(d * DAY + ASK_AT + j, f"bench:{qid}", "bench.tasks",
                     [Effect(A, DELIVER, {"qid": qid, "key": k})]) for qid, d, j, k in self.asks]
        probes = [((cron_id(d),), PROBE_DELAY, f"bench:{qid}",
                   [Effect(A, START_AGENT), Effect(A, RESTORE_STATE),
                    Effect(A, DELIVER, {"qid": qid, "key": k}), Effect(A, SHUTDOWN_AGENT)])
                  for qid, d, k in self.probes]
        grading = [(f"answered:{qid}", 0.0, f"bench:grade:{qid}", [Effect(B, RUN_HOOK, {"hook": "grade", "qid": qid})])
                   for qid in self.expected]
        srcs = [ScheduledSource("bench.tasks", tells + asks), AgentActionGatedSource("bench.grading", grading)]
        if probes:
            srcs.append(EventChainSource("bench.probes", probes))
        return srcs

    def apply(self, eff, sched) -> None:
        if eff.kind == RUN_HOOK and eff.payload["hook"] == "grade":
            qid = eff.payload["qid"]
            self.graded[qid] = (self.expected[qid], self.agent.reactions.get(qid, ""))

    def _acc(self, prefix: str, total: int) -> float:
        got = [e == g.strip().rstrip(".").strip() for q, (e, g) in self.graded.items() if q.startswith(prefix)]
        return sum(got) / total if total else 0.0

    def accuracy(self) -> float:
        return self._acc("ask:", len(self.asks))

    def probe_accuracy(self) -> float:
        return self._acc("probe:", len(self.probes))

    def probes_asked(self) -> int:
        return sum(q.startswith("probe:") for q in self.graded)
