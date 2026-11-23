### iot4cows / inter_sf

Spreading factors that are not perfectly orthogonal (design item 14). Croce et al.'s measured rejection table against the engine's orthogonal default, for the two adaptive scenarios and ADR without power control, under both receiver rules. Same site, same seed, so the difference between paired rows is the table.

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| LoRaSim rule, orthogonal SFs | MULTI | 88.0 | [87.1, 89.1] | 27.8 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| LoRaSim rule, orthogonal SFs | ADR | 111.4 | [108.4, 113.7] | 5.5 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, ADR margin only, orthogonal SFs | ADR | 131.9 | [129.6, 133.8] | 25.7 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Croce rejection | MULTI | 88.0 | [87.1, 89.1] | 27.8 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| LoRaSim rule, Croce rejection | ADR | 111.4 | [108.4, 113.7] | 5.5 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, ADR margin only, Croce rejection | ADR | 118.7 | [117.4, 120.0] | 25.7 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, orthogonal SFs | MULTI | 116.9 | [116.2, 117.6] | 28.2 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, orthogonal SFs | ADR | 215.5 | [212.2, 218.5] | 7.1 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, ADR margin only, orthogonal SFs | ADR | 192.5 | [189.8, 194.9] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Croce rejection | MULTI | 116.9 | [116.2, 117.6] | 28.2 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, Croce rejection | ADR | 215.5 | [212.2, 218.5] | 7.1 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, ADR margin only, Croce rejection | ADR | 165.6 | [163.3, 167.8] | 25.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

| Configuration | Scenario | At N | Weak signal | Collided | of which another SF | CI width |
|---|---|---|---|---|---|---|
| LoRaSim rule, orthogonal SFs | MULTI | 91 | 0.00% | 10.33% | off | 2.0 |
| LoRaSim rule, orthogonal SFs | ADR | 108 | 0.00% | 9.74% | off | 5.3 |
| LoRaSim rule, ADR margin only, orthogonal SFs | ADR | 128 | 0.00% | 9.73% | off | 4.2 |
| LoRaSim rule, Croce rejection | MULTI | 91 | 0.00% | 10.33% | 0.00% | 2.0 |
| LoRaSim rule, Croce rejection | ADR | 108 | 0.00% | 9.74% | 0.00% | 5.3 |
| LoRaSim rule, ADR margin only, Croce rejection | ADR | 128 | 0.00% | 10.69% | 1.03% | 2.6 |
| lock rule, orthogonal SFs | MULTI | 108 | 0.00% | 9.28% | off | 1.4 |
| lock rule, orthogonal SFs | ADR | 213 | 0.00% | 9.86% | off | 6.3 |
| lock rule, ADR margin only, orthogonal SFs | ADR | 180 | 0.00% | 9.36% | off | 5.1 |
| lock rule, Croce rejection | MULTI | 108 | 0.00% | 9.28% | 0.00% | 1.4 |
| lock rule, Croce rejection | ADR | 213 | 0.00% | 9.86% | 0.00% | 6.3 |
| lock rule, ADR margin only, Croce rejection | ADR | 152 | 0.00% | 9.21% | 1.24% | 4.5 |

Losses are shares of transmitted packets at the simulated node count nearest each capacity.
"Of which another SF" counts collided packets that an overlap with another spreading factor took, alone or together with a same-SF overlap. "Off" marks a configuration with orthogonal spreading factors.

*Source: experiment `inter_sf` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/inter_sf/`. Regenerate with `python3 run.py reproduce iot4cows --only inter_sf`.*
