### iot4cows / validation

The degeneracy ladder: switch off, one at a time, each mechanism pure ALOHA lacks, and check the engine walks down onto exp(-2G).

| N | G | full model | no demod limit | single channel | no capture | no preamble | ALOHA |
|---|---|---|---|---|---|---|---|
| 10 | 0.110 | 0.9787 | 0.9787 | 0.8399 | 0.8118 | 0.8045 | 0.8032 |
| 30 | 0.329 | 0.9385 | 0.9385 | 0.6079 | 0.5313 | 0.5185 | 0.5182 |
| 60 | 0.657 | 0.8806 | 0.8806 | 0.3876 | 0.2822 | 0.2685 | 0.2685 |
| 100 | 1.096 | 0.8117 | 0.8117 | 0.2280 | 0.1218 | 0.1122 | 0.1118 |
| 200 | 2.191 | 0.6631 | 0.6636 | 0.0892 | 0.0146 | 0.0125 | 0.0125 |

What each mechanism is worth at N = 200, as the DER it adds:

- demodulator limit: -0.0006 (0.6631 with it, 0.6636 without)
- multiple channels: +0.5744 (0.6636 with it, 0.0892 without)
- capture effect: +0.0746 (0.0892 with it, 0.0146 without)
- preamble allowance: +0.0021 (0.0146 with it, 0.0125 without)
- residual against ALOHA: -0.0000

Verdict: directions hold, 5 of 5 points within 3 standard errors of the bound. PASS.

*Source: experiment `validation` of `studies/iot4cows/experiments.py`, 30 runs per point, N = 10, 30, 60, 100, 200, 3600 s simulated, seed 99. Data in `studies/iot4cows/outputs/validation/`. Regenerate with `python3 run.py reproduce iot4cows --only validation`.*
