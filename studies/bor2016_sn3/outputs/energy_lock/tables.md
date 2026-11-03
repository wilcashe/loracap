### bor2016_sn3 / energy_lock

The energy comparison above under the lock receiver rule (design items 13 and 17). Energy per extracted message depends on how many packets get through, so it depends on the rule too. Same seed and grid as `energy`, so the two tables differ only by the rule.

| N | MULTI vs SF12 | ADR vs SF12 |
|---|---|---|
| 40 | -75% | -24% |
| 64 | -75% | -24% |
| 100 | -76% | -26% |
| 200 | -79% | -31% |

- Mean transmit-power reduction under MULTI: 0.0 dB, averaged over those N.
- Mean transmit-power reduction under ADR: 0.1 dB, averaged over those N.
- Transmit energy per run under SF12: N = 40: 1391.5 J, N = 64: 2228.8 J, N = 100: 3486.7 J, N = 200: 6967.4 J.
- At a 1000 s interval with 2 uA of sleep draw, transmitting is 96.7% of the average current under SF12. Sleep overtakes it past 8.1 h.

*Source: experiment `energy_lock` of `studies/bor2016_sn3/experiments.py`, 15 runs per point, N = 40, 64, 100, 200, 200000 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/bor2016_sn3/outputs/energy_lock/`. Regenerate with `python3 run.py reproduce bor2016_sn3 --only energy_lock`.*
