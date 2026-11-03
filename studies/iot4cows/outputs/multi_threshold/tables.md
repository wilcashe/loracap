### iot4cows / multi_threshold

MULTI at the 1 and 3 dB same-SF thresholds under both receiver rules, so that the margin's gain over MULTI can be read at those thresholds against the ADR rows of `receiver` and `inter_sf_threshold` (ROADMAP item 17). No rejection table: at this site MULTI puts every node on SF7, where the table has nothing to act on.

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| LoRaSim rule, 1 dB threshold | MULTI | 165.5 | [164.6, 166.4] | 29.4 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| LoRaSim rule, 3 dB threshold | MULTI | 137.8 | [136.8, 138.8] | 29.1 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, 1 dB threshold | MULTI | 129.4 | [128.6, 130.3] | 29.1 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, 3 dB threshold | MULTI | 138.5 | [137.8, 139.3] | 29.1 dB | 22.0 dBm | SF7 300.0 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

*Source: experiment `multi_threshold` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/multi_threshold/`. Regenerate with `python3 run.py reproduce iot4cows --only multi_threshold`.*
