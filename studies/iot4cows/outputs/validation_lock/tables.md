### iot4cows / validation_lock

The degeneracy ladder under the lock rule. One more rung swaps the rule back to LoRaSim's, and the first-come configuration must land on exp(-G).

| N | G | full model | lorasim rule | no demod limit | single channel | no capture | no preamble | ALOHA |
|---|---|---|---|---|---|---|---|---|
| 10 | 0.110 | 0.9852 | 0.9787 | 0.9787 | 0.8399 | 0.8118 | 0.8045 | 0.8032 |
| 30 | 0.329 | 0.9534 | 0.9385 | 0.9385 | 0.6079 | 0.5313 | 0.5185 | 0.5182 |
| 60 | 0.657 | 0.9083 | 0.8806 | 0.8806 | 0.3876 | 0.2822 | 0.2685 | 0.2685 |
| 100 | 1.096 | 0.8530 | 0.8117 | 0.8117 | 0.2280 | 0.1218 | 0.1122 | 0.1118 |
| 200 | 2.191 | 0.7254 | 0.6631 | 0.6636 | 0.0892 | 0.0146 | 0.0125 | 0.0125 |

What each mechanism is worth at N = 200, as the DER it adds:

- receiver lock: +0.0624 (0.7254 with it, 0.6631 without)
- demodulator limit: -0.0006 (0.6631 with it, 0.6636 without)
- multiple channels: +0.5744 (0.6636 with it, 0.0892 without)
- capture effect: +0.0746 (0.0892 with it, 0.0146 without)
- preamble allowance: +0.0021 (0.0146 with it, 0.0125 without)
- residual against ALOHA: -0.0000

The receiver lock is checked for no direction: it saves the first of two equal-power packets and loses both when the later one is stronger, so its sign depends on the site.

The lock rule's own bound, on one channel with no capture and no preamble allowance:

| N | first-come | exp(-G) |
|---|---|---|
| 10 | 0.8969 | 0.8962 |
| 30 | 0.7200 | 0.7199 |
| 60 | 0.5181 | 0.5182 |
| 100 | 0.3347 | 0.3343 |
| 200 | 0.1118 | 0.1118 |

Verdict: directions hold, 5 of 5 points within 3 standard errors of the bound. 5 of 5 first-come points within 3 standard errors of exp(-G). PASS.

*Source: experiment `validation_lock` of `studies/iot4cows/experiments.py`, 30 runs per point, N = 10, 30, 60, 100, 200, 3600 s simulated, seed 99. Data in `studies/iot4cows/outputs/validation_lock/`. Regenerate with `python3 run.py reproduce iot4cows --only validation_lock`.*
