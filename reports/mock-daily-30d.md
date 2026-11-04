Scenario: daily mode, 30 simulated days, seed 0, flaky cron rate 0.0, model mock

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| none | 0.23 | 0.00 | 30/30 | 120 | 2640 | 0 | 0 | 0.00/0.0 | 30.0 | 0.20 | 12,702,503x |
| recency | 0.29 | 0.27 | 30/30 | 120 | 6200 | 0 | 0 | 0.00/0.0 | 30.0 | 0.24 | 10,753,961x |
| keyword | 1.00 | 1.00 | 30/30 | 120 | 3345 | 0 | 0 | 0.00/0.0 | 30.0 | 0.26 | 9,985,618x |
| selective | 1.00 | 1.00 | 30/30 | 120 | 3265 | 0 | 0 | 0.00/0.0 | 30.0 | 0.25 | 10,371,694x |
| capped | 0.64 | 0.67 | 30/30 | 120 | 3095 | 0 | 0 | 0.00/0.0 | 30.0 | 0.22 | 12,020,938x |
| capped+selective | 1.00 | 1.00 | 30/30 | 120 | 3720 | 0 | 0 | 0.00/0.0 | 30.0 | 0.26 | 10,110,998x |
