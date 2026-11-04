Scenario: hard mode, 30 simulated days, seed 0, flaky cron rate 0.0, model openai/gpt-oss-120b

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| extract | 0.95 | 0.00 | 0/0 | 140 | 30540 | 0 | 0 | 0.00/34.9 | 30.0 | 308.55 | 8,389x |
