### iot4cows / saturation

Where the gateway stops delivering more traffic. Capacity is where the DER falls below the threshold, a requirement on the share delivered. Past it the network still delivers more messages per hour for a while, until losses grow faster than the traffic offered. The grid is carried on to 3000 nodes to find that peak, under the study's own receiver rule, capture threshold and orthogonal spreading factors.

| Scenario | Capacity at DER = 0.9 | 95% CI | Most delivered per hour | At N | Collided at the peak | No free demodulator at the peak | No free demodulator at N max |
|---|---|---|---|---|---|---|---|
| SF8 | 49.9 | [49.2, 50.5] | 42,445 | 417 (354 to 491) | 52.5% | 5.1% | 76.6% (N = 3000) |
| MULTI | 88.0 | [87.1, 89.0] | 75,577 | 805 (683 to 949) | 54.1% | 6.8% | 60.0% (N = 3000) |
| ADR | 111.4 | [108.5, 113.8] | 82,583 | 805 (683 to 949) | 43.1% | 14.2% | 68.1% (N = 3000) |

Delivered per hour is packets transmitted times DER, both means over the runs, scaled from the simulated time to an hour. The peak is the simulated node count that delivers the most, so the true maximum lies between the neighbouring node counts given in brackets. It carries no interval, because transmitted packets are saved as a mean and not run by run. Losses are shares of the packets transmitted. A packet refused for want of a demodulator is counted there only, never also as collided.

*Source: experiment `saturation` of `studies/iot4cows/experiments.py`, 30 runs per point, 41 node counts from 3 to 3000, 3600 s simulated, seed 99, 2000 bootstrap replicates. Data in `studies/iot4cows/outputs/saturation/`. Regenerate with `python3 run.py reproduce iot4cows --only saturation`.*
