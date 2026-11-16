### iot4cows / saturation

Where the gateway stops delivering more traffic. Capacity is where the DER falls below the threshold, a requirement on the share delivered. Past it the network still delivers more messages per hour for a while, until losses grow faster than the traffic offered. The grid is carried on to 3000 nodes to find that peak, under the study's own receiver rule, capture threshold and orthogonal spreading factors.

| Scenario | Capacity at DER = 0.9 | 95% CI | Most delivered per hour | At N | Collided at the peak | No free demodulator at the peak | No free demodulator at N max |
|---|---|---|---|---|---|---|---|
| SF8 | 61.8 | [61.1, 62.7] | 52,682 | 579 (491 to 683) | 54.4% | 7.8% | 71.5% (N = 3000) |
| MULTI | 114.9 | [113.9, 115.9] | 97,612 | 949 (805 to 1118) | 52.1% | 5.0% | 50.2% (N = 3000) |
| ADR | 145.1 | [143.1, 147.5] | 105,739 | 949 (805 to 1118) | 41.7% | 11.9% | 60.5% (N = 3000) |

Delivered per hour is packets transmitted times DER, both means over the runs, scaled from the simulated time to an hour. The peak is the simulated node count that delivers the most, so the true maximum lies between the neighbouring node counts given in brackets. It carries no interval, because transmitted packets are saved as a mean and not run by run. Losses are shares of the packets transmitted. A packet refused for want of a demodulator is counted there only, never also as collided.

*Source: experiment `saturation` of `studies/iot4cows/experiments.py`, 30 runs per point, 41 node counts from 3 to 3000, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/saturation/`. Regenerate with `python3 run.py reproduce iot4cows --only saturation`.*
