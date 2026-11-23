### iot4cows / sweep

Capacity of SF8 across the default exponent bracket, which is what `run.py sweep iot4cows` gives a user with no arguments.

| Exponent | Reach | Covers site | Capacity |
|---|---|---|---|
| 2.00 | 3055 m | yes | 49.0 |
| 2.16 (this study) | 2371 m | yes | 49.5 |
| 2.25 | 2089 m | yes | 49.8 |
| 2.50 | 1542 m | yes | 51.5 |
| 2.75 | 1202 m | yes | 53.2 |
| 3.00 | 977 m | yes | 54.7 |
| 3.25 | 820 m | NO | 31.0 |
| 3.50 | 706 m | NO | no crossing |

While the site is covered, capacity spans 49.0 to 54.7, 12% of the lower value. Site radius 958 m, scenario SF8.

*Source: experiment `sweep` of `studies/iot4cows/experiments.py`, 30 runs per point, capacity by bisection on node count, 3600 s simulated, seed 99. Data in `studies/iot4cows/outputs/sweep/`. Regenerate with `python3 run.py reproduce iot4cows --only sweep`.*
