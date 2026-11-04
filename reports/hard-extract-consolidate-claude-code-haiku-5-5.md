Scenario: hard mode, 30 simulated days, seed 0, flaky cron rate 0.0, model claude-haiku-5-5 via Claude Code

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| extract+consolidate | 0.95 | 0.00 | 0/0 | 170 | 53234 | 0 | 0 | 1.20/33.4 | 30.0 | 671.91 | 3,852x |
