### iot4cows / inter_sf_eigner

Rejection between spreading factors with Eigner's table, measured on an SX1301 concentrator, in place of Croce et al.'s, measured on an SX1272 node radio (design item 19). ADR with and without power control under both receiver rules. The Croce and orthogonal counterparts of every row are in experiment `inter_sf`, at the same seed and grid. MULTI is left out: at this site it puts every node on SF7, where neither table has anything to act on.

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| LoRaSim rule, Eigner rejection | ADR | 145.1 | [143.1, 147.4] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| LoRaSim rule, Eigner rejection, ADR margin only | ADR | 153.0 | [151.1, 154.7] | 25.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Eigner rejection | ADR | 275.1 | [272.6, 277.5] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Eigner rejection, ADR margin only | ADR | 211.1 | [208.1, 214.6] | 27.1 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

| Configuration | Scenario | At N | Weak signal | Collided | of which another SF | CI width |
|---|---|---|---|---|---|---|
| LoRaSim rule, Eigner rejection | ADR | 152 | 0.00% | 10.46% | 0.00% | 4.3 |
| LoRaSim rule, Eigner rejection, ADR margin only | ADR | 152 | 0.00% | 9.94% | 1.01% | 3.6 |
| lock rule, Eigner rejection | ADR | 253 | 0.00% | 9.22% | 0.00% | 4.9 |
| lock rule, Eigner rejection, ADR margin only | ADR | 213 | 0.00% | 10.08% | 1.44% | 6.5 |

Losses are shares of transmitted packets at the simulated node count nearest each capacity.
"Of which another SF" counts collided packets that an overlap with another spreading factor took, alone or together with a same-SF overlap. "Off" marks a configuration with orthogonal spreading factors.

*Source: experiment `inter_sf_eigner` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/inter_sf_eigner/`. Regenerate with `python3 run.py reproduce iot4cows --only inter_sf_eigner`.*
