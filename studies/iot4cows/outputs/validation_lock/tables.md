### iot4cows / validation_lock

The degeneracy ladder under the lock rule. One more rung swaps the rule back to LoRaSim's, and the first-come configuration must land on exp(-G).

| N | G | full model | lorasim rule | no demod limit | single channel | no capture | no preamble | ALOHA |
|---|---|---|---|---|---|---|---|---|
| 10 | 0.089 | 0.9879 | 0.9825 | 0.9825 | 0.8692 | 0.8454 | 0.8386 | 0.8368 |
| 30 | 0.267 | 0.9618 | 0.9497 | 0.9497 | 0.6682 | 0.6014 | 0.5867 | 0.5859 |
| 60 | 0.535 | 0.9249 | 0.9022 | 0.9022 | 0.4603 | 0.3609 | 0.3438 | 0.3433 |
| 100 | 0.891 | 0.8791 | 0.8446 | 0.8446 | 0.2925 | 0.1831 | 0.1688 | 0.1683 |
| 200 | 1.782 | 0.7717 | 0.7170 | 0.7172 | 0.1214 | 0.0331 | 0.0282 | 0.0283 |

What each mechanism is worth at N = 200, as the DER it adds:

- receiver lock: +0.0547 (0.7717 with it, 0.7170 without)
- demodulator limit: -0.0002 (0.7170 with it, 0.7172 without)
- multiple channels: +0.5958 (0.7172 with it, 0.1214 without)
- capture effect: +0.0883 (0.1214 with it, 0.0331 without)
- preamble allowance: +0.0049 (0.0331 with it, 0.0282 without)
- residual against ALOHA: -0.0002

The receiver lock is checked for no direction: it saves the first of two equal-power packets and loses both when the later one is stronger, so its sign depends on the site.

The lock rule's own bound, on one channel with no capture and no preamble allowance:

| N | first-come | exp(-G) |
|---|---|---|
| 10 | 0.9156 | 0.9148 |
| 30 | 0.7661 | 0.7655 |
| 60 | 0.5861 | 0.5859 |
| 100 | 0.4110 | 0.4103 |
| 200 | 0.1684 | 0.1683 |

Verdict: directions hold, 5 of 5 points within 3 standard errors of the bound. 5 of 5 first-come points within 3 standard errors of exp(-G). PASS.

*Source: experiment `validation_lock` of `studies/iot4cows/experiments.py`, 30 runs per point, N = 10, 30, 60, 100, 200, 3600 s simulated, seed 99. Data in `studies/iot4cows/outputs/validation_lock/`. Regenerate with `python3 run.py reproduce iot4cows --only validation_lock`.*
