### iot4cows / compare_anchored

Fitted model against a fully assumed one: rural's median exponent with the intercept anchored so the slowest simulated rate just reaches the site edge, which is the position of a deployer with no measurements.

| Model | SF7 | SF8 | SF9 |
|---|---|---|---|
| fitted (field) | 114.9 [113.9, 115.9] | 61.8 [61.1, 62.6] | 33.9 [33.0, 34.7] |
| assumed (rural) | no crossing - | 20.4 [3.4, 23.9] | 36.8 [36.2, 37.4] |

Reach as a multiple of the site radius:

- fitted (field): SF7 1.90, SF8 2.48, SF9 3.23
- assumed (rural): SF7 0.68, SF8 0.82, SF9 1.00

*Source: experiment `compare_anchored` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/compare_anchored/`. Regenerate with `python3 run.py reproduce iot4cows --only compare_anchored`.*
