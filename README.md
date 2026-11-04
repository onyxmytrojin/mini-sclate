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
A model-based consolidation call (as in Hindsight/GBrain) is the obvious fix and is not built. One seed, 20 questions.

### Model-based consolidation (`extract+consolidate`)
Adds a nightly model call that merges lines about the same person and attribute even when worded differently
("Hindsight/GBrain-style" consolidation; my version, not a port). Same data and seed.

| model | extract | extract + consolidate |
|---|---|---|
| Haiku 5.5 via Claude Code | 0.85 | 0.95 |
| gpt-oss-120b | 0.95 | 0.40 |
| gpt-oss-20b | 0.85 | not completed (stopped twice: at 69 of 190 calls by memory pressure, then at 132 of 190 by me because Groq rate limits made it take hours) |

Two different stories from one change. With Haiku 5.5 the merge removed the duplicate stale values and reached 0.95;
one fact (Lena's locker) was still lost because the model dropped it from the merged list despite the instruction.
With gpt-oss-120b it went badly: 7 of 30 consolidation calls produced no parseable lines (dead after retries) and the
memory ended with 14 lines instead of about 30, so many facts were lost (8 of 20 right). I have not diagnosed why
(output format, truncation and over-aggressive merging are all possible), so treat the 0.40 as a failure of this
prompt on this model, not a general result. The takeaway I can stand behind: a model-written consolidation step can
fix stale duplicates, but it is lossy and its reliability depends on the model; a safeguard that refuses a merge
that shrinks the memory too much would be the next thing to try. One seed, 20 questions, one run each.

## What this does not show
- **Not a replication of the paper's findings.** The memories are toy baselines I wrote. The ties at 1.00 come from
  how they are built. The capped-vs-added gap is built in. Nothing here supports or contradicts the paper's claim
  that an added memory system does not reliably beat a harness's native memory.
- **The default benchmark is easy (hard mode above is the harder one).** One lookup per question, so a competent model answers correctly whenever the right
  line is in the prompt. It cannot tell models apart. I have run only one model. Harder questions (similar keys,
  paraphrase, conflicting values) would be needed for that.
- **One seed, small samples.** 20 to 60 questions per config. Differences of a few points are noise.
- **Not replicated:** containers, libfaketime (only the prompt sees the simulated date), mid-turn event arrival
  (each fire runs to completion), the capture proxy's log probabilities, the real harnesses and memory systems, the
  seven ported benchmarks, post-training.
- A failing fire blocks later fires from the same source until it succeeds or is dead-lettered.

## Next steps
Make the benchmark harder, run a second model for comparison, add a second benchmark adapter, and persist the
agent's working state so a crash mid-session resumes.
