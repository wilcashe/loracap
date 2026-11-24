#!/usr/bin/env python3
"""
loracap.sitemap
===============

The site map (design item 31): where the nodes of one run sit, which
spreading factor each was given, and how far each spreading factor reaches.

It shows one placement, not an average over runs. That placement is the
first repetition of the highlighted scenario (or the first scenario) at one
node count, replayed with the seed `core.run_batch` gave that repetition, so
the map is that repetition exactly and not one like it. The node count is
the scenario's capacity, rounded to the nearest whole node, unless the study
sets `site_map_nodes`.

The placement is written to site_map.json beside results.json, and the
figure is drawn from that file. `run.py plot` therefore redraws the map
without simulating, and a later change to the code cannot alter a map that
was already written.
"""
from __future__ import annotations

import json
import math
import os
import random

from . import core
from .analysis import crossing, group_by_scenario
from .study import Study, output_dir

SITE_MAP_JSON = "site_map.json"
FIGURE_KIND = "site_map"


def first_repetition_seed(study: Study) -> int:
    """The seed of repetition 0 at every point of a study's grid.

    `core.run_batch` seeds repetition i with base_seed * 100_000 + i,
    whatever the scenario and node count, so this is the one to replay."""
    return study.base_seed * 100_000


def map_scenario(study: Study) -> str:
    return study.highlight_scenario or study.scenarios[0]


def map_node_count(study: Study, rows):
    """(n_nodes, nodes_from, capacity) for the map.

    `nodes_from` is "site_map_nodes" when the study fixes the count and
    "capacity" when it is the scenario's capacity. When the study fixes none
    and the scenario's mean DER never crosses the threshold, n_nodes is None:
    there is no capacity to show, and inventing a count would draw a map of a
    point the study never chose."""
    if study.site_map_nodes is not None:
        return study.site_map_nodes, "site_map_nodes", None
    rs = group_by_scenario(rows).get(map_scenario(study), [])
    cap = (crossing([r["n_nodes"] for r in rs], [r["der_mean"] for r in rs],
                    study.der_threshold) if rs else None)
    if cap is None:
        return None, None, None
    # Halves go up, as a reader rounds, rather than to the even number as
    # Python's round() does.
    return max(1, int(math.floor(cap + 0.5))), "capacity", cap


def snapshot(study: Study, scenario: str, n_nodes: int) -> dict:
    """The placement of the first repetition of `scenario` at `n_nodes`."""
    cfg = study.to_sim_config()
    seed = first_repetition_seed(study)
    xy = {}
    placed = core.place_nodes(cfg, n_nodes, scenario, random.Random(seed), xy)
    disc = cfg.placement == "disc"
    if disc:
        # A disc placement draws a distance only, because propagation here
        # depends on nothing else. These angles exist for the drawing alone
        # and come from a generator of their own, so they cannot touch the
        # run they illustrate.
        angles = random.Random(f"site map angles {seed}")
        for nid, d in placed["positions"]:
            a = angles.uniform(0.0, 2.0 * math.pi)
            xy[nid] = (d * math.cos(a), d * math.sin(a))

    nodes, per_sf, unreachable, below = [], {}, 0, 0
    for nid, d in placed["positions"]:
        sf = placed["node_sf"][nid]
        shadow = placed["node_shadow"][nid]
        x, y = xy[nid]
        if sf is None:
            # An adaptive scenario found no data rate for it: it never
            # transmits.
            tx, link = None, "unreachable"
            unreachable += 1
        else:
            tx = placed["node_tx"][nid]
            per_sf[str(sf)] = per_sf.get(str(sf), 0) + 1
            # Against the node's own link, shadowing included. Per-packet
            # fading is left out, as in the received-power spread: it moves
            # every packet differently and belongs to the run, not the map.
            heard = core.rssi_dbm(cfg, d, tx, shadow) >= cfg.sensitivity_dbm[sf]
            link = "ok" if heard else "below_sensitivity"
            below += 0 if heard else 1
        nodes.append({
            "id": nid, "x_m": round(x, 2), "y_m": round(y, 2),
            "distance_m": round(d, 2), "sf": sf, "tx_power_dbm": tx,
            "shadowing_db": round(shadow, 3), "link": link,
        })

    # Reach for the data rates the study's scenarios use, not for every one
    # the band defines: a rate no scenario uses may not even be legal at the
    # study's payload, as SF10 at 32 bytes in US915 is not.
    used = set()
    for scen in study.scenarios:
        used.update(core.parse_scenario(scen, cfg)[1])
    polygons = cfg.placement_polygons_m if not disc else None
    return {
        "scenario": scenario,
        "n_nodes": n_nodes,
        "repetition": 0,
        "seed": seed,
        "placement": cfg.placement,
        "angles_for_display_only": disc,
        "disc_radius_m": round(placed["max_d"], 1) if disc else None,
        "polygons_m": ([[[round(px, 2), round(py, 2)] for px, py in ring]
                        for ring in polygons] if polygons else None),
        "shadowing_sigma_db": cfg.shadowing_sigma_db,
        # Where the model stops being measured, so the figure can say which
        # reach is an extrapolation (design item 39). None when not known.
        "max_measured_distance_m": study.max_measured_distance_m,
        # The distance at which the median link meets each data rate's
        # sensitivity at full power. Shadowing moves a node's link about it.
        "reach_m": {str(sf): round(core.max_distance_m(cfg, cfg.sensitivity_dbm[sf]), 1)
                    for sf in sorted(used)},
        "counts": {"per_sf": dict(sorted(per_sf.items(), key=lambda kv: int(kv[0]))),
                   "unreachable": unreachable,
                   "below_sensitivity": below},
        "nodes": nodes,
    }


def write_site_map(study: Study, rows, out_dir=None, root=None,
                   provenance=None):
    """Write site_map.json when the study asks for the map.

    Returns (path, note). The path is None when nothing was written, and the
    note then says why, for the caller to show: a map nobody asked for needs
    no note, a map that could not be placed does.

    When no map is written, one left in the same directory by an earlier run
    is removed. `run` and the web page write every run into the same
    outputs/, so the old placement would otherwise be drawn, and downloaded,
    as if it belonged to this run."""
    out = out_dir or output_dir(study.name, root)
    path = os.path.join(out, SITE_MAP_JSON)
    if FIGURE_KIND not in study.extra_figures:
        _remove(path)
        return None, None
    n_nodes, nodes_from, cap = map_node_count(study, rows)
    scenario = map_scenario(study)
    if n_nodes is None:
        _remove(path)
        return None, (
            f"No site map: {scenario}'s DER never crosses "
            f"{study.der_threshold:g} over the simulated node counts, so it "
            f"has no capacity to show. Set site_map_nodes to choose a node "
            f"count.")
    data = snapshot(study, scenario, n_nodes)
    data["nodes_from"] = nodes_from
    data["capacity"] = cap
    payload = {"study": study.name, "site_map": data}
    if provenance is not None:
        payload["provenance"] = provenance
    os.makedirs(out, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path, None


def _remove(path):
    if os.path.isfile(path):
        os.remove(path)


def load_site_map(out_dir: str):
    """The map data written beside a run's results, or None if there is none."""
    path = os.path.join(out_dir, SITE_MAP_JSON)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)["site_map"]
