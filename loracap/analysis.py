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
    rng = random.Random(seed)
    lo_q, hi_q = (1 - conf) / 2, 1 - (1 - conf) / 2
    out = {}
    for scen, rs in by.items():
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


def write_capacity(study_name, capacity, threshold, root=None):
    path = os.path.join(output_dir(study_name, root), CAPACITY_JSON)
    with open(path, "w") as f:
        json.dump({"der_threshold": threshold, "capacity": capacity}, f, indent=2)
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
