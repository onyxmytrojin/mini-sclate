"""Event model following the SCLATE paper (Algorithm 1, Tables 4-6).

Sources are polled with a DispatchContext and return their next Fire, or None when dormant. A Fire carries
typed Effects. Source classes here map to the paper's catalog: ScheduledSource (time-triggered, like
UserInputSource/CronSource), EventChainSource (gated on prior fire_ids), AgentActionGatedSource (gated on agent
actions recorded in ctx.agent_actions)."""
from dataclasses import dataclass, field

# Effect primitives (paper Table 6). RunHook carries {"hook": name, ...} for adapter callbacks.
DELIVER, RUN_HOOK = "Deliver", "RunHook"
START_AGENT, SHUTDOWN_AGENT = "StartAgent", "ShutdownAgent"
SAVE_STATE, RESTORE_STATE = "SaveState", "RestoreState"


@dataclass
class Effect:
    target: str  # adapter name: "agent" or "bench"
    kind: str    # one of the primitives above
    payload: dict = field(default_factory=dict)


@dataclass
class Fire:
    t: float
    fire_id: str
    source_id: str
    effects: list[Effect]


@dataclass
class DispatchContext:
    """Read-only snapshot. `completed` maps fire_id -> simulated completion time (the paper's registry H);
    `agent_actions` maps an action name -> simulated time the agent performed it."""
    time: float
    completed: dict
    dead: set
    agent_actions: dict = field(default_factory=dict)


class ScheduledSource:
    """Time-triggered fires, in order. A fire that keeps failing blocks later fires from the same source
    until it succeeds or is dead-lettered."""

    def __init__(self, source_id: str, fires: list[Fire]):
        self.source_id = source_id
        self.fires = sorted(fires, key=lambda f: (f.t, f.fire_id))
        self.cursor = 0

    def next_fire(self, ctx: DispatchContext):
        while self.cursor < len(self.fires):
            f = self.fires[self.cursor]
            if f.fire_id in ctx.completed or f.fire_id in ctx.dead:
                self.cursor += 1
            else:
                return f
        return None


class _GatedSource:
    """Shared logic: each item becomes eligible when its gate opens; earliest eligible item is the next fire."""

    def __init__(self, source_id: str, items: list):
        self.source_id = source_id
        self.items = items

    def _gate_time(self, item, ctx: DispatchContext):
        raise NotImplementedError

    def next_fire(self, ctx: DispatchContext):
        best = None
        for item in self.items:
            fid = item[2]
            if fid in ctx.completed or fid in ctx.dead:
                continue
            base = self._gate_time(item, ctx)
            if base is None:
                continue
            f = Fire(base + item[1], fid, self.source_id, item[3])
            if best is None or (f.t, f.fire_id) < (best.t, best.fire_id):
                best = f
        return best


class EventChainSource(_GatedSource):
    """Fires once ALL prerequisite fire_ids have completed (paper's EventChainSource). If a prerequisite is
    dead-lettered the item never fires. items: (prereq_fire_ids, delay, own_fire_id, effects)."""

    def _gate_time(self, item, ctx):
        times = [ctx.completed.get(p) for p in item[0]]
        return None if any(t is None for t in times) else max(times)


class AgentActionGatedSource(_GatedSource):
    """Fires once the agent has performed a named action (paper's AgentActionGatedSource).
    items: (action_name, delay, own_fire_id, effects)."""

    def _gate_time(self, item, ctx):
        return ctx.agent_actions.get(item[0])
