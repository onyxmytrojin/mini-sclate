import unittest

from mini_sclate.extract_memory import (CONSOLIDATE_SYSTEM, EXTRACT_SYSTEM, ConsolidatingExtractMemory,
                                        ExtractMemory)
from mini_sclate.store import Store


class FakeProxy:
    """Scripted replies keyed by system prompt, so no model is needed."""

    def __init__(self, extract, consolidate=None):
        self.extract, self.consolidate, self.calls = list(extract), consolidate, []

    def complete(self, prompt, system=None):
        self.calls.append(system)
        if system == EXTRACT_SYSTEM:
            return self.extract.pop(0)
        return self.consolidate(prompt) if callable(self.consolidate) else self.consolidate


class ExtractTests(unittest.TestCase):
    def make(self, cls, extract, consolidate=None):
        m = cls(Store())
        m.attach(FakeProxy(extract, consolidate))
        return m

    def test_observe_stores_parsed_line_and_falls_back_to_raw(self):
        m = self.make(ExtractMemory, ["Maya | badge number | 1234", "garbled reply"])
        m.observe("Maya was issued badge 1234.")
        m.observe("Noah parks in spot 5555.")
        self.assertEqual(m.store.notes("extract"), ["Maya | badge number | 1234", "Noah parks in spot 5555."])

    def test_exact_dedupe_keeps_newest_value(self):
        m = self.make(ExtractMemory, ["Maya | badge | 1111", "Maya | badge | 2222"])
        m.observe("a"); m.observe("b"); m.consolidate()
        self.assertEqual(m.store.notes("extract"), ["Maya | badge | 2222"])

    def test_synonym_attributes_survive_exact_dedupe(self):
        m = self.make(ExtractMemory, ["Maya | badge | 1111", "Maya | badge number | 2222"])
        m.observe("a"); m.observe("b"); m.consolidate()
        self.assertEqual(len(m.store.notes("extract")), 2)  # the weakness the model-based step targets

    def test_model_consolidation_merges_synonyms(self):
        m = self.make(ConsolidatingExtractMemory, ["Maya | badge | 1111", "Maya | badge number | 2222"],
                      consolidate="Maya | badge number | 2222")
        m.observe("a"); m.observe("b"); m.consolidate()
        self.assertEqual(m.store.notes("extract"), ["Maya | badge number | 2222"])
        self.assertIn(CONSOLIDATE_SYSTEM, m.proxy.calls)

    def test_unparseable_consolidation_keeps_old_memory_and_raises(self):
        m = self.make(ConsolidatingExtractMemory, ["Maya | badge | 1111"], consolidate="sorry, I can't")
        m.observe("a")
        with self.assertRaises(RuntimeError):
            m.consolidate()
        self.assertEqual(m.store.notes("extract"), ["Maya | badge | 1111"])


if __name__ == "__main__":
    unittest.main()
