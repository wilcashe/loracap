### iot4cows / intercept

Shifting the path-loss intercept moves every node's received power equally, so while the site is covered the DER must not move at all.

| Intercept shift | L(d0) | DER | Weak-signal losses |
|---|---|---|---|
| -10 dB | 120.30 dB | 0.935174 | 0 |
| -5 dB | 125.30 dB | 0.935174 | 0 |
| +0 dB | 130.30 dB | 0.935174 | 0 |
| +5 dB | 135.30 dB | 0.935174 | 0 |

Largest DER difference 0.00e+00, SF8 at N = 39. Invariant: yes.

*Source: experiment `intercept` of `studies/iot4cows/experiments.py`, 30 runs per point, N = 39, 3600 s simulated, seed 99. Data in `studies/iot4cows/outputs/intercept/`. Regenerate with `python3 run.py reproduce iot4cows --only intercept`.*
