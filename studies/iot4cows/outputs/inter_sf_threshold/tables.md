### iot4cows / inter_sf_threshold

Croce et al.'s rejection table at the 1 and 3 dB same-SF thresholds, under both receiver rules, for ADR with and without power control (design item 17). The orthogonal counterparts of every row are in experiment `receiver`, at the same seed and grid.

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| LoRaSim rule, Croce rejection, 1 dB threshold | ADR | 129.6 | [127.0, 131.9] | 6.3 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Croce rejection, 1 dB threshold, ADR margin only | ADR | 159.8 | [158.0, 161.4] | 25.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Croce rejection, 3 dB threshold | ADR | 111.8 | [109.0, 114.0] | 5.5 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Croce rejection, 3 dB threshold, ADR margin only | ADR | 135.4 | [134.0, 136.7] | 25.7 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection, 1 dB threshold | ADR | 194.9 | [192.6, 197.1] | 7.0 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection, 1 dB threshold, ADR margin only | ADR | 144.0 | [142.0, 146.3] | 25.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection, 3 dB threshold | ADR | 214.8 | [211.7, 217.9] | 7.1 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection, 3 dB threshold, ADR margin only | ADR | 154.5 | [151.3, 157.4] | 25.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

| Configuration | Scenario | At N | Weak signal | Collided | of which another SF | CI width |
|---|---|---|---|---|---|---|
| LoRaSim rule, Croce rejection, 1 dB threshold | ADR | 128 | 0.00% | 9.88% | 0.00% | 5.0 |
| LoRaSim rule, Croce rejection, 1 dB threshold, ADR margin only | ADR | 152 | 0.00% | 9.53% | 1.24% | 3.3 |
| LoRaSim rule, Croce rejection, 3 dB threshold | ADR | 108 | 0.00% | 9.71% | 0.00% | 5.1 |
| LoRaSim rule, Croce rejection, 3 dB threshold, ADR margin only | ADR | 128 | 0.00% | 9.49% | 1.03% | 2.6 |
| lock rule, Croce rejection, 1 dB threshold | ADR | 180 | 0.00% | 9.25% | 0.00% | 4.5 |
| lock rule, Croce rejection, 1 dB threshold, ADR margin only | ADR | 152 | 0.00% | 10.55% | 1.24% | 4.4 |
| lock rule, Croce rejection, 3 dB threshold | ADR | 213 | 0.00% | 9.89% | 0.00% | 6.2 |
| lock rule, Croce rejection, 3 dB threshold, ADR margin only | ADR | 152 | 0.00% | 9.84% | 1.24% | 6.2 |

Losses are shares of transmitted packets at the simulated node count nearest each capacity.
"Of which another SF" counts collided packets that an overlap with another spreading factor took, alone or together with a same-SF overlap. "Off" marks a configuration with orthogonal spreading factors.

*Source: experiment `inter_sf_threshold` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/inter_sf_threshold/`. Regenerate with `python3 run.py reproduce iot4cows --only inter_sf_threshold`.*
