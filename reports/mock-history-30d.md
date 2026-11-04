Scenario: history mode, 30 simulated days, seed 0, flaky cron rate 0.0, model mock

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| none | 0.00 | 0.00 | 0/0 | 20 | 540 | 0 | 0 | 0.00/0.0 | 30.0 | 0.14 | 18,683,939x |
| recency | 0.00 | 0.00 | 0/0 | 20 | 1140 | 0 | 0 | 0.00/0.0 | 30.0 | 0.18 | 14,256,531x |
| keyword | 1.00 | 0.00 | 0/0 | 20 | 670 | 0 | 0 | 0.00/0.0 | 30.0 | 0.18 | 14,122,708x |
| selective | 1.00 | 0.00 | 0/0 | 20 | 640 | 0 | 0 | 0.00/0.0 | 30.0 | 0.18 | 14,581,213x |
| capped | 0.40 | 0.00 | 0/0 | 20 | 605 | 0 | 0 | 0.00/0.0 | 30.0 | 0.14 | 17,851,872x |
| capped+selective | 1.00 | 0.00 | 0/0 | 20 | 705 | 0 | 0 | 0.00/0.0 | 30.0 | 0.20 | 12,792,614x |
