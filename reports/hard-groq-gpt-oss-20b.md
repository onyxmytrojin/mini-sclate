Scenario: hard mode, 30 simulated days, seed 0, flaky cron rate 0.0, model openai/gpt-oss-20b

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| none | 0.00 | 0.00 | 0/0 | 20 | 3945 | 0 | 0 | 0.00/189.9 | 30.0 | 203.95 | 12,691x |
| recency | 0.00 | 0.00 | 0/0 | 20 | 5245 | 0 | 0 | 0.00/11.2 | 30.0 | 25.35 | 102,109x |
| overlap | 0.90 | 0.00 | 0/0 | 20 | 5342 | 0 | 0 | 0.00/31.6 | 30.0 | 52.72 | 49,096x |
| capped-overlap | 0.05 | 0.00 | 0/0 | 20 | 5362 | 0 | 0 | 0.00/36.6 | 30.0 | 55.93 | 46,283x |
| full | 0.55 | 0.00 | 0/0 | 20 | 30645 | 0 | 0 | 0.00/162.3 | 30.0 | 192.54 | 13,443x |
