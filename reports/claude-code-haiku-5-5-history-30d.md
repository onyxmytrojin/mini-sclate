Scenario: history mode, 30 simulated days, seed 0, flaky cron rate 0.0, model claude-haiku-5-5 via Claude Code

| config | accuracy | probe acc | probes run | model calls | prompt tokens | retries | dead | lateness p50/max (s) | sim days | wall s | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| none | 0.00 | 0.00 | 0/0 | 20 | 4400 | 0 | 0 | 0.00/444.6 | 30.0 | 468.34 | 5,527x |
| recency | 0.00 | 0.00 | 0/0 | 20 | 5840 | 0 | 0 | 0.00/450.7 | 30.0 | 474.60 | 5,454x |
| keyword | 1.00 | 0.00 | 0/0 | 20 | 4712 | 0 | 0 | 0.00/446.6 | 30.0 | 470.03 | 5,507x |
| selective | 1.00 | 0.00 | 0/0 | 20 | 4640 | 0 | 0 | 0.00/445.0 | 30.0 | 468.66 | 5,523x |
| capped | 0.40 | 0.00 | 0/0 | 20 | 4556 | 0 | 0 | 0.00/452.8 | 30.0 | 476.66 | 5,430x |
| capped+selective | 1.00 | 0.00 | 0/0 | 20 | 4796 | 0 | 0 | 0.00/443.6 | 30.0 | 467.46 | 5,537x |
