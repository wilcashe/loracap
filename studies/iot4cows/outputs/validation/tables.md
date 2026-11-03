### iot4cows / validation

The degeneracy ladder: switch off, one at a time, each mechanism pure ALOHA lacks, and check the engine walks down onto exp(-2G).

| N | G | full model | no demod limit | single channel | no capture | no preamble | ALOHA |
|---|---|---|---|---|---|---|---|
| 10 | 0.089 | 0.9825 | 0.9825 | 0.8692 | 0.8454 | 0.8386 | 0.8368 |
| 30 | 0.267 | 0.9497 | 0.9497 | 0.6682 | 0.6014 | 0.5867 | 0.5859 |
| 60 | 0.535 | 0.9022 | 0.9022 | 0.4603 | 0.3609 | 0.3438 | 0.3433 |
| 100 | 0.891 | 0.8446 | 0.8446 | 0.2925 | 0.1831 | 0.1688 | 0.1683 |
| 200 | 1.782 | 0.7170 | 0.7172 | 0.1214 | 0.0331 | 0.0282 | 0.0283 |

What each mechanism is worth at N = 200, as the DER it adds:

- demodulator limit: -0.0002 (0.7170 with it, 0.7172 without)
- multiple channels: +0.5958 (0.7172 with it, 0.1214 without)
- capture effect: +0.0883 (0.1214 with it, 0.0331 without)
- preamble allowance: +0.0049 (0.0331 with it, 0.0282 without)
- residual against ALOHA: -0.0002

Verdict: directions hold, 5 of 5 points within 3 standard errors of the bound. PASS.

*Source: experiment `validation` of `studies/iot4cows/experiments.py`, 30 runs per point, N = 10, 30, 60, 100, 200, 3600 s simulated, seed 99. Data in `studies/iot4cows/outputs/validation/`. Regenerate with `python3 run.py reproduce iot4cows --only validation`.*
