"""
Every result the README quotes for the worked example.

Run with `python3 run.py reproduce iot4cows`, or one experiment with
`--only <name>`. Each writes into outputs/<name>/, which nothing run by hand
touches, and every file there records the configuration that produced it.

One configuration for the whole site
------------------------------------
Every experiment below uses the study's own settings: 30 runs per point,
the 27-point node grid from 3 to 300, 3600 s simulated, seed 99 and 2000
bootstrap replicates. That is deliberate. The same quantity, SF8 capacity
with no shadowing, used to be quoted as 61.8, 61.7, 62.0, 62.3 and 62.6,
each from a run with a different grid or repetition count. With one
configuration it is one number wherever it appears, and a difference
between two rows of a table can be attributed to what the rows change.

The exceptions are stated where they occur: the propagation sweep finds
capacity by bisection rather than on the grid, and the validation ladder and
the intercept check evaluate a few fixed node counts.
"""
from loracap.reproduce import Experiment, Variant

# The study's own settings, stated here rather than inherited so that a
# change to study.py cannot move a quoted number without this file saying so.
CANONICAL = dict(
    n_runs=30,
    sim_time_s=3600.0,
    base_seed=99,
)
GRID = (3, 4, 5, 6, 7, 8, 10, 12, 14, 17, 20, 23, 28, 33, 39, 46,
        54, 65, 77, 91, 108, 128, 152, 180, 213, 253, 300)

