Scenario: history mode, 30 simulated days, seed 0, flaky cron rate 0.0, model openai/gpt-oss-20b

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| none | 0.00 | 0.00 | 0/0 | 20 | 3580 | 0 | 0 | 0.00/0.6 | 30.0 | 10.16 | 254,639x |
| recency | 0.00 | 0.00 | 0/0 | 20 | 4900 | 0 | 0 | 0.00/15.0 | 30.0 | 30.51 | 84,841x |
| keyword | 1.00 | 0.00 | 0/0 | 20 | 3866 | 0 | 0 | 0.00/30.8 | 30.0 | 51.06 | 50,692x |
| selective | 1.00 | 0.00 | 0/0 | 20 | 3800 | 0 | 0 | 0.00/30.6 | 30.0 | 51.36 | 50,400x |
| capped | 0.40 | 0.00 | 0/0 | 20 | 3723 | 0 | 0 | 0.00/30.9 | 30.0 | 52.45 | 49,351x |
| capped+selective | 1.00 | 0.00 | 0/0 | 20 | 3943 | 0 | 0 | 0.00/30.4 | 30.0 | 51.27 | 50,490x |
