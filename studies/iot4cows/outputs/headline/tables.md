### iot4cows / headline

Capacity at the three legal 125 kHz data rates for a 32-byte payload in US915: SF7 optimistic, SF8 deployed, SF9 conservative.

| Scenario | Capacity at DER = 0.9 | 95% CI |
|---|---|---|
| SF7 | 114.9 | [113.9, 115.9] |
| SF8 | 61.8 | [61.1, 62.6] |
| SF9 | 33.9 | [33.0, 34.7] |

*Source: experiment `headline` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/headline/`. Regenerate with `python3 run.py reproduce iot4cows --only headline`.*
