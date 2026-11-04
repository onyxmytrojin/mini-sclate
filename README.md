# mini-sclate

A small rebuild of the core scheduler from Apple's paper
[SCLATE: A Substrate for Continual-Learning Agent Training and Evaluation](https://machinelearning.apple.com/research/sclate-agent-training-evaluation)
(Jung, Salekin, Tran, Movellan, Huang, Bilkhu; [arXiv 2609.32391](https://arxiv.org/abs/2609.32391)).
This is a learning project. It is not affiliated with Apple or the authors.

## The problem the paper describes
Agents that learn across many sessions have to be tested with agent-side events mixed in with the benchmark's own
tasks: sessions stopping and starting, crons, memory consolidation. Benchmarks only schedule their own events, so
every benchmark/agent pair ends up with a custom scheduling loop.

## What is rebuilt
Mapped to the paper's sections and tables. The full table, including what is **not** replicated, is in
[`notes/fidelity.md`](notes/fidelity.md).

- **Open scheduler with pull-based sources** (3.1, Algorithm 1). Each tick, every source is polled with a
  `DispatchContext` and the earliest fire runs, ties broken on source id.
- **Hybrid simulated clock.** Work runs at real speed, idle gaps are skipped.
- **Gated sources** (Table 5). `EventChainSource` (fires after all prerequisite fires complete) and
  `AgentActionGatedSource` (fires after the agent performs a named action).
- **Typed effects** (Table 6): `Deliver`, `RunHook`, `StartAgent`, `ShutdownAgent`, `SaveState`, `RestoreState`.
- **Independent grader.** Grading is a separate fire, gated on the agent having answered. The scheduler holds no
  grading logic.
- **Agent restarts between sessions.** `ShutdownAgent` wipes working context and in-process memory. Memory returns
  only through a snapshot with an integrity token, and a torn or tampered snapshot is refused.
- **Multi-session recall protocol** (4.2). In `history` mode, facts are split across consecutive days, the agent
  stops between sessions, and every question is asked in the last session. The facts are synthetic, not
  LongMemEval or PersonaMem.
- **Native vs added memory structure** (4.2). A capped memory that rejects new facts once full, with and without a
  selective memory added on top.
- **Delivery lateness** (4.1, Table 7) and a model-call proxy that logs usage.

## What I added (not in the paper)
A SQLite fire registry so a crash resumes without replaying finished work, retry with exponential backoff in
simulated time, a dead-letter state, and `--flaky` fault injection on the consolidation cron. If a cron is
dead-lettered, the probe gated on it never runs.

## Run it
```
set PYTHONPATH=src            (PowerShell: $env:PYTHONPATH="src")
python -m mini_sclate.run --days 30 --mode history            # mock model, no key needed
python -m mini_sclate.run --days 30 --flaky 0.4               # inject cron failures
python -m mini_sclate.run --days 30 --mode history --model groq
python -m mini_sclate.run --days 30 --mode hard --model groq --model-id openai/gpt-oss-120b --configs extract+consolidate --max-tokens 4096
python -m unittest discover -s tests
```
For `--model groq` or `--model anthropic`, copy `.env.example` to `.env` and fill in the key (`.env` is gitignored).
Default models: `openai/gpt-oss-20b` on Groq, `claude-haiku-5-5` on Anthropic. The Anthropic client is tested only
against a stub, not the live API.

## Results with a real model
`openai/gpt-oss-20b` on Groq, seed 0, one run each. Full tables are in [`reports/`](reports/).

**History mode** (30 simulated days, 20 questions in the last session):

| memory | accuracy |
|---|---|
| none | 0.00 |
| recency | 0.00 |
| keyword | 1.00 |
| selective | 1.00 |
| capped | 0.40 |
| capped + selective | 1.00 |

**Daily mode** (20 simulated days, 60 daily questions plus a probe after each night's consolidation):

| memory | daily accuracy | probe accuracy |
|---|---|---|
| none | 0.30 | 0.00 |
| recency | 0.37 | 0.35 |
| keyword | 1.00 | 1.00 |
| selective | 1.00 | 1.00 |
| capped | 0.82 | 0.85 |
| capped + selective | 1.00 | 1.00 |

The mock model gives the same history-mode accuracies. Real API latency counts as busy time on the clock, so the
simulated-to-real speedup is about 8,000x in the daily run against millions-x with the mock. Event lateness reached
about 6 s at worst in the daily run and about 30 s in the history run.

## Results through an unmodified Claude Code
`claude -p --bare` (Claude Code 2.1.316, Haiku 5.5, no tools) run once per model call behind a local capture proxy
that holds the API key, pins the model and enforces a $2 lifetime cap. History mode, 30 days, seed 0, one run
(report: `reports/claude-code-haiku-5-5-history-30d.md`).

| memory | accuracy |
|---|---|
| none | 0.00 |
| recency | 0.00 |
| keyword | 1.00 |
| selective | 1.00 |
| capped | 0.40 |
| capped + selective | 1.00 |

These match the Groq and mock numbers exactly, which confirms the benchmark does not separate models. What it adds
is that the real harness path works end to end. Total spend for 120 calls plus tests: $0.0033, about 230 tokens per
call, about 23 s per call (process startup), so lateness reached about 450 s. This uses the harness only as a
stateless call, not its native memory, tools or multi-turn loop.

## Hard mode (separates models)
`--mode hard`: 8 people with near-identical names x 4 attributes with 4-digit values, each fact told in two phrasings
and reset several times over 30 days, questions paraphrased, all asked in the last session (20 questions). Memories:
none, recency, word-overlap retrieval (budget 6), the same under a 40-note cap, and full context. Seed 0, one run each
(reports in `reports/hard-*.md`).

| memory | mock | gpt-oss-20b | gpt-oss-120b | Haiku 5.5 via Claude Code |
|---|---|---|---|---|
| none | 0.00 | 0.00 | 0.00 | 0.00 |
| recency | 0.00 | 0.00 | 0.00 | 0.00 |
| overlap | 0.70 | 0.90 | 0.90 | 0.90 |
| capped overlap | 0.05 | 0.05 | 0.05 | 0.05 |
| full context | 0.70 | 0.55 | 0.85 | 0.95 |

Reading it: full context is where the models differ (0.55, 0.85, 0.95), because the model must pick the right person,
attribute and latest value out of about 120 sentences. Overlap retrieval is capped at 0.90 for all three real
models, which points to the same two questions never being retrieved (lexical retrieval misses paraphrases), so that
ceiling comes from the memory, not the model. The capped memory fails for everyone because it stops storing after 40
notes. 20 questions per cell and one seed: a gap of one question is 5 points, so treat 0.85 vs 0.95 as suggestive only.
Spend for all Claude Code runs so far: $0.017 of $2.

### LLM-extraction memory (the paper's style of memory)
`extract` makes its own model call per told sentence to rewrite it as `person | attribute | value`, and the nightly cron
keeps the newest line per (person, attribute). The paper describes Mem0, Hindsight and GBrain as memories that "make
their own extraction and consolidation calls with the same model as the agent"; this is my small version, not a port.
Same data and seed as the table above, one run each, 140 model calls per run (120 extraction + 20 answers):

| model | overlap | full context | extract |
|---|---|---|---|
| gpt-oss-20b | 0.90 | 0.55 | 0.85 |
| gpt-oss-120b | 0.90 | 0.85 | 0.95 |
| Haiku 5.5 via Claude Code | 0.90 | 0.95 | 0.85 (two clean runs, both 0.85) |

Extraction fixes the retrieval misses that cap overlap, and it helps the weakest model most (0.55 to 0.85). It does not
beat full context for the strongest model. I looked at the Haiku run's three wrong answers: the model wrote the same
attribute under different names ("gym locker code" / "gym locker combination", "badge" / "badge number" / "office
badge number", "parking spot" / "parking space"), so the consolidation step, which dedupes on the exact attribute
string, kept both an old and a new value and the answer step sometimes picked the old one. That is the same kind of
weakness the paper reports for added memories, found here by reading the stored lines, not proven by the paper.
The model-based consolidation call that addresses this (as in Hindsight/GBrain) is the next section. One seed, 20 questions.

### Model-based consolidation (`extract+consolidate`)
Adds a nightly model call that merges lines about the same person and attribute even when worded differently
("Hindsight/GBrain-style" consolidation; my version, not a port). Same data and seed.

| model | extract | extract + consolidate |
|---|---|---|
| Haiku 5.5 via Claude Code | 0.85 | 0.95 |
| gpt-oss-120b, 1,024-token output budget | 0.95 | 0.40 |
| gpt-oss-120b, 4,096-token output budget (`--max-tokens 4096`) | 0.95 | **1.00** |
| gpt-oss-20b | 0.85 | not completed (stopped twice: at 69 of 190 calls by memory pressure, then at 132 of 190 by me because Groq rate limits made it take hours) |

With Haiku 5.5 the merge removed the duplicate stale values and reached 0.95; one fact (Lena's locker) was still lost
because the model dropped it from the merged list despite the instruction.

The 0.40 for gpt-oss-120b was truncation, not the merge prompt. At the original 1,024-token output budget, 30 calls
ended at the ceiling (the stored usage shows `tokens_out` = 1024), because gpt-oss spends part of that budget on
reasoning. 7 consolidation calls produced no parseable lines (dead after retries) and the memory ended with 14 lines
instead of about 30 (8 of 20 right). Rerunning the same configuration (same data, seed and prompt) with a 4,096-token
budget gave 20 of 20, with no retries and no dead fires; the longest reply was 1,892 tokens, so the merged list simply
did not fit in 1,024. A model-written consolidation step can fix stale duplicates, and it is lossy whenever its reply
is cut short or the model drops a line, so its output budget is part of its correctness. Report:
`reports/hard-extract-consolidate-groq-gpt-oss-120b-4096.md` (the truncated run is kept in
`reports/hard-extract-consolidate-groq-gpt-oss-120b-FAILED-PARSE.md`). One seed, 20 questions, one run each.

## Scope
- **Not a replication of the paper's findings.** The memories are toy baselines I wrote. The ties at 1.00 come from
  how they are built, and the capped-vs-added gap is built in. Nothing here supports or contradicts the paper's claim
  that an added memory system does not reliably beat a harness's native memory.
- **Models:** the default benchmark has one lookup per question, so any competent model answers it when the right line
  is in the prompt and it cannot tell models apart. Hard mode separates three models (gpt-oss-20b, gpt-oss-120b,
  Haiku 5.5) and is where the model comparisons above come from.
- **Samples:** one seed and 20 to 60 questions per config, so differences of a few points are within noise.
- **Left out of the rebuild:** containers, libfaketime (only the prompt sees the simulated date), mid-turn event arrival
  (each fire runs to completion), the capture proxy's log probabilities, the real harnesses and memory systems, the
  seven ported benchmarks, post-training. `notes/fidelity.md` has the full table.
- A failing fire blocks later fires from the same source until it succeeds or is dead-lettered.
