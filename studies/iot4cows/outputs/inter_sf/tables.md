### iot4cows / inter_sf

Spreading factors that are not perfectly orthogonal (design item 14). Croce et al.'s measured rejection table against the engine's orthogonal default, for the two adaptive scenarios and ADR without power control, under both receiver rules. Same site, same seed, so the difference between paired rows is the table.

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| LoRaSim rule, orthogonal SFs | MULTI | 114.9 | [113.9, 115.9] | 28.2 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| LoRaSim rule, orthogonal SFs | ADR | 145.1 | [143.1, 147.4] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, ADR margin only, orthogonal SFs | ADR | 170.8 | [168.9, 172.6] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Croce rejection | MULTI | 114.9 | [113.9, 115.9] | 28.2 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| LoRaSim rule, Croce rejection | ADR | 145.1 | [143.1, 147.4] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, ADR margin only, Croce rejection | ADR | 153.2 | [151.4, 155.0] | 25.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, orthogonal SFs | MULTI | 151.1 | [150.0, 152.3] | 29.4 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, orthogonal SFs | ADR | 275.1 | [272.6, 277.5] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, ADR margin only, orthogonal SFs | ADR | 246.2 | [243.1, 249.9] | 27.2 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection | MULTI | 151.1 | [150.0, 152.3] | 29.4 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, Croce rejection | ADR | 275.1 | [272.6, 277.5] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, ADR margin only, Croce rejection | ADR | 211.6 | [208.6, 215.1] | 27.1 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

| Configuration | Scenario | At N | Weak signal | Collided | of which another SF | CI width |
|---|---|---|---|---|---|---|
| LoRaSim rule, orthogonal SFs | MULTI | 108 | 0.00% | 9.45% | off | 2.0 |
| LoRaSim rule, orthogonal SFs | ADR | 152 | 0.00% | 10.46% | off | 4.3 |
| LoRaSim rule, ADR margin only, orthogonal SFs | ADR | 180 | 0.00% | 10.49% | off | 3.7 |
| LoRaSim rule, Croce rejection | MULTI | 108 | 0.00% | 9.45% | 0.00% | 2.0 |
| LoRaSim rule, Croce rejection | ADR | 152 | 0.00% | 10.46% | 0.00% | 4.3 |
| LoRaSim rule, ADR margin only, Croce rejection | ADR | 152 | 0.00% | 9.92% | 0.99% | 3.6 |
| lock rule, orthogonal SFs | MULTI | 152 | 0.00% | 10.06% | off | 2.3 |
| lock rule, orthogonal SFs | ADR | 253 | 0.00% | 9.22% | off | 4.9 |
| lock rule, ADR margin only, orthogonal SFs | ADR | 253 | 0.00% | 10.24% | off | 6.8 |
| lock rule, Croce rejection | MULTI | 152 | 0.00% | 10.06% | 0.00% | 2.3 |
| lock rule, Croce rejection | ADR | 253 | 0.00% | 9.22% | 0.00% | 4.9 |
| lock rule, ADR margin only, Croce rejection | ADR | 213 | 0.00% | 10.05% | 1.42% | 6.5 |

Losses are shares of transmitted packets at the simulated node count nearest each capacity.
"Of which another SF" counts collided packets that an overlap with another spreading factor took, alone or together with a same-SF overlap. "Off" marks a configuration with orthogonal spreading factors.

*Source: experiment `inter_sf` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/inter_sf/`. Regenerate with `python3 run.py reproduce iot4cows --only inter_sf`.*
