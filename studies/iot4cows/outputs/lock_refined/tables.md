### iot4cows / lock_refined

The lock rule with its two refinements of design item 18, one at a time and together: Eigner's per-SF survival table for the locked packet, and recapture during its header. The unrefined lock rule's rows are in experiment `receiver`, at the same seed and grid.

| Configuration | Scenario | Capacity | 95% CI | RSSI spread | Mean power | Nodes per SF at N max |
|---|---|---|---|---|---|---|
| lock rule, Eigner survival | SF8 | 65.9 | [65.1, 66.7] | 25.0 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| lock rule, Eigner survival | MULTI | 122.6 | [121.9, 123.3] | 29.1 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, Eigner survival | ADR | 190.8 | [188.5, 192.8] | 7.0 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Eigner survival, ADR margin only | ADR | 192.2 | [190.1, 194.1] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, header recapture | SF8 | 83.4 | [82.9, 83.8] | 26.8 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| lock rule, header recapture | MULTI | 154.1 | [153.0, 155.2] | 29.4 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, header recapture | ADR | 275.2 | [272.8, 277.7] | 7.2 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, header recapture, ADR margin only | ADR | 250.0 | [246.8, 253.8] | 27.2 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Eigner survival and header recapture | SF8 | 67.1 | [66.4, 67.8] | 25.0 dB | 22.0 dBm | SF8 300.0 (N = 300) |
| lock rule, Eigner survival and header recapture | MULTI | 124.7 | [123.9, 125.5] | 29.1 dB | 22.0 dBm | SF7 300.0 (N = 300) |
| lock rule, Eigner survival and header recapture | ADR | 190.8 | [188.5, 192.9] | 7.0 dB | 18.1 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |
| lock rule, Eigner survival and header recapture, ADR margin only | ADR | 194.5 | [192.6, 196.4] | 26.9 dB | 22.0 dBm | SF7 219.7, SF8 65.6, SF9 14.7 (N = 300) |

RSSI spread is the largest range of received power within one spreading factor, and it and mean power are taken at the simulated node count nearest each capacity. Nodes per SF are means over the runs.

*Source: experiment `lock_refined` of `studies/iot4cows/experiments.py`, 30 runs per point, 27 node counts from 3 to 300, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/lock_refined/`. Regenerate with `python3 run.py reproduce iot4cows --only lock_refined`.*
