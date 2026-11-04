Scenario: hard mode, 30 simulated days, seed 0, flaky cron rate 0.0, model openai/gpt-oss-120b

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| extract+consolidate | 0.40 | 0.00 | 0/0 | 190 | 42968 | 20 | 7 | 0.00/197.3 | 30.0 | 621.54 | 4,165x |

WARNING: fires failed without fault injection. First error: RuntimeError('consolidation reply had no parseable lines; keeping the old memory')
