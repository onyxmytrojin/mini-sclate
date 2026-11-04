Scenario: hard mode, 30 simulated days, seed 0, flaky cron rate 0.0, model claude-haiku-5-5 via Claude Code

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| none | 0.00 | 0.00 | 0/0 | 20 | 5294 | 0 | 0 | 0.00/36.8 | 30.0 | 56.25 | 46,019x |
| recency | 0.00 | 0.00 | 0/0 | 20 | 7114 | 0 | 0 | 0.00/33.0 | 30.0 | 52.80 | 49,022x |
| overlap | 0.90 | 0.00 | 0/0 | 20 | 7219 | 0 | 0 | 0.00/37.6 | 30.0 | 57.61 | 44,928x |
| capped-overlap | 0.05 | 0.00 | 0/0 | 20 | 7241 | 0 | 0 | 0.00/36.5 | 30.0 | 57.35 | 45,132x |
| full | 0.95 | 0.00 | 0/0 | 20 | 42454 | 0 | 0 | 0.00/57.1 | 30.0 | 76.89 | 33,662x |
