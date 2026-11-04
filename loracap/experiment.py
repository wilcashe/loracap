#!/usr/bin/env python3
"""
loracap.experiment
===========================

Runs the (scenario x node count x repetitions) grid for a study and writes the
results to that study's outputs/ directory.
"""
from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import asdict

from .core import run_batch
from .study import Study, output_dir

RESULTS_CSV = "results.csv"
RESULTS_JSON = "results.json"


def run_study(study: Study, progress=True, callback=None) -> list:
    cfg = study.to_sim_config()
    rows = []
    total = len(study.scenarios) * len(study.node_counts)
    done = 0
    t0 = time.time()
    for scenario in study.scenarios:
        for n_nodes in study.node_counts:
            row = run_batch(
                cfg,
                n_nodes=n_nodes,
                sim_time_ms=study.sim_time_ms,
                scenario=scenario,
                n_runs=study.n_runs,
                base_seed=study.base_seed,
            )
            rows.append(row)
            done += 1
            if progress:
                print(f"[{done:>3}/{total}] {scenario:<6} n={n_nodes:<5} "
                      f"DER={row['der_mean']:.4f} +/- {row['der_std']:.4f}",
                      flush=True)
            if callback is not None:
                callback(done, total, row)
    if progress:
        print(f"\nCompleted in {time.time() - t0:.1f} s.")
    return rows


def study_record(study: Study) -> dict:
    """The full study definition as plain data, for embedding next to results."""
    record = asdict(study)
    record["polygons_m"] = (
        f"<{len(study.polygons_m)} polygon(s), omitted for brevity>"
        if study.polygons_m else None
    )
    record["resolved_sensitivity_dbm"] = study.resolved_sensitivity()
    record["net_antenna_gain_db"] = study.net_antenna_gain_db
    return record


# Per-run lists and per-SF dictionaries live in the JSON only, so the CSV
# stays one scalar per cell and readable in a spreadsheet.
_JSON_ONLY = ("der_runs", "der_fleet_runs", "nodes_per_sf_mean")


def write_results(study: Study, rows: list, root=None, out_dir=None,
                  provenance=None) -> tuple:
    """Write results.csv and results.json.

    `out_dir` defaults to the study's outputs/ directory, which is where ad hoc
    runs land. `run.py reproduce` passes its own experiment directory instead,
    so an ad hoc run can never overwrite a result a document cites.
    """
    out = out_dir or output_dir(study.name, root)
    os.makedirs(out, exist_ok=True)

    csv_rows = [{k: v for k, v in r.items() if k not in _JSON_ONLY}
                for r in rows]
    csv_path = os.path.join(out, RESULTS_CSV)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        w.writeheader()
        w.writerows(csv_rows)

    # the full study definition travels with the results, so a result file is
    # always self-describing and no run is orphaned from its configuration
    payload = {"study": study_record(study), "results": rows}
    if provenance is not None:
        payload["provenance"] = provenance
    json_path = os.path.join(out, RESULTS_JSON)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return csv_path, json_path


def load_results(study_name: str, root=None, out_dir=None) -> list:
    path = os.path.join(out_dir or output_dir(study_name, root), RESULTS_JSON)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"No results at {path}. Run the study first:  python3 run.py run {study_name}"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)["results"]
