### iot4cows / inter_sf_threshold

Croce et al.'s rejection table at the 1 and 3 dB same-SF thresholds, under both receiver rules, for ADR with and without power control (design item 17). The orthogonal counterparts of every row are in experiment `receiver`, at the same seed and grid.

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| LoRaSim rule, Croce rejection, 1 dB threshold | ADR | 167.1 | [164.9, 169.2] | 7.0 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Croce rejection, 1 dB threshold, ADR margin only | ADR | 204.7 | [203.2, 206.4] | 27.1 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Croce rejection, 3 dB threshold | ADR | 145.5 | [143.5, 147.9] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Croce rejection, 3 dB threshold, ADR margin only | ADR | 173.3 | [172.0, 174.6] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection, 1 dB threshold | ADR | 249.4 | [246.4, 252.7] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection, 1 dB threshold, ADR margin only | ADR | 184.8 | [182.1, 187.2] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection, 3 dB threshold | ADR | 274.2 | [271.7, 276.7] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection, 3 dB threshold, ADR margin only | ADR | 198.5 | [196.1, 201.0] | 27.1 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

| Configuration | Scenario | At N | Weak signal | Collided | of which another SF | CI width |
|---|---|---|---|---|---|---|
| LoRaSim rule, Croce rejection, 1 dB threshold | ADR | 180 | 0.00% | 10.71% | 0.00% | 4.3 |
| LoRaSim rule, Croce rejection, 1 dB threshold, ADR margin only | ADR | 213 | 0.00% | 10.37% | 1.42% | 3.2 |
| LoRaSim rule, Croce rejection, 3 dB threshold | ADR | 152 | 0.00% | 10.43% | 0.00% | 4.4 |
| LoRaSim rule, Croce rejection, 3 dB threshold, ADR margin only | ADR | 180 | 0.00% | 10.37% | 1.22% | 2.6 |
| lock rule, Croce rejection, 1 dB threshold | ADR | 253 | 0.00% | 10.12% | 0.00% | 6.2 |
| lock rule, Croce rejection, 1 dB threshold, ADR margin only | ADR | 180 | 0.00% | 9.75% | 1.22% | 5.1 |
| lock rule, Croce rejection, 3 dB threshold | ADR | 253 | 0.00% | 9.25% | 0.00% | 5.0 |
| lock rule, Croce rejection, 3 dB threshold, ADR margin only | ADR | 213 | 0.00% | 10.69% | 1.42% | 4.9 |

Losses are shares of transmitted packets at the simulated node count nearest each capacity.
"Of which another SF" counts collided packets that an overlap with another spreading factor took, alone or together with a same-SF overlap. "Off" marks a configuration with orthogonal spreading factors.

*Source: experiment `inter_sf_threshold` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/inter_sf_threshold/`. Regenerate with `python3 run.py reproduce iot4cows --only inter_sf_threshold`.*
