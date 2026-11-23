### iot4cows / adr

Fixed SF8, ideal assignment (MULTI), and steady-state ADR with and without power control, so the margin's effect and power control's effect are measured separately.

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| base | SF8 | 49.9 | [49.3, 50.5] | 22.8 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| base | MULTI | 88.0 | [87.1, 89.1] | 27.8 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| base | ADR | 111.4 | [108.4, 113.7] | 5.5 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| ADR, margin only | ADR | 131.9 | [129.6, 133.8] | 25.7 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

*Source: experiment `adr` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/adr/`. Regenerate with `python3 run.py reproduce iot4cows --only adr`.*
