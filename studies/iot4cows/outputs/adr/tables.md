### iot4cows / adr

Fixed SF8, ideal assignment (MULTI), and steady-state ADR with and without power control, so the margin's effect and power control's effect are measured separately.

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| base | SF8 | 61.8 | [61.1, 62.6] | 25.0 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| base | MULTI | 114.9 | [113.9, 115.9] | 28.2 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| base | ADR | 145.1 | [143.1, 147.4] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| ADR, margin only | ADR | 170.8 | [168.9, 172.6] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

*Source: experiment `adr` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/adr/`. Regenerate with `python3 run.py reproduce iot4cows --only adr`.*
