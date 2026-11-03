### iot4cows / receiver

The two receiver rules side by side: LoRaSim's, where power decides at any offset, and the lock rule, where the receiver stays on the packet it synchronised to first (design item 13). Same site, same seed, so the difference between rows is the rule.

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| LoRaSim rule | SF8 | 61.8 | [61.1, 62.6] | 25.0 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| LoRaSim rule | MULTI | 114.9 | [113.9, 115.9] | 28.2 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| LoRaSim rule | ADR | 145.1 | [143.1, 147.4] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule | SF8 | 81.7 | [81.1, 82.2] | 26.8 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| lock rule | MULTI | 151.1 | [150.0, 152.3] | 29.4 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule | ADR | 275.1 | [272.6, 277.5] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, ADR margin only | ADR | 170.8 | [168.9, 172.6] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, ADR margin only | ADR | 246.2 | [243.1, 249.9] | 27.2 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, 1 dB threshold | ADR | 167.1 | [164.9, 169.2] | 7.0 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, 1 dB threshold, ADR margin only | ADR | 236.6 | [235.1, 238.1] | 27.2 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, 3 dB threshold | ADR | 145.5 | [143.5, 147.9] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, 3 dB threshold, ADR margin only | ADR | 195.9 | [194.4, 197.3] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, 1 dB threshold | ADR | 249.4 | [246.4, 252.7] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, 1 dB threshold, ADR margin only | ADR | 210.8 | [207.6, 214.4] | 27.1 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, 3 dB threshold | ADR | 274.2 | [271.7, 276.7] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, 3 dB threshold, ADR margin only | ADR | 228.7 | [225.4, 231.7] | 27.1 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

| Configuration | Scenario | At N | Weak signal | Collided | CI width |
|---|---|---|---|---|---|
| LoRaSim rule | SF8 | 65 | 0.00% | 10.49% | 1.6 |
| LoRaSim rule | MULTI | 108 | 0.00% | 9.45% | 2.0 |
| LoRaSim rule | ADR | 152 | 0.00% | 10.46% | 4.3 |
| lock rule | SF8 | 77 | 0.00% | 9.45% | 1.1 |
| lock rule | MULTI | 152 | 0.00% | 10.06% | 2.3 |
| lock rule | ADR | 253 | 0.00% | 9.22% | 4.9 |
| LoRaSim rule, ADR margin only | ADR | 180 | 0.00% | 10.49% | 3.7 |
| lock rule, ADR margin only | ADR | 253 | 0.00% | 10.24% | 6.8 |
| LoRaSim rule, 1 dB threshold | ADR | 180 | 0.00% | 10.71% | 4.3 |
| LoRaSim rule, 1 dB threshold, ADR margin only | ADR | 253 | 0.00% | 10.63% | 3.0 |
| LoRaSim rule, 3 dB threshold | ADR | 152 | 0.00% | 10.43% | 4.4 |
| LoRaSim rule, 3 dB threshold, ADR margin only | ADR | 180 | 0.00% | 9.23% | 2.9 |
| lock rule, 1 dB threshold | ADR | 253 | 0.00% | 10.12% | 6.2 |
| lock rule, 1 dB threshold, ADR margin only | ADR | 213 | 0.00% | 10.09% | 6.8 |
| lock rule, 3 dB threshold | ADR | 253 | 0.00% | 9.25% | 5.0 |
| lock rule, 3 dB threshold, ADR margin only | ADR | 213 | 0.00% | 9.34% | 6.3 |

Losses are shares of transmitted packets at the simulated node count nearest each capacity.

*Source: experiment `receiver` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/receiver/`. Regenerate with `python3 run.py reproduce iot4cows --only receiver`.*
