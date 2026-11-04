# Paper vs this repo

Paper: SCLATE, arXiv 2609.32391. Section and table numbers refer to the paper.

| Paper element | Where in the paper | Here | Status |
|---|---|---|---|
| Open scheduler, pull-based sources polled with a DispatchContext | 3.1, Algorithm 1 | scheduler.py, events.py | Rebuilt (single-threaded) |
| Tie-break on (time, source_id) | Algorithm 1 line 9, 17 | scheduler.py | Rebuilt |
| Completed-fires registry H | Algorithm 1 | `ctx.completed` | Rebuilt, persisted in SQLite |
| Hybrid clock: flow while busy, jump when idle | 3.1 | clock.py | Rebuilt. Busy time counts at real speed, so live-API runs compress far less than mock runs |
| "Flow mode" mid-turn event arrival (events reach the agent while a turn runs) | Table 4 note, Table 7 (36% mid-turn) | none | Not replicated: each fire runs to completion |
| libfaketime so harness crons follow simulated time | 3.1, Fig. 8 | simulated date line in the prompt | Partial: only the prompt sees the date |
| EventChainSource | Table 5 | events.EventChainSource | Rebuilt (all prerequisites must complete) |
| AgentActionGatedSource | Table 5 | events.AgentActionGatedSource | Rebuilt (gates grading on `answered:<qid>`) |
| Session start/end, memory consolidation, cron sources | Table 5 | agent.sources() | Rebuilt as scheduled sources |
| AppStateConditionedSource, SidecarReadySource, UserInputSource (dynamic) | Table 5 | none | Not replicated |
| Effects: Deliver, RunHook, StartAgent, ShutdownAgent, SaveState, RestoreState | Table 6 | events.py constants | Rebuilt. AsyncReserve and AwaitWakeup not replicated |
| Independent grader, scheduler holds no grading logic | 3.2, Table 4 grading_policy | benchmark.py RunHook "grade" | Rebuilt (toy exact-match grader) |
| save_state / restore_state, integrity token, refuse torn saves | Table 4 | snapshot.py | Rebuilt for a toy memory |
| Agent process dies between sessions | 3.2, 4.2 | ShutdownAgent wipes working context and in-process memory | Rebuilt |
| Multi-session recall protocol (split history over consecutive days, stop process between sessions, ask in last session) | 4.2 | benchmark mode "history" | Rebuilt on synthetic facts, not LongMemEval or PersonaMem |
| Capped native memory rejecting new facts when full (Hermes) | 4.2 | memory.CappedMemory | Mechanism imitated, my own cap and my own toy |
| Added memory vs native memory comparison | 4.2, Table 1 | capped vs capped+selective | Structure copied, components are toy |
| Scheduler validation: delivery lateness (0.9 s median, 2.0 s max vs GAIA-2) | 4.1, Fig. 3a, Table 7 | scheduler.lateness_stats() | Metric rebuilt. No GAIA-2 comparison |
| Capture proxy recording tokens and log probabilities of every model call, in-container | 3, 3.3 | proxy.ModelProxy (tokens only, in-process) | Partial |
| Containers, orchestrator, rollout engine, trajectory building | 3.3 | none | Not replicated |
| Harnesses (Claude Code, Hermes, Codex), memories (Mem0, Hindsight, GBrain), 10 models, 7 benchmarks | 4 | none | Not replicated |
| Post-training (GRPO, Qwen3.5-4B) | 4.3 | none | Not replicated |

## Added here, not in the paper
SQLite fire registry with crash resume, retry with exponential backoff in simulated time, dead-letter state,
fault injection (`--flaky`) on the consolidation cron.
