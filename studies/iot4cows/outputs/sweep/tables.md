### iot4cows / sweep

Capacity of SF8 across the default exponent bracket, which is what `run.py sweep iot4cows` gives a user with no arguments.

| Exponent | Reach | Covers site | Capacity |
|---|---|---|---|
| 2.00 | 3055 m | yes | 60.3 |
| 2.16 (this study) | 2371 m | yes | 62.0 |
| 2.25 | 2089 m | yes | 62.6 |
| 2.50 | 1542 m | yes | 64.2 |
| 2.75 | 1202 m | yes | 65.7 |
| 3.00 | 977 m | yes | 67.4 |
| 3.25 | 820 m | NO | 35.8 |
| 3.50 | 706 m | NO | no crossing |

While the site is covered, capacity spans 60.3 to 67.4, 12% of the lower value. Site radius 958 m, scenario SF8.

*Source: experiment `sweep` of `studies/iot4cows/experiments.py`, 30 runs per point, capacity by bisection on node count, 3600 s simulated, seed 99. Data in `studies/iot4cows/outputs/sweep/`. Regenerate with `python3 run.py reproduce iot4cows --only sweep`.*
