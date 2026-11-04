Scenario: hard mode, 30 simulated days, seed 0, flaky cron rate 0.0, model openai/gpt-oss-120b

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| extract+consolidate | 1.00 | 0.00 | 0/0 | 170 | 40582 | 0 | 0 | 0.00/64.0 | 30.0 | 555.87 | 4,657x |
