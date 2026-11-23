### iot4cows / compare_anchored

Fitted model against a fully assumed one: rural's median exponent with the intercept anchored so the slowest simulated rate just reaches the site edge, which is the position of a deployer with no measurements.

| Model | SF7 | SF8 | SF9 |
|---|---|---|---|
| fitted (field) | 88.0 [87.1, 89.1] | 49.9 [49.3, 50.5] | 26.3 [25.6, 27.1] |
| assumed (rural) | no crossing - | 18.2 [3.3, 21.1] | 28.8 [28.0, 29.5] |

Reach as a multiple of the site radius:

- fitted (field): SF7 1.90, SF8 2.48, SF9 3.23
- assumed (rural): SF7 0.68, SF8 0.82, SF9 1.00

*Source: experiment `compare_anchored` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/compare_anchored/`. Regenerate with `python3 run.py reproduce iot4cows --only compare_anchored`.*
