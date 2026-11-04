"""LLM-extraction memory, in the style the paper describes for Mem0 / Hindsight / GBrain: the memory makes its own
model calls, with the same model as the agent ("make their own extraction and consolidation calls with the same
model as the agent", sec. 4.2). This is my small version, not a port of any of them; I do not know their internals.

- observe(): one model call turns each told sentence into a normalized `person | attribute | value` line.
  If the reply cannot be parsed, the raw sentence is kept instead.
- consolidate() (the nightly cron): keeps only the newest line per (person, attribute), so a fact that was set
  again replaces the old value.
- recall(): returns every consolidated line plus the day's not-yet-consolidated lines. No retrieval step, so it
  cannot miss a paraphrase; the cost is that the model call count grows with the number of facts told."""
import re

EXTRACT_SYSTEM = ("Rewrite the sentence as one line in the form: person | attribute | value. Use the person's first "
                  "name, a short lowercase attribute name (for example 'gym locker code'), and the value exactly as "
                  "written. Reply with only that line.")


class ExtractMemory:
    name = "extract"

    def __init__(self, store, budget: int = 6):
        self.store = store
        self.budget = budget  # unused: recall returns every consolidated line
        self.proxy = None

    def attach(self, proxy) -> None:
        self.proxy = proxy

    def observe(self, text: str) -> None:
        reply = self.proxy.complete("Sentence: " + text, EXTRACT_SYSTEM).strip().splitlines()[0] if self.proxy else ""
        parts = [p.strip() for p in reply.split("|")]
        self.store.add_note("extract", " | ".join(parts) if len(parts) == 3 and all(parts) else text)

    def consolidate(self) -> None:
        latest: dict[tuple, str] = {}
        order: list[str] = []
        for line in self.store.notes("extract"):
            parts = [p.strip() for p in line.split("|")]
            key = (parts[0].lower(), parts[1].lower()) if len(parts) == 3 else (line,)
            latest.pop(key, None)  # re-insert so order reflects when each fact was last set
            latest[key] = line
        self.store.clear_bucket("extract")
        for line in latest.values():
            self.store.add_note("extract", line)

    def recall(self, key: str) -> list[str]:
        return [self._pretty(n) for n in self.store.notes("extract")]

    @staticmethod
    def _pretty(line: str) -> str:
        parts = [p.strip() for p in line.split("|")]
        return f"{parts[0]}'s {parts[1]}: {parts[2]}" if len(parts) == 3 else line


CONSOLIDATE_SYSTEM = ("You maintain a memory of facts, one per line as: person | attribute | value. Lines are listed "
                      "oldest first. Merge them: lines about the same person and the same real-world attribute are the "
                      "same fact even if the attribute is worded differently; keep only the newest value for each "
                      "fact. Do not invent or drop facts about other attributes. Reply with only the merged lines, in "
                      "the same oldest-to-newest order, one per line, no commentary.")


class ConsolidatingExtractMemory(ExtractMemory):
    """ExtractMemory plus a model-based nightly consolidation call, as the paper describes for Hindsight and GBrain
    ("memory consolidation events between sessions"). The exact-string dedupe runs first to shrink the prompt; the
    model call then merges lines whose attribute names differ but mean the same thing."""
    name = "extract+consolidate"

    def consolidate(self) -> None:
        super().consolidate()
        lines = self.store.notes("extract")
        if not lines or not self.proxy:
            return
        reply = self.proxy.complete("Memory lines (oldest first):\n" + "\n".join(lines), CONSOLIDATE_SYSTEM)
        merged = []
        for raw in reply.strip().splitlines():
            parts = [p.strip() for p in raw.split("|")]
            if len(parts) == 3 and all(parts):
                merged.append(" | ".join(parts))
        if not merged:
            raise RuntimeError("consolidation reply had no parseable lines; keeping the old memory")
        self.store.clear_bucket("extract")
        for line in merged:
            self.store.add_note("extract", line)
