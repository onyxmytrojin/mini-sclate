Scenario: hard mode, 30 simulated days, seed 0, flaky cron rate 0.0, model openai/gpt-oss-20b

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| extract | 0.85 | 0.00 | 0/0 | 140 | 30500 | 22 | 0 | 0.00/7649.1 | 30.0 | 8380.71 | 309x |

WARNING: fires failed without fault injection. First error: <HTTPError 429: 'Too Many Requests'>
