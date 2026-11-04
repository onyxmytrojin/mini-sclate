"""Hybrid simulated clock: real time counts while work runs, idle gaps are skipped."""
import time
from contextlib import contextmanager


class HybridClock:
    def __init__(self, start: float = 0.0):
        self._sim = start
        self._start = start
        self.skipped = 0.0
        self._wall0 = time.perf_counter()

    def now(self) -> float:
        return self._sim

    @contextmanager
    def busy(self):
        """Time spent inside the block moves the simulated clock at real speed."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self._sim += time.perf_counter() - t0

    def advance_to(self, t: float) -> None:
        """Jump over an idle gap. Never moves backwards."""
        if t > self._sim:
            self.skipped += t - self._sim
            self._sim = t

    def sim_elapsed(self) -> float:
        return self._sim - self._start

    def wall_elapsed(self) -> float:
        return time.perf_counter() - self._wall0
