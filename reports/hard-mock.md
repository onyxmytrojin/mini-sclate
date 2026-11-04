Scenario: hard mode, 30 simulated days, seed 0, flaky cron rate 0.0, model mock

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| none | 0.00 | 0.00 | 0/0 | 20 | 750 | 0 | 0 | 0.00/0.0 | 30.0 | 0.13 | 19,569,108x |
| recency | 0.00 | 0.00 | 0/0 | 20 | 1550 | 0 | 0 | 0.00/0.0 | 30.0 | 0.15 | 17,793,054x |
| overlap | 0.70 | 0.00 | 0/0 | 20 | 1614 | 0 | 0 | 0.00/0.0 | 30.0 | 0.17 | 14,817,503x |
| capped-overlap | 0.05 | 0.00 | 0/0 | 20 | 1634 | 0 | 0 | 0.00/0.0 | 30.0 | 0.16 | 16,679,297x |
| full | 0.70 | 0.00 | 0/0 | 20 | 16850 | 0 | 0 | 0.00/0.0 | 30.0 | 0.20 | 12,938,655x |