EXPERIMENTS = [
    Experiment(
        name="headline",
        kind="run",
        description=("Capacity at the three legal 125 kHz data rates for a "
                     "32-byte payload in US915: SF7 optimistic, SF8 deployed, "
                     "SF9 conservative."),
        node_counts=GRID,
        scenarios=("SF7", "SF8", "SF9"),
        figure=True,
        **CANONICAL,
    ),
    Experiment(
        name="sweep",
        kind="sweep",
        description=("Capacity of SF8 across the default exponent bracket, "
                     "which is what `run.py sweep iot4cows` gives a user "
                     "with no arguments."),
        options=dict(scenario="SF8", low=2.0, high=3.5, steps=7),
        **CANONICAL,
    ),
    Experiment(
        name="intercept",
        kind="intercept",
        description=("Shifting the path-loss intercept moves every node's "
                     "received power equally, so while the site is covered "
                     "the DER must not move at all."),
        # The middle of the study's grid, which is what `sweep
        # --check-intercept` picks when no node count is given.
        options=dict(scenario="SF8", n_nodes=39,
                     offsets_db=(-10.0, -5.0, 0.0, 5.0)),
        **CANONICAL,
    ),
    Experiment(
        name="compare_exponent",
        kind="compare",
        description=("Fitted model against rural's published median exponent, "
                     "keeping the measured intercept: what the exponent "
                     "alone is worth."),
        node_counts=GRID,
        scenarios=("SF7", "SF8", "SF9"),
        options=dict(variant="exponent_only", terrain="rural"),
        **CANONICAL,
    ),
    Experiment(
        name="compare_anchored",
        kind="compare",
        description=("Fitted model against a fully assumed one: rural's "
                     "median exponent with the intercept anchored so the "
                     "slowest simulated rate just reaches the site edge, "
                     "which is the position of a deployer with no "
                     "measurements."),
        node_counts=GRID,
        scenarios=("SF7", "SF8", "SF9"),
        options=dict(variant="terrain", terrain="rural"),
        **CANONICAL,
    ),
    Experiment(
        name="shadowing",
        kind="run",
        description=("Log-normal shadowing drawn once per node, at zero, at "
                     "4 dB, at the unbinned field residual of 7.41 dB, and "
                     "at 10 dB, for a fixed rate and the two adaptive "
                     "scenarios."),
        node_counts=GRID,
        scenarios=("SF8", "MULTI", "ADR"),
        variants=(
            Variant("sigma_0", "σ = 0 dB", {"shadowing_sigma_db": 0.0}),
            Variant("sigma_4", "σ = 4 dB", {"shadowing_sigma_db": 4.0}),
            Variant("sigma_7.41", "σ = 7.41 dB", {"shadowing_sigma_db": 7.41}),
            Variant("sigma_10", "σ = 10 dB", {"shadowing_sigma_db": 10.0}),
        ),
        tables=("pivot", "fleet", "losses"),
        **CANONICAL,
    ),
    Experiment(
        name="adr",
        kind="run",
        description=("Fixed SF8, ideal assignment (MULTI), and steady-state "
                     "ADR with and without power control, so the margin's "
                     "effect and power control's effect are measured "
                     "separately."),
        node_counts=GRID,
        scenarios=("SF8", "MULTI", "ADR"),
        variants=(
            Variant("base", "base"),
            # An empty offset list leaves ADR choosing a data rate with its
            # margin but never reducing power, which isolates the margin.
            Variant("margin_only", "ADR, margin only",
                    {"tx_power_offsets_db": ()}, scenarios=("ADR",)),
        ),
        tables=("detail",),
        **CANONICAL,
    ),
    Experiment(
        name="receiver",
        kind="run",
        description=("The two receiver rules side by side: LoRaSim's, where "
                     "power decides at any offset, and the lock rule, where "
                     "the receiver stays on the packet it synchronised to "
                     "first (design item 13). Same site, same seed, so the "
                     "difference between rows is the rule."),
        node_counts=GRID,
        scenarios=("SF8", "MULTI", "ADR"),
        # The two rules at their defaults, one panel each. The threshold and
        # power-control variants stay in the table, since a panel per
        # variant would bury the one comparison the figure exists for.
        figure=True,
        figure_panels=("lorasim", "lock"),
        variants=(
            Variant("lorasim", "LoRaSim rule"),
            Variant("lock", "lock rule", {"receiver_model": "lock"}),
            # ADR without power control under each rule. Item 9 found power
            # control costs capacity by equalising received powers, which
            # under LoRaSim's rule loses both packets of an equal-power pair.
            # Under the lock rule the first of such a pair survives, so
            # whether that finding holds is measured here, not assumed.
            Variant("lorasim_margin_only", "LoRaSim rule, ADR margin only",
                    {"tx_power_offsets_db": ()}, scenarios=("ADR",)),
            Variant("lock_margin_only", "lock rule, ADR margin only",
                    {"receiver_model": "lock", "tx_power_offsets_db": ()},
                    scenarios=("ADR",)),
        ) + tuple(
            # The capture threshold is an assumption under both rules: the
            # measurements bracket it between about 0 and 6 dB without
            # placing it. Whether power control's sign under each rule
            # survives a lower threshold is therefore measured too.
            Variant(f"{rule}_thr{thr:g}{suffix}",
                    f"{label}, {thr:g} dB threshold{tail}",
                    {"receiver_model": rule, "capture_threshold_db": thr,
                     **extra},
                    scenarios=("ADR",))
            for rule, label in (("lorasim", "LoRaSim rule"),
                                ("lock", "lock rule"))
            for thr in (1.0, 3.0)
            for suffix, tail, extra in (
                ("", "", {}),
                ("_margin_only", ", ADR margin only",
                 {"tx_power_offsets_db": ()}))
        ),
        tables=("detail", "losses"),
        **CANONICAL,
    ),
    Experiment(
        name="inter_sf",
        kind="run",
        description=("Spreading factors that are not perfectly orthogonal "
                     "(design item 14). Croce et al.'s measured rejection "
                     "table against the engine's orthogonal default, for "
                     "the two adaptive scenarios and ADR without power "
                     "control, under both receiver rules. Same site, same "
                     "seed, so the difference between paired rows is the "
                     "table."),
        node_counts=GRID,
        scenarios=("MULTI", "ADR"),
        variants=tuple(
            Variant(f"{rule}{tag}{suffix}", f"{label}{tail}{text}",
                    {**rule_over, **table_over, **extra},
                    scenarios=scen)
            for rule, label, rule_over in (
                ("lorasim", "LoRaSim rule", {}),
                ("lock", "lock rule", {"receiver_model": "lock"}))
            for tag, text, table_over in (
                ("_orthogonal", ", orthogonal SFs", {}),
                ("_croce", ", Croce rejection",
                 {"inter_sf_rejection": "CROCE2020_SX1272"}))
            for suffix, tail, extra, scen in (
                ("", "", {}, ()),
                # Without power control the received powers keep their full
                # spread, so near nodes on a fast data rate can bury far ones
                # on a slow one. That is the case the table can change.
                ("_margin_only", ", ADR margin only",
                 {"tx_power_offsets_db": ()}, ("ADR",)))
        ),
        tables=("detail", "losses"),
        **CANONICAL,
    ),
    Experiment(
        name="inter_sf_threshold",
        kind="run",
        description=("Croce et al.'s rejection table at the 1 and 3 dB "
                     "same-SF thresholds, under both receiver rules, for "
                     "ADR with and without power control (design item 17). "
                     "The orthogonal counterparts of every row are in "
                     "experiment `receiver`, at the same seed and grid."),
        node_counts=GRID,
        scenarios=("ADR",),
        variants=tuple(
            Variant(f"{rule}_croce_thr{thr:g}{suffix}",
                    f"{label}, Croce rejection, {thr:g} dB threshold{tail}",
                    {"receiver_model": rule, "capture_threshold_db": thr,
                     "inter_sf_rejection": "CROCE2020_SX1272", **extra})
            for rule, label in (("lorasim", "LoRaSim rule"),
                                ("lock", "lock rule"))
            for thr in (1.0, 3.0)
            for suffix, tail, extra in (
                ("", "", {}),
                ("_margin_only", ", ADR margin only",
                 {"tx_power_offsets_db": ()}))
        ),
        tables=("detail", "losses"),
        **CANONICAL,
    ),
    Experiment(
        name="multi_threshold",
        kind="run",
        description=("MULTI at the 1 and 3 dB same-SF thresholds under both "
                     "receiver rules, so that the margin's gain over MULTI "
                     "can be read at those thresholds against the ADR rows "
                     "of `receiver` and `inter_sf_threshold` (design item "
                     "17). No rejection table: at this site MULTI puts every "
                     "node on SF7, where the table has nothing to act on."),
        node_counts=GRID,
        scenarios=("MULTI",),
        variants=tuple(
            Variant(f"{rule}_thr{thr:g}", f"{label}, {thr:g} dB threshold",
                    {"receiver_model": rule, "capture_threshold_db": thr})
            for rule, label in (("lorasim", "LoRaSim rule"),
                                ("lock", "lock rule"))
            for thr in (1.0, 3.0)
        ),
        tables=("detail",),
        **CANONICAL,
    ),
    Experiment(
        name="lock_refined",
        kind="run",
        description=("The lock rule with its two refinements of design item "
                     "18, one at a time and together: Eigner's per-SF "
                     "survival table for the locked packet, and recapture "
                     "during its header. The unrefined lock rule's rows are "
                     "in experiment `receiver`, at the same seed and grid."),
        node_counts=GRID,
        scenarios=("SF8", "MULTI", "ADR"),
        variants=tuple(
            Variant(f"lock_{tag}{suffix}", f"lock rule, {text}{tail}",
                    {"receiver_model": "lock", **over, **extra}, scenarios=scen)
            for tag, text, over in (
                ("survival", "Eigner survival",
                 {"lock_survival": "EIGNER2021_SX1301"}),
                ("recapture", "header recapture", {"header_recapture": True}),
                ("both", "Eigner survival and header recapture",
                 {"lock_survival": "EIGNER2021_SX1301",
                  "header_recapture": True}))
            for suffix, tail, extra, scen in (
                ("", "", {}, ()),
                ("_margin_only", ", ADR margin only",
                 {"tx_power_offsets_db": ()}, ("ADR",)))
        ),
        tables=("detail",),
        **CANONICAL,
    ),
    Experiment(
        name="inter_sf_eigner",
        kind="run",
        description=("Rejection between spreading factors with Eigner's "
                     "table, measured on an SX1301 concentrator, in place "
                     "of Croce et al.'s, measured on an SX1272 node radio "
                     "(design item 19). ADR with and without power "
                     "control under both receiver rules. The Croce and "
                     "orthogonal counterparts of every row are in "
                     "experiment `inter_sf`, at the same seed and grid. "
                     "MULTI is left out: at this site it puts every node on "
                     "SF7, where neither table has anything to act on."),
        node_counts=GRID,
        scenarios=("ADR",),
        variants=tuple(
            Variant(f"{rule}_eigner{suffix}",
                    f"{label}, Eigner rejection{tail}",
                    {"inter_sf_rejection": "EIGNER2021_SX1301", **rule_over,
                     **extra})
            for rule, label, rule_over in (
                ("lorasim", "LoRaSim rule", {}),
                ("lock", "lock rule", {"receiver_model": "lock"}))
            for suffix, tail, extra in (
                ("", "", {}),
                ("_margin_only", ", ADR margin only",
                 {"tx_power_offsets_db": ()}))
        ),
        tables=("detail", "losses"),
        **CANONICAL,
    ),
    Experiment(
        name="validation_lock",
        kind="validate",
        description=("The degeneracy ladder under the lock rule. One more "
                     "rung swaps the rule back to LoRaSim's, and the "
                     "first-come configuration must land on exp(-G)."),
        node_counts=(10, 30, 60, 100, 200),
        overrides={"receiver_model": "lock"},
        options=dict(scenario="SF8"),
        figure=True,
        **CANONICAL,
    ),
    Experiment(
        name="validation",
        kind="validate",
        description=("The degeneracy ladder: switch off, one at a time, each "
                     "mechanism pure ALOHA lacks, and check the engine walks "
                     "down onto exp(-2G)."),
        node_counts=(10, 30, 60, 100, 200),
        options=dict(scenario="SF8"),
        figure=True,
        **CANONICAL,
    ),
]
