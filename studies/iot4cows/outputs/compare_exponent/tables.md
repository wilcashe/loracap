### iot4cows / compare_exponent

Fitted model against rural's published median exponent, keeping the measured intercept: what the exponent alone is worth.

| Model | SF7 | SF8 | SF9 |
|---|---|---|---|
| fitted (field) | 114.9 [113.9, 115.9] | 61.8 [61.1, 62.6] | 33.9 [33.0, 34.7] |
| exponent only (rural) | 89.4 [83.7, 94.9] | 67.1 [66.3, 67.9] | 36.8 [36.2, 37.4] |

Reach as a multiple of the site radius:

- fitted (field): SF7 1.90, SF8 2.48, SF9 3.23
- exponent only (rural): SF7 0.88, SF8 1.07, SF9 1.30

*Source: experiment `compare_exponent` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/compare_exponent/`. Regenerate with `python3 run.py reproduce iot4cows --only compare_exponent`.*
