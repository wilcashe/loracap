### iot4cows / shadowing

Log-normal shadowing drawn once per node, at zero, at 4 dB, at the unbinned field residual of 7.41 dB, and at 10 dB, for a fixed rate and the two adaptive scenarios.

| Configuration | SF8 | MULTI | ADR | Excluded, worst case |
|---|---|---|---|---|
| σ = 0 dB | 49.9 [49.3, 50.5] | 88.0 [87.1, 89.1] | 111.4 [108.4, 113.7] | 0.0% |
| σ = 4 dB | 53.0 [52.1, 54.2] | 95.6 [94.3, 96.7] | 115.0 [113.5, 116.6] | 0.2% |
| σ = 7.41 dB | 44.8 [36.5, 48.1] | 112.8 [111.2, 114.2] | 115.2 [113.7, 116.6] | 4.0% |
| σ = 10 dB | 4.9 [3.6, 21.6] | 126.0 [123.9, 128.5] | 118.3 [116.4, 120.4] | 6.7% |

| Configuration | Scenario | Capacity, `der` | Capacity, `der_fleet` | Excluded, worst case |
|---|---|---|---|---|
| σ = 0 dB | SF8 | 49.9 | 49.9 | 0.0% |
| σ = 0 dB | MULTI | 88.0 | 88.0 | 0.0% |
| σ = 0 dB | ADR | 111.4 | 111.4 | 0.0% |
| σ = 4 dB | SF8 | 53.0 | 53.0 | 0.0% |
| σ = 4 dB | MULTI | 95.6 | 95.5 | 0.2% |
| σ = 4 dB | ADR | 115.0 | 114.8 | 0.2% |
| σ = 7.41 dB | SF8 | 44.8 | 44.8 | 0.0% |
| σ = 7.41 dB | MULTI | 112.8 | 99.7 | 4.0% |
| σ = 7.41 dB | ADR | 115.2 | 102.0 | 4.0% |
| σ = 10 dB | SF8 | 4.9 | 4.9 | 0.0% |
| σ = 10 dB | MULTI | 126.0 | 69.6 | 6.7% |
| σ = 10 dB | ADR | 118.3 | 63.6 | 6.7% |

| Configuration | Scenario | At N | Weak signal | Collided | CI width |
|---|---|---|---|---|---|
| σ = 0 dB | SF8 | 46 | 0.00% | 9.28% | 1.3 |
| σ = 0 dB | MULTI | 91 | 0.00% | 10.33% | 2.0 |
| σ = 0 dB | ADR | 108 | 0.00% | 9.74% | 5.3 |
| σ = 4 dB | SF8 | 54 | 0.13% | 10.07% | 2.1 |
| σ = 4 dB | MULTI | 91 | 0.00% | 9.56% | 2.4 |
| σ = 4 dB | ADR | 108 | 0.00% | 9.42% | 3.1 |
| σ = 7.41 dB | SF8 | 46 | 2.48% | 7.63% | 11.6 |
| σ = 7.41 dB | MULTI | 108 | 0.00% | 9.62% | 3.0 |
| σ = 7.41 dB | ADR | 108 | 0.00% | 9.43% | 2.9 |
| σ = 10 dB | SF8 | 5 | 9.21% | 0.95% | 18.0 |
| σ = 10 dB | MULTI | 128 | 0.00% | 10.15% | 4.6 |
| σ = 10 dB | ADR | 128 | 0.00% | 10.74% | 3.9 |

Losses are shares of transmitted packets at the simulated node count nearest each capacity.

*Source: experiment `shadowing` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/shadowing/`. Regenerate with `python3 run.py reproduce iot4cows --only shadowing`.*
