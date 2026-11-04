# mini-sclate: plan

Small rebuild of one idea from Apple's SCLATE paper
(https://machinelearning.apple.com/research/sclate-agent-training-evaluation, arXiv 2609.32391).
I read the abstract only so far; this scope follows the abstract, not the paper's implementation.

## Problem (from the abstract)
Continual-learning agents run over long multi-session horizons. Testing them means interleaving benchmark
tasks with agent-side events (session stop/start, crons, memory consolidation). Benchmarks only schedule
their own events, so every benchmark/agent pair builds its own scheduling loop.

## What SCLATE does that I copy
1. One open event scheduler. Benchmarks and agents each add events through an adapter.
2. A hybrid simulated clock: real time while the agent works, idle gaps skipped. Month-long scenarios run in seconds.
3. A proxy in front of every model call that records usage.
4. Head-to-head comparison of memory configurations on the same scenario.

## What I leave out
Real LLMs and GPUs, the seven ported benchmarks, post-training, log probabilities, in-container proxying.
The model is a deterministic mock, so results show the scheduler and harness mechanics, not model quality.
Memory configs are toy baselines I wrote. They say nothing about any real harness.

## What I add from my own background (backend reliability)
- SQLite-backed event store, so a crash resumes without replaying finished events.
- Idempotency keys: the same event key is never inserted or run twice.
- Retry with exponential backoff in simulated time, then a dead-letter state.
- Fault injection (`--flaky`) to exercise retries during the run.

## Layout
- clock.py: HybridClock (busy time counts, idle gaps skip)
- events.py / store.py: Event, SQLite store (events, notes, kv)
- scheduler.py: heap scheduler, dedup, retry, DLQ, resume
- proxy.py: ModelProxy + MockModel, JSONL call log
- memory.py: none / recency / keyword / selective
- agent.py: AgentAdapter (session_start/stop, cron, observe, answer)
- benchmark.py: multi-session recall benchmark adapter
- run.py: CLI, comparison table, report

## Done when
- Tests pass: clock skipping, dedup, retry then DLQ, crash-resume, end-to-end.
- `python -m mini_sclate.run` compares four memory configs on a 30-day scenario and writes results/report.md.
- README credits the paper and says what is and is not replicated.
