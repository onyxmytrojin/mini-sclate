import json
import os
import tempfile
import unittest

from mini_sclate.clock import HybridClock
from mini_sclate.events import AgentActionGatedSource, Effect, EventChainSource, Fire, ScheduledSource
from mini_sclate.proxy import AnthropicModel, GroqModel, MockModel, ModelProxy
from mini_sclate.run import run_config
from mini_sclate.scheduler import Scheduler
from mini_sclate.snapshot import TornSnapshot, restore_state, save_state
from mini_sclate.store import Store


class Recorder:
    name = "rec"

    def __init__(self, fail_times: int = 0, fail_ids=()):
        self.seen: list[str] = []
        self.fail_times = fail_times
        self.fail_ids = set(fail_ids)
        self.calls = 0

    def apply(self, eff, sched):
        self.calls += 1
        if self.calls <= self.fail_times or eff.payload["id"] in self.fail_ids:
            raise RuntimeError("boom")
        if "action" in eff.payload:
            sched.agent_actions[eff.payload["action"]] = sched.clock.now()
        self.seen.append(eff.payload["id"])


def fire(t, fid, src="s", **extra):
    return Fire(t, fid, src, [Effect("rec", "x", {"id": fid, **extra})])


def make(rec=None, db=":memory:", **kw):
    store, clock = Store(db), HybridClock()
    sched = Scheduler(store, clock, **kw)
    rec = rec or Recorder()
    sched.register(rec)
    return store, clock, sched, rec


class SchedulerTests(unittest.TestCase):
    def test_idle_gap_is_skipped(self):
        _, clock, sched, _ = make()
        sched.add_source(ScheduledSource("s", [fire(30 * 86400, "a")]))
        sched.run()
        self.assertGreaterEqual(clock.sim_elapsed(), 30 * 86400)
        self.assertLess(clock.wall_elapsed(), 2)

    def test_two_sources_interleave_in_time_order(self):
        _, _, sched, rec = make()
        sched.add_source(ScheduledSource("a", [fire(10, "a1", "a"), fire(30, "a2", "a")]))
        sched.add_source(ScheduledSource("b", [fire(20, "b1", "b"), fire(40, "b2", "b")]))
        sched.run()
        self.assertEqual(rec.seen, ["a1", "b1", "a2", "b2"])

    def test_tie_breaks_on_source_id(self):
        _, _, sched, rec = make()
        sched.add_source(ScheduledSource("z", [fire(5, "z1", "z")]))
        sched.add_source(ScheduledSource("a", [fire(5, "a1", "a")]))
        sched.run()
        self.assertEqual(rec.seen, ["a1", "z1"])

    def test_event_chain_waits_for_all_prerequisites(self):
        _, clock, sched, rec = make()
        sched.add_source(ScheduledSource("s", [fire(100, "p1"), fire(300, "p2")]))
        sched.add_source(EventChainSource("c", [(("p1", "p2"), 50, "child", [Effect("rec", "x", {"id": "child"})])]))
        sched.run()
        self.assertEqual(rec.seen, ["p1", "p2", "child"])
        self.assertGreaterEqual(clock.now(), 350)

    def test_dead_prerequisite_blocks_child(self):
        store, _, sched, rec = make(Recorder(fail_ids={"dep"}))
        sched.add_source(ScheduledSource("s", [fire(100, "dep")]))
        sched.add_source(EventChainSource("c", [(("dep",), 50, "child", [Effect("rec", "x", {"id": "child"})])]))
        sched.run()
        self.assertEqual(rec.seen, [])
        self.assertEqual(store.counts(), {"dead": 1})

    def test_agent_action_gated_source(self):
        _, _, sched, rec = make()
        sched.add_source(ScheduledSource("s", [fire(100, "act", action="did-thing")]))
        sched.add_source(AgentActionGatedSource("g", [("did-thing", 5, "graded", [Effect("rec", "x", {"id": "graded"})]),
                                                      ("never", 0, "never-fires", [Effect("rec", "x", {"id": "nf"})])]))
        sched.run()
        self.assertEqual(rec.seen, ["act", "graded"])

    def test_retry_then_success_and_lateness(self):
        store, _, sched, rec = make(Recorder(fail_times=2))
        sched.add_source(ScheduledSource("s", [fire(1, "k")]))
        sched.run()
        self.assertEqual(rec.seen, ["k"])
        self.assertEqual(sched.retries, 2)
        self.assertEqual(store.counts(), {"done": 1})
        self.assertGreaterEqual(sched.lateness_stats()[1], 60)  # waited out the first backoff at least

    def test_on_time_fires_have_no_lateness(self):
        _, _, sched, _ = make()
        sched.add_source(ScheduledSource("s", [fire(10, "a"), fire(20, "b")]))
        sched.run()
        self.assertLess(sched.lateness_stats()[1], 0.5)

    def test_dead_letter_after_max_attempts(self):
        store, _, sched, rec = make(Recorder(fail_times=99))
        sched.add_source(ScheduledSource("s", [fire(1, "k"), fire(2, "k2")]))
        sched.run()
        self.assertEqual(rec.calls, 6)
        self.assertEqual(store.counts(), {"dead": 2})

    def test_crash_resume_does_not_replay_finished_fires(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "q.db")
            ids = [f"e{i}" for i in range(6)]
            store, _, sched, rec = make(db=path)
            sched.add_source(ScheduledSource("s", [fire(i, f) for i, f in enumerate(ids)]))
            sched.run(max_fires=3)  # "crash" here
            store.db.close()

            store2, _, sched2, rec2 = make(db=path)
            sched2.add_source(ScheduledSource("s", [fire(i, f) for i, f in enumerate(ids)]))
            sched2.run()
            self.assertEqual(rec.seen + rec2.seen, ids)
            self.assertEqual(store2.counts(), {"done": 6})
            store2.db.close()


class SnapshotTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")
            a = Store()
            a.add_note("x", "k is 1")
            a.kv_put("k", "1")
            save_state(a, path)
            b = Store()
            b.add_note("junk", "old")
            self.assertTrue(restore_state(b, path))
            self.assertEqual(b.notes("x"), ["k is 1"])
            self.assertEqual(b.notes("junk"), [])
            self.assertEqual(b.kv_get("k"), "1")

    def test_no_snapshot_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(restore_state(Store(), os.path.join(d, "none.json")))

    def test_torn_and_tampered_snapshots_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")
            a = Store()
            a.kv_put("k", "1")
            save_state(a, path)
            raw = open(path, encoding="utf-8").read()
            open(path, "w", encoding="utf-8").write(raw[: len(raw) // 2])  # torn write
            with self.assertRaises(TornSnapshot):
                restore_state(Store(), path)
            doc = json.loads(raw)
            doc["payload"] = doc["payload"].replace('"1"', '"2"')  # tampered payload, old token
            open(path, "w", encoding="utf-8").write(json.dumps(doc))
            with self.assertRaises(TornSnapshot):
                restore_state(Store(), path)


class ModelTests(unittest.TestCase):
    def test_anthropic_client_parses_response_and_usage(self):
        seen = {}

        def stub(body):
            seen.update(body)
            return {"content": [{"type": "text", "text": " 4821 "}], "usage": {"input_tokens": 30, "output_tokens": 2}}

        proxy = ModelProxy(AnthropicModel(post=stub), HybridClock())
        self.assertEqual(proxy.complete("a is 1\nQ: a"), "4821")
        self.assertEqual(proxy.calls[0]["tokens_in"], 30)
        self.assertEqual(seen["messages"][0]["role"], "user")

    def test_groq_client_parses_response_and_usage(self):
        seen = {}

        def stub(body):
            seen.update(body)
            return {"choices": [{"message": {"content": "4821\n"}}],
                    "usage": {"prompt_tokens": 41, "completion_tokens": 3}}

        proxy = ModelProxy(GroqModel(post=stub), HybridClock())
        self.assertEqual(proxy.complete("a is 1\nQ: a"), "4821")
        self.assertEqual((proxy.calls[0]["tokens_in"], proxy.calls[0]["tokens_out"]), (41, 3))
        self.assertEqual(seen["messages"][0]["role"], "system")

    def test_clients_require_keys(self):
        saved = {k: os.environ.pop(k, None) for k in ("GROQ_API_KEY", "ANTHROPIC_API_KEY")}
        try:
            with self.assertRaises(RuntimeError):
                GroqModel()
            with self.assertRaises(RuntimeError):
                AnthropicModel()
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


class CaptureModel(MockModel):
    def __init__(self):
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        return super().complete(prompt)


class EndToEndTests(unittest.TestCase):
    def test_memory_survives_process_shutdown_only_via_snapshot(self):
        none = run_config("none", days=20, seed=1)
        sel = run_config("selective", days=20, seed=1)
        self.assertGreater(sel["accuracy"], none["accuracy"] + 0.3)

    def test_probes_fire_after_each_cron(self):
        self.assertEqual(run_config("selective", days=10, seed=1)["probes"], "10/10")

    def test_dead_cron_suppresses_its_probe(self):
        r = run_config("selective", days=20, seed=2, flaky=0.9)
        self.assertGreater(r["dead"], 0)
        self.assertLess(int(r["probes"].split("/")[0]), 20)

    def test_flaky_cron_retries_and_selective_still_recalls(self):
        r = run_config("selective", days=20, seed=1, flaky=0.4)
        self.assertGreater(r["retries"], 0)
        self.assertEqual(r["accuracy"], 1.0)

    def test_same_seed_is_deterministic(self):
        a = run_config("recency", days=15, seed=3)
        b = run_config("recency", days=15, seed=3)
        self.assertEqual((a["accuracy"], a["tokens_in"]), (b["accuracy"], b["tokens_in"]))

    def test_history_mode_asks_only_in_last_session(self):
        none = run_config("none", days=20, seed=1, mode="history")
        keyword = run_config("keyword", days=20, seed=1, mode="history")
        self.assertEqual(none["model_calls"], 20)
        self.assertEqual(none["accuracy"], 0.0)  # nothing carried across the shutdowns
        self.assertEqual(keyword["accuracy"], 1.0)

    def test_added_memory_lifts_capped_native_memory(self):
        capped = run_config("capped", days=30, seed=0, mode="history")
        both = run_config("capped+selective", days=30, seed=0, mode="history")
        self.assertLess(capped["accuracy"], 1.0)
        self.assertGreater(both["accuracy"], capped["accuracy"])

    def test_simulated_date_reaches_the_prompt(self):
        model = CaptureModel()
        run_config("keyword", days=4, seed=0, model=model)
        self.assertTrue(any(p.startswith("Date: day 4") for p in model.prompts))
        self.assertTrue(any(p.startswith("Date: day 1") for p in model.prompts))


if __name__ == "__main__":
    unittest.main()
