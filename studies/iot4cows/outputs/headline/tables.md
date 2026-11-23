### iot4cows / headline

Capacity at the three legal 125 kHz data rates for a 32-byte payload in US915: SF7 optimistic, SF8 deployed, SF9 conservative.

| Scenario | Capacity at DER = 0.9 | 95% CI |
|---|---|---|
| SF7 | 88.0 | [87.1, 89.1] |
| SF8 | 49.9 | [49.3, 50.5] |
| SF9 | 26.3 | [25.6, 27.1] |

*Source: experiment `headline` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/headline/`. Regenerate with `python3 run.py reproduce iot4cows --only headline`.*
