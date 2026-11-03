"""
The reproduction of Bor et al.'s Experiment Set 1, configuration SN1.

Run with `python3 run.py reproduce bor2016_sn1`. The settings are the
study's own, which are the paper's, stated here so a change to study.py
cannot move the quoted number without this file saying so.
"""
from loracap.reproduce import Experiment

EXPERIMENTS = [
    Experiment(
        name="headline",
        kind="run",
        description="SN1, coding rate 4/8: capacity at DER = 0.9.",
        n_runs=15,
        sim_time_s=200_000.0,
        base_seed=99,
        node_counts=(10, 20, 30, 40, 50, 55, 60, 64, 70, 80, 90, 100, 120,
                     150, 200, 250, 300),
        scenarios=("SF12",),
        figure=True,
    ),
]
