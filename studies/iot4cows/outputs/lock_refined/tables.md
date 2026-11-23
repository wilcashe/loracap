### iot4cows / lock_refined

The lock rule with its two refinements of design item 18, one at a time and together: Eigner's per-SF survival table for the locked packet, and recapture during its header. The unrefined lock rule's rows are in experiment `receiver`, at the same seed and grid.

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| lock rule, Eigner survival | SF8 | 53.6 | [53.0, 54.2] | 24.6 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| lock rule, Eigner survival | MULTI | 94.4 | [93.5, 95.2] | 27.8 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, Eigner survival | ADR | 147.7 | [145.6, 150.4] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Eigner survival, ADR margin only | ADR | 148.9 | [146.6, 151.7] | 25.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, header recapture | SF8 | 66.9 | [66.2, 67.6] | 25.0 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| lock rule, header recapture | MULTI | 118.8 | [118.1, 119.4] | 29.1 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, header recapture | ADR | 215.6 | [212.3, 218.6] | 7.1 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, header recapture, ADR margin only | ADR | 194.7 | [192.2, 197.2] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Eigner survival and header recapture | SF8 | 54.3 | [53.7, 54.9] | 24.6 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| lock rule, Eigner survival and header recapture | MULTI | 95.6 | [94.8, 96.4] | 27.8 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, Eigner survival and header recapture | ADR | 147.8 | [145.6, 150.5] | 6.4 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Eigner survival and header recapture, ADR margin only | ADR | 150.2 | [147.8, 153.0] | 25.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

*Source: experiment `lock_refined` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/lock_refined/`. Regenerate with `python3 run.py reproduce iot4cows --only lock_refined`.*
