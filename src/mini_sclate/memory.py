"""Toy memory configurations written for this project. They are NOT models of any real harness or memory
system. `capped` imitates one behaviour the paper describes for Hermes's built-in memory (a small size cap that
rejects new facts once full); the cap size and everything else here is my own."""
import re

STOP = {"the", "what", "which", "who", "does", "that", "this", "with", "for", "and", "now", "has", "his", "her",
        "can", "its", "are", "was", "from", "number", "use", "uses"}
FACT = re.compile(r"(.+?) is (.+)")


class Memory:
    name = "base"

    def __init__(self, store, budget: int = 6):
        self.store = store
        self.budget = budget  # max memory lines placed in a prompt

    def observe(self, text: str) -> None: ...

    def consolidate(self) -> None: ...

    def recall(self, key: str) -> list[str]:
        return []


class NoMemory(Memory):
    name = "none"


class RecencyMemory(Memory):
    """Keeps every note, recalls only the most recent ones."""
    name = "recency"

    def observe(self, text):
        self.store.add_note("recency", text)

    def recall(self, key):
        return self.store.notes("recency")[-self.budget:]


class KeywordMemory(Memory):
    """Keeps every note, recalls the notes that start with the asked key."""
    name = "keyword"

    def observe(self, text):
        self.store.add_note("keyword", text)

    def recall(self, key):
        return [n for n in self.store.notes("keyword") if n.startswith(key + " is ")][-self.budget:]


class SelectiveMemory(Memory):
    """Raw notes land in an inbox; the nightly cron distills them into one value per key."""
    name = "selective"

    def observe(self, text):
        self.store.add_note("inbox", text)

    def consolidate(self):
        for text in self.store.notes("inbox"):
            m = FACT.fullmatch(text)
            if m:
                self.store.kv_put(m.group(1), m.group(2))
        self.store.clear_bucket("inbox")

    def recall(self, key):
        lines = []
        v = self.store.kv_get(key)
        if v is not None:
            lines.append(f"{key} is {v}")
        lines += [n for n in self.store.notes("inbox") if n.startswith(key + " is ")]
        return lines[-self.budget:]


class CappedMemory(Memory):
    """Keyword recall over a fixed-size store that rejects new notes once full."""
    name = "capped"

    def __init__(self, store, budget: int = 6, cap: int = 40):
        super().__init__(store, budget)
        self.cap = cap

    def observe(self, text):
        if len(self.store.notes("capped")) < self.cap:
            self.store.add_note("capped", text)

    def recall(self, key):
        return [n for n in self.store.notes("capped") if n.startswith(key + " is ")][-self.budget:]


class CappedPlusSelective(Memory):
    """A capped 'native' memory with an added selective memory on top, mirroring the paper's native-vs-added
    comparison structure. Added memory's lines come last so the newest value wins."""
    name = "capped+selective"

    def __init__(self, store, budget: int = 6):
        super().__init__(store, budget)
        self.native = CappedMemory(store, budget)
        self.added = SelectiveMemory(store, budget)

    def observe(self, text):
        self.native.observe(text)
        self.added.observe(text)

    def consolidate(self):
        self.added.consolidate()

    def recall(self, key):
        return (self.native.recall(key) + self.added.recall(key))[-self.budget:]


def tokens(text: str) -> set:
    """Lowercased content words, for the lexical retrieval used in hard mode."""
    return {t for t in re.findall(r"[a-z]+", text.lower()) if len(t) > 2 and t not in STOP}


class OverlapMemory(Memory):
    """Hard-mode retrieval: keeps every sentence, returns the `budget` with the most words in common with the
    question (ties go to the more recent), in the order they were told. Purely lexical, so paraphrase hurts it."""
    name = "overlap"
    bucket = "overlap"

    def observe(self, text):
        self.store.add_note(self.bucket, text)

    def recall(self, key):
        q = tokens(key)
        scored = [(len(q & tokens(n)), i, n) for i, n in enumerate(self.store.notes(self.bucket))]
        top = sorted((x for x in scored if x[0] > 0), reverse=True)[:self.budget]
        return [n for _, _, n in sorted(top, key=lambda x: x[1])]


class CappedOverlapMemory(OverlapMemory):
    """Overlap retrieval over a fixed-size store that rejects new sentences once full (the Hermes-style cap)."""
    name = "capped-overlap"
    bucket = "capped-overlap"

    def __init__(self, store, budget: int = 6, cap: int = 40):
        super().__init__(store, budget)
        self.cap = cap

    def observe(self, text):
        if len(self.store.notes(self.bucket)) < self.cap:
            super().observe(text)


class FullContextMemory(Memory):
    """Keeps every sentence and puts all of them in the prompt, so the model does all the retrieval."""
    name = "full"

    def observe(self, text):
        self.store.add_note("full", text)

    def recall(self, key):
        return self.store.notes("full")


CONFIGS = {c.name: c for c in (NoMemory, RecencyMemory, KeywordMemory, SelectiveMemory, CappedMemory,
                               CappedPlusSelective)}

from .extract_memory import ConsolidatingExtractMemory, ExtractMemory  # noqa: E402

HARD_CONFIGS = {c.name: c for c in (NoMemory, RecencyMemory, OverlapMemory, CappedOverlapMemory, FullContextMemory,
                                    ExtractMemory, ConsolidatingExtractMemory)}
