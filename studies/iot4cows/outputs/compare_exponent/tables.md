### iot4cows / compare_exponent

Fitted model against rural's published median exponent, keeping the measured intercept: what the exponent alone is worth.

| Model | SF7 | SF8 | SF9 |
|---|---|---|---|
| fitted (field) | 88.0 [87.1, 89.1] | 49.9 [49.3, 50.5] | 26.3 [25.6, 27.1] |
| exponent only (rural) | 69.9 [64.1, 74.4] | 54.3 [53.5, 55.0] | 28.8 [28.0, 29.5] |

Reach as a multiple of the site radius:

- fitted (field): SF7 1.90, SF8 2.48, SF9 3.23
- exponent only (rural): SF7 0.88, SF8 1.07, SF9 1.30

*Source: experiment `compare_exponent` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/compare_exponent/`. Regenerate with `python3 run.py reproduce iot4cows --only compare_exponent`.*
