"""
The reproduction of Bor et al.'s Experiment Set 1, configuration SN3, and
the energy results computed on it.

Run with `python3 run.py reproduce bor2016_sn3`. The settings are the
study's own, which are the paper's, stated here so a change to study.py
cannot move a quoted number without this file saying so.
"""
from loracap.reproduce import Experiment

COMMON = dict(n_runs=15, sim_time_s=200_000.0, base_seed=99)

EXPERIMENTS = [
    Experiment(
        name="headline",
        kind="run",
        description="SN3, coding rate 4/5: capacity at DER = 0.9.",
        node_counts=(10, 20, 30, 40, 50, 55, 60, 64, 70, 80, 90, 100, 120,
                     150, 200, 250, 300),
        scenarios=("SF12",),
        figure=True,
        # What the capacity above is read against. None of the three is
        # produced here, which is why they are marks and not curves.
        #   52.3  LoRaSim itself (github.com/mcbor/lorasim, ported to
        #         Python 3) at these settings, run outside this repository.
        #         See study.py, "WHAT THIS REPRODUCTION FOUND".
        #   64    Bor et al. (2016), abstract, body and findings.
        #   120   Bor et al. (2016), caption of Figure 4, for the same
        #         configuration.
        figure_marks=((52.3, "LoRaSim, external run"),
                      (64.0, "Bor et al., text"),
                      (120.0, "Bor et al., Fig. 4 caption")),
        **COMMON,
    ),
    Experiment(
        name="energy",
        kind="run",
        description=("Energy per extracted message for ideal assignment "
                     "(MULTI) and steady-state ADR against fixed SF12, in "
                     "EU868, the comparison Bor et al. make for their "
                     "network energy consumption."),
        node_counts=(40, 64, 100, 200),
        scenarios=("SF12", "MULTI", "ADR"),
        overrides=dict(
            # The study simulates SF12 only, as SN3 does. The adaptive
            # scenarios need the whole EU868 range to choose from.
            spreading_factors=(7, 8, 9, 10, 11, 12),
            # ASSUMED, not sourced: the illustrative sleep draw and battery
            # the README's energy example uses. They do not affect energy
            # per message. They decide only the transmit share of the
            # average current and the interval at which sleep overtakes
            # transmission, and those two figures inherit the assumption.
            sleep_current_ua=2.0,
            battery_capacity_mah=2400.0,
        ),
        options=dict(energy_reference="SF12", energy_nodes=(40, 64, 100, 200)),
        tables=("energy",),
        **COMMON,
    ),
    Experiment(
        name="energy_lock",
        kind="run",
        description=("The energy comparison above under the lock receiver "
                     "rule (design items 13 and 17). Energy per extracted "
                     "message depends on how many packets get through, so "
                     "it depends on the rule too. Same seed and grid as "
                     "`energy`, so the two tables differ only by the rule."),
        node_counts=(40, 64, 100, 200),
        scenarios=("SF12", "MULTI", "ADR"),
        overrides=dict(
            spreading_factors=(7, 8, 9, 10, 11, 12),
            # The same ASSUMED sleep draw and battery as `energy`, kept so the
            # two tables stay comparable line by line.
            sleep_current_ua=2.0,
            battery_capacity_mah=2400.0,
            receiver_model="lock",
        ),
        options=dict(energy_reference="SF12", energy_nodes=(40, 64, 100, 200)),
        tables=("energy",),
        **COMMON,
    ),
]
