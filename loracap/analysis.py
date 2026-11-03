#!/usr/bin/env python3
"""
loracap.analysis
=========================

Derives network capacity from the DER curve, with a confidence interval.

The capacity is the node count at which the mean DER crosses an operational
threshold. It is a derived quantity, not a measured one, so reporting it as a
single interpolated number would repeat one level down the very problem that
repeated runs were introduced to solve. The interval here comes from
resampling the per-run DER values at every node count, rebuilding the curve,
and re-deriving the crossing, over many bootstrap replicates.
"""
from __future__ import annotations

import json
import os
import random
from collections import defaultdict

from .study import output_dir

CAPACITY_JSON = "capacity.json"


def group_by_scenario(rows):
    by = defaultdict(list)
    for r in rows:
        by[r["scenario"]].append(r)
    for rs in by.values():
        rs.sort(key=lambda r: r["n_nodes"])
    return dict(by)


def crossing(node_counts, ders, threshold):
    """First downward crossing of `threshold`, linearly interpolated.

    Returns None when the curve never crosses, which happens if the node range
    is too narrow. The caller should widen node_counts rather than treat a
    missing crossing as a capacity.
    """
    for i in range(len(node_counts) - 1):
        y0, y1 = ders[i], ders[i + 1]
        if y0 >= threshold >= y1:
            x0, x1 = node_counts[i], node_counts[i + 1]
            if y0 == y1:
                return float(x0)
            return x0 + (y0 - threshold) / (y0 - y1) * (x1 - x0)
    return None


def capacity_with_ci(rows, threshold=0.9, n_boot=2000, seed=12345, conf=0.95):
    by = group_by_scenario(rows)
    lo_q, hi_q = (1 - conf) / 2, 1 - (1 - conf) / 2
    out = {}
    for scen, rs in by.items():
        # One stream per scenario. With a single stream shared across
        # scenarios, a scenario's interval depended on which scenarios were
        # resampled before it, so the same curve got a different interval in
        # a different table. Seeding from a string is deterministic.
        rng = random.Random(f"{seed}:{scen}")
        counts = [r["n_nodes"] for r in rs]
        point = crossing(counts, [r["der_mean"] for r in rs], threshold)
        if point is None:
            out[scen] = {
                "capacity": None, "ci_low": None, "ci_high": None,
                "note": "DER never crosses the threshold over the simulated node "
                        "range; widen node_counts.",
            }
            continue
        boot = []
        for _ in range(n_boot):
            curve = []
            for r in rs:
                runs = r["der_runs"]
                k = len(runs)
                curve.append(sum(runs[rng.randrange(k)] for _ in range(k)) / k)
            c = crossing(counts, curve, threshold)
            if c is not None:
                boot.append(c)
        boot.sort()
        if boot:
            lo = boot[int(lo_q * (len(boot) - 1))]
            hi = boot[int(hi_q * (len(boot) - 1))]
        else:
            lo = hi = None
        out[scen] = {
            "capacity": point, "ci_low": lo, "ci_high": hi,
            "n_bootstrap": len(boot),
        }
    return out


def write_capacity(study_name, capacity, threshold, root=None, out_dir=None,
                   provenance=None, fleet_capacity=None):
    out = out_dir or output_dir(study_name, root)
    os.makedirs(out, exist_ok=True)
    payload = {"der_threshold": threshold, "capacity": capacity}
    if fleet_capacity is not None:
        # Counting the nodes an adaptive scenario excluded as lost traffic.
        # Stored beside the headline figure because `run` reports both
        # whenever they diverge, and a reported number needs a file.
        payload["fleet_capacity"] = fleet_capacity
    if provenance is not None:
        payload["provenance"] = provenance
    path = os.path.join(out, CAPACITY_JSON)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return path


def format_capacity(capacity, threshold, conf=0.95) -> str:
    pct = int(round(conf * 100))
    lines = [f"Capacity at DER = {threshold}", ""]
    lines.append(f"  {'Scenario':<10}{'Nodes':>9}{f'{pct}% CI':>18}")
    for scen, c in capacity.items():
        if c["capacity"] is None:
            lines.append(f"  {scen:<10}{'n/a':>9}   {c.get('note', '')}")
            continue
        ci = f"[{c['ci_low']:.1f}, {c['ci_high']:.1f}]" if c["ci_low"] is not None else "-"
        lines.append(f"  {scen:<10}{c['capacity']:>9.1f}{ci:>18}")
    return "\n".join(lines)


def service_life(row, study, n_nodes=None):
    """Average current and battery service life for one node, from a result row.

    Transmit energy alone is not a service life, because the node also draws
    while idle, so this needs `sleep_current_ua` and returns None without it.

    Which term dominates is reported rather than assumed, as `transmit_share`,
    because it is not the same for every deployment. At a 1000 s interval with
    1.3 s of SF12 airtime, transmitting is about 97% of the average current.
    Stretch the interval to several hours and a few microamps of sleep draw
    overtakes it.

    Returns None when the study asks for no energy figure, or gives no sleep
    current, or no battery capacity.
    """
    energy = row.get("tx_energy_j_mean")
    if (energy is None or study.sleep_current_ua is None
            or study.battery_capacity_mah is None):
        return None
    nodes = n_nodes or row["n_nodes"]
    if not nodes or study.supply_voltage_v <= 0 or study.sim_time_s <= 0:
        return None

    # average transmit current per node, in mA
    joules_per_node = energy / nodes
    tx_ma = 1000.0 * joules_per_node / (study.supply_voltage_v * study.sim_time_s)
    sleep_ma = study.sleep_current_ua / 1000.0
    total_ma = tx_ma + sleep_ma
    if total_ma <= 0:
        return None
    hours = study.battery_capacity_mah / total_ma
    return {
        "n_nodes": nodes,
        "tx_current_ma": tx_ma,
        "sleep_current_ma": sleep_ma,
        "average_current_ma": total_ma,
        "transmit_share": tx_ma / total_ma,
        "service_life_days": hours / 24.0,
        "service_life_years": hours / 24.0 / 365.25,
    }
