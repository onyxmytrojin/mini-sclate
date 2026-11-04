"""Open event scheduler (paper Algorithm 1, single-threaded): poll every source for its next fire, pick the
earliest by (time, source_id), advance the hybrid clock, run the fire's effects.

Added on top of the paper: a SQLite fire registry (crash resume, no replay), retry with backoff in
simulated time, and a dead-letter state. A fire's effects run as one unit and are retried together.
`lateness` records how long after its scheduled time each fire actually started (paper Table 7)."""
import statistics

from .clock import HybridClock
from .events import DispatchContext
from .store import Store


class Scheduler:
    def __init__(self, store: Store, clock: HybridClock, max_attempts: int = 3, backoff: float = 60.0):
        self.store = store
        self.clock = clock
        self.max_attempts = max_attempts
        self.backoff = backoff
        self.sources: list = []
        self.adapters: dict = {}
        self.agent_actions: dict = {}  # action name -> simulated time; adapters write, gated sources read
        self.retries = 0
        self.first_error = None
        self.lateness: list[float] = []
        self.completed, self.dead, self.attempts, self.not_before = store.load_state()

    def add_source(self, source) -> None:
        self.sources.append(source)

    def register(self, adapter) -> None:
        self.adapters[adapter.name] = adapter

    def lateness_stats(self) -> tuple[float, float]:
        if not self.lateness:
            return 0.0, 0.0
        return statistics.median(self.lateness), max(self.lateness)

    def run(self, max_fires: int | None = None) -> int:
        n = 0
        while max_fires is None or n < max_fires:
            ctx = DispatchContext(self.clock.now(), self.completed, self.dead, self.agent_actions)
            ready = []
            for s in self.sources:
                f = s.next_fire(ctx)
                if f is not None:
                    ready.append((max(f.t, self.not_before.get(f.fire_id, 0.0)), f.source_id, f))
            if not ready:
                break
            t, _, fire = min(ready, key=lambda r: (r[0], r[1], r[2].fire_id))
            self.clock.advance_to(t)
            started = self.clock.now()
            try:
                with self.clock.busy():
                    for eff in fire.effects:
                        self.adapters[eff.target].apply(eff, self)
                self.completed[fire.fire_id] = self.clock.now()
                self.store.mark_done(fire.fire_id, self.clock.now())
                self.lateness.append(max(0.0, started - fire.t))
            except Exception as exc:  # noqa: BLE001 - any effect failure is retried
                if self.first_error is None:
                    self.first_error = repr(exc)
                att = self.attempts.get(fire.fire_id, 0) + 1
                self.attempts[fire.fire_id] = att
                if att >= self.max_attempts:
                    self.dead.add(fire.fire_id)
                    self.store.mark_dead(fire.fire_id, repr(exc), att)
                else:
                    self.retries += 1
                    self.not_before[fire.fire_id] = self.clock.now() + self.backoff * 2 ** (att - 1)
                    self.store.mark_retry(fire.fire_id, att, self.not_before[fire.fire_id])
            n += 1
        return n
