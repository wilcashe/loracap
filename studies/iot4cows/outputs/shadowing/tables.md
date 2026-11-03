### iot4cows / shadowing

Log-normal shadowing drawn once per node, at zero, at 4 dB, at the unbinned field residual of 7.41 dB, and at 10 dB, for a fixed rate and the two adaptive scenarios.

| Configuration | SF8 | MULTI | ADR | Excluded, worst case |
|---|---|---|---|---|
| σ = 0 dB | 61.8 [61.1, 62.6] | 114.9 [113.9, 115.9] | 145.1 [143.1, 147.4] | 0.0% |
| σ = 4 dB | 66.3 [65.0, 67.3] | 124.7 [123.4, 126.2] | 149.5 [146.3, 153.3] | 0.2% |
| σ = 7.41 dB | 53.4 [49.0, 57.5] | 145.5 [144.0, 147.4] | 148.2 [146.3, 150.6] | 4.0% |
| σ = 10 dB | 4.9 [3.6, 25.9] | 162.6 [160.5, 164.5] | 150.7 [148.2, 153.9] | 6.7% |

| Configuration | Scenario | Capacity, `der` | Capacity, `der_fleet` | Excluded, worst case |
|---|---|---|---|---|
| σ = 0 dB | SF8 | 61.8 | 61.8 | 0.0% |
| σ = 0 dB | MULTI | 114.9 | 114.9 | 0.0% |
| σ = 0 dB | ADR | 145.1 | 145.1 | 0.0% |
| σ = 4 dB | SF8 | 66.3 | 66.3 | 0.0% |
| σ = 4 dB | MULTI | 124.7 | 124.7 | 0.2% |
| σ = 4 dB | ADR | 149.5 | 148.7 | 0.2% |
| σ = 7.41 dB | SF8 | 53.4 | 53.4 | 0.0% |
| σ = 7.41 dB | MULTI | 145.5 | 128.3 | 4.0% |
| σ = 7.41 dB | ADR | 148.2 | 129.9 | 4.0% |
| σ = 10 dB | SF8 | 4.9 | 4.9 | 0.0% |
| σ = 10 dB | MULTI | 162.6 | 96.2 | 6.7% |
| σ = 10 dB | ADR | 150.7 | 88.8 | 6.7% |

| Configuration | Scenario | At N | Weak signal | Collided | CI width |
|---|---|---|---|---|---|
| σ = 0 dB | SF8 | 65 | 0.00% | 10.49% | 1.6 |
| σ = 0 dB | MULTI | 108 | 0.00% | 9.45% | 2.0 |
| σ = 0 dB | ADR | 152 | 0.00% | 10.46% | 4.3 |
| σ = 4 dB | SF8 | 65 | 0.05% | 9.76% | 2.3 |
| σ = 4 dB | MULTI | 128 | 0.00% | 10.25% | 2.9 |
| σ = 4 dB | ADR | 152 | 0.00% | 10.14% | 7.0 |
| σ = 7.41 dB | SF8 | 54 | 2.89% | 7.21% | 8.6 |
| σ = 7.41 dB | MULTI | 152 | 0.00% | 10.45% | 3.4 |
| σ = 7.41 dB | ADR | 152 | 0.00% | 10.24% | 4.3 |
| σ = 10 dB | SF8 | 5 | 9.21% | 0.78% | 22.3 |
| σ = 10 dB | MULTI | 152 | 0.00% | 9.42% | 3.9 |
| σ = 10 dB | ADR | 152 | 0.00% | 10.09% | 5.7 |

Losses are shares of transmitted packets at the simulated node count nearest each capacity.

*Source: experiment `shadowing` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/shadowing/`. Regenerate with `python3 run.py reproduce iot4cows --only shadowing`.*
