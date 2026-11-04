Scenario: daily mode, 20 simulated days, seed 0, flaky cron rate 0.0, model openai/gpt-oss-20b

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| none | 0.30 | 0.00 | 20/20 | 80 | 13440 | 0 | 0 | 0.00/6.2 | 20.0 | 212.33 | 8,124x |
| recency | 0.37 | 0.35 | 20/20 | 80 | 18632 | 0 | 0 | 0.00/6.0 | 20.0 | 215.66 | 7,999x |
| keyword | 1.00 | 1.00 | 20/20 | 80 | 14507 | 0 | 0 | 0.00/5.6 | 20.0 | 208.63 | 8,268x |
| selective | 1.00 | 1.00 | 20/20 | 80 | 14375 | 0 | 0 | 0.00/6.1 | 20.0 | 209.53 | 8,233x |
| capped | 0.82 | 0.85 | 20/20 | 80 | 14309 | 0 | 0 | 0.00/6.0 | 20.0 | 208.88 | 8,258x |
| capped+selective | 1.00 | 1.00 | 20/20 | 80 | 15244 | 0 | 0 | 0.00/6.8 | 20.0 | 213.25 | 8,089x |
