### iot4cows / receiver

The two receiver rules side by side: LoRaSim's, where power decides at any offset, and the lock rule, where the receiver stays on the packet it synchronised to first (design item 13). Same site, same seed, so the difference between rows is the rule.

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| LoRaSim rule | SF8 | 49.9 | [49.3, 50.5] | 22.8 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| LoRaSim rule | MULTI | 88.0 | [87.1, 89.1] | 27.8 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| LoRaSim rule | ADR | 111.4 | [108.4, 113.7] | 5.5 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule | SF8 | 65.8 | [64.9, 66.5] | 25.0 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| lock rule | MULTI | 116.9 | [116.2, 117.6] | 28.2 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule | ADR | 215.5 | [212.2, 218.5] | 7.1 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, ADR margin only | ADR | 131.9 | [129.6, 133.8] | 25.7 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, ADR margin only | ADR | 192.5 | [189.8, 194.9] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, 1 dB threshold | ADR | 129.6 | [127.0, 131.9] | 6.3 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, 1 dB threshold, ADR margin only | ADR | 184.2 | [182.6, 185.6] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, 3 dB threshold | ADR | 111.8 | [109.0, 114.0] | 5.5 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, 3 dB threshold, ADR margin only | ADR | 152.0 | [150.2, 153.9] | 25.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, 1 dB threshold | ADR | 194.9 | [192.6, 197.1] | 7.0 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, 1 dB threshold, ADR margin only | ADR | 163.5 | [160.6, 166.0] | 25.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, 3 dB threshold | ADR | 214.8 | [211.7, 217.9] | 7.1 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, 3 dB threshold, ADR margin only | ADR | 178.3 | [175.0, 181.8] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

| Configuration | Scenario | At N | Weak signal | Collided | CI width |
|---|---|---|---|---|---|
| LoRaSim rule | SF8 | 46 | 0.00% | 9.28% | 1.3 |
| LoRaSim rule | MULTI | 91 | 0.00% | 10.33% | 2.0 |
| LoRaSim rule | ADR | 108 | 0.00% | 9.74% | 5.3 |
| lock rule | SF8 | 65 | 0.00% | 9.89% | 1.6 |
| lock rule | MULTI | 108 | 0.00% | 9.28% | 1.4 |
| lock rule | ADR | 213 | 0.00% | 9.86% | 6.3 |
| LoRaSim rule, ADR margin only | ADR | 128 | 0.00% | 9.73% | 4.2 |
| lock rule, ADR margin only | ADR | 180 | 0.00% | 9.36% | 5.1 |
| LoRaSim rule, 1 dB threshold | ADR | 128 | 0.00% | 9.88% | 5.0 |
| LoRaSim rule, 1 dB threshold, ADR margin only | ADR | 180 | 0.00% | 9.77% | 3.1 |
| LoRaSim rule, 3 dB threshold | ADR | 108 | 0.00% | 9.71% | 5.1 |
| LoRaSim rule, 3 dB threshold, ADR margin only | ADR | 152 | 0.00% | 10.00% | 3.7 |
| lock rule, 1 dB threshold | ADR | 180 | 0.00% | 9.25% | 4.5 |
| lock rule, 1 dB threshold, ADR margin only | ADR | 152 | 0.00% | 9.36% | 5.3 |
| lock rule, 3 dB threshold | ADR | 213 | 0.00% | 9.89% | 6.2 |
| lock rule, 3 dB threshold, ADR margin only | ADR | 180 | 0.00% | 10.07% | 6.8 |

Losses are shares of transmitted packets at the simulated node count nearest each capacity.

*Source: experiment `receiver` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/receiver/`. Regenerate with `python3 run.py reproduce iot4cows --only receiver`.*
