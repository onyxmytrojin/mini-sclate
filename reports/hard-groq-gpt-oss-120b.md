Scenario: hard mode, 30 simulated days, seed 0, flaky cron rate 0.0, model openai/gpt-oss-120b

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| none | 0.00 | 0.00 | 0/0 | 20 | 3945 | 0 | 0 | 0.00/0.6 | 30.0 | 10.20 | 253,796x |
| recency | 0.00 | 0.00 | 0/0 | 20 | 5245 | 0 | 0 | 0.00/15.5 | 30.0 | 31.77 | 81,480x |
| overlap | 0.90 | 0.00 | 0/0 | 20 | 5342 | 0 | 0 | 0.00/32.2 | 30.0 | 53.73 | 48,174x |
| capped-overlap | 0.05 | 0.00 | 0/0 | 20 | 5362 | 0 | 0 | 0.00/34.6 | 30.0 | 53.90 | 48,024x |
| full | 0.85 | 0.00 | 0/0 | 20 | 30645 | 0 | 0 | 0.00/155.9 | 30.0 | 182.86 | 14,155x |
