#!/usr/bin/env python3
"""
loracap.reproduce
=================

Every number a document cites, regenerated from a saved configuration.

Why this exists
---------------
Before this module the commands wrote fixed file names (`results.json`,
`validation.json`, ...) whatever their arguments, so a quick four-run check
silently replaced the run a table had been copied from. Experiments that
change the configuration, such as shadowing or ADR, had no place to live
except a temporary edit to `study.py`, so the configuration behind a table
was not recorded anywhere. And nothing tied a table to the run that produced
it, which is how one quantity came to be quoted as five different numbers.

Each of those has its own fix here.

  - A study may carry `experiments.py` next to `study.py`: a list of named
    `Experiment`s, each stating its repetitions, node grid, simulated time,
    seed and bootstrap count explicitly. Nothing is inherited silently from
    the study, because a value that is not written down is a value nobody
    can check.
  - Each experiment writes into its own `outputs/<experiment>/` directory.
    Ad hoc commands keep writing to `outputs/` itself, so they can never
    overwrite a result a document cites.
  - Every file written carries a `provenance` record: the experiment, the
    fully resolved study, the code digest and the date.

`run.py reproduce <study>` runs the manifest and prints each table ready to
paste, with the line that says where it came from. `--tables` prints them
again from the saved files without simulating anything.

Standard library only.
"""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import __version__, analysis, experiment as experiment_mod
from .study import Study, output_dir, study_dir, validate as validate_study

MANIFEST_FILENAME = "experiments.py"
KINDS = ("run", "sweep", "intercept", "validate", "compare")

# Fields an experiment states explicitly. Overriding them through `overrides`
# as well would leave two places that disagree about the same setting.
_EXPLICIT = ("name", "n_runs", "sim_time_s", "base_seed", "node_counts",
             "scenarios")

_NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


class ManifestError(ValueError):
    """A manifest that cannot be run as written."""


@dataclass(frozen=True)
class Variant:
    """One configuration inside an experiment.

    `name` is the subdirectory the results go to, `label` is what a table
    prints, `overrides` are Study fields changed for this variant only.
    `scenarios`, when given, restricts the variant to a subset of the
    experiment's scenarios, so a variant that only changes ADR does not rerun
    the fixed-rate scenarios it cannot affect.
    """
    name: str
    label: str
    overrides: Dict = field(default_factory=dict)
    scenarios: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Experiment:
    """One reproducible result.

    The first six fields have no default on purpose. `kind` selects the
    command (`run`, `sweep`, `intercept`, `validate`, `compare`), and the
    kind-specific settings go in `options`, documented in `_KIND_OPTIONS`.

    `overrides` applies to every variant. A `run` experiment with more than
    one variant writes one subdirectory per variant, so a table can set
    configurations side by side and every row still has its own file.
    """
    name: str
    kind: str
    description: str
    n_runs: int
    sim_time_s: float
    base_seed: int
    node_counts: Tuple[int, ...] = ()
    scenarios: Tuple[str, ...] = ()
    overrides: Dict = field(default_factory=dict)
    variants: Tuple[Variant, ...] = (Variant("", ""),)
    n_bootstrap: int = 2000
    options: Dict = field(default_factory=dict)
    tables: Tuple[str, ...] = ()
    figure: bool = False
    # One panel per named variant, side by side on a shared DER axis, drawn
    # into the experiment's own directory. This is how a figure compares
    # configurations: several variants each drawing their own figure would
    # leave the comparison to the reader's eye across files.
    figure_panels: Tuple[str, ...] = ()
    # Reference node counts drawn as labelled vertical lines, for numbers the
    # figure must be read against that the experiment does not produce, such
    # as a value another simulator or a paper reports. Each is
    # (node_count, label), and its source belongs in a comment beside it.
    figure_marks: Tuple[Tuple[float, str], ...] = ()


# What each kind needs. "grid" means node_counts must be given, "scenarios"
# that the scenario list must be. Options marked required have no default.
_KIND_OPTIONS = {
    "run": dict(grid=True, scenarios=True, required=(),
                allowed=("energy_reference", "energy_nodes")),
    "sweep": dict(grid=False, scenarios=False,
                  required=("scenario", "low", "high", "steps"), allowed=()),
    "intercept": dict(grid=False, scenarios=False,
                      required=("scenario", "n_nodes", "offsets_db"), allowed=()),
    "validate": dict(grid=True, scenarios=False, required=("scenario",),
                     allowed=()),
    "compare": dict(grid=True, scenarios=True, required=("variant", "terrain"),
                    allowed=("range_m", "anchor_sf", "exponent")),
}


# ---------------------------------------------------------------------------
# Loading and checking a manifest
# ---------------------------------------------------------------------------

def manifest_path(study_name: str, root=None) -> str:
    return os.path.join(study_dir(study_name, root), MANIFEST_FILENAME)


def has_manifest(study_name: str, root=None) -> bool:
    return os.path.isfile(manifest_path(study_name, root))


def load_manifest(study_name: str, root=None) -> List[Experiment]:
    path = manifest_path(study_name, root)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{study_name} has no {MANIFEST_FILENAME}")
    spec = importlib.util.spec_from_file_location(
        f"experiments_{study_name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    exps = getattr(module, "EXPERIMENTS", None)
    if exps is None:
        raise ManifestError(f"{path} must define EXPERIMENTS = [Experiment(...)]")
    exps = list(exps)
    check_manifest(exps)
    return exps


def check_manifest(exps: Sequence[Experiment]) -> None:
    """Raise ManifestError on the first thing that would make a run ambiguous.

    Checked before anything is simulated, because a manifest error found
    after an hour of simulation costs the hour.
    """
    study_fields = {f.name for f in dataclasses.fields(Study)}
    seen = set()
    for e in exps:
        if not isinstance(e, Experiment):
            raise ManifestError(f"{e!r} is not an Experiment")
        where = f"experiment {e.name!r}"
        if not _NAME.match(e.name):
            raise ManifestError(f"{where}: use lower-case letters, digits, "
                                f"'.', '-' or '_' so it is a safe directory name")
        if e.name in seen:
            raise ManifestError(f"{where} appears twice")
        seen.add(e.name)
        if e.kind not in KINDS:
            raise ManifestError(f"{where}: kind must be one of {KINDS}")
        spec = _KIND_OPTIONS[e.kind]
        if not isinstance(e.n_runs, int) or e.n_runs < 2:
            raise ManifestError(f"{where}: n_runs must be an integer >= 2, "
                                f"since the interval needs a spread")
        if not e.sim_time_s or e.sim_time_s <= 0:
            raise ManifestError(f"{where}: sim_time_s must be positive")
        if spec["grid"]:
            counts = list(e.node_counts)
            if not counts:
                raise ManifestError(f"{where}: node_counts must be stated")
            if counts != sorted(set(counts)) or counts[0] < 1:
                raise ManifestError(f"{where}: node_counts must be distinct, "
                                    f"positive and increasing")
        elif e.node_counts:
            raise ManifestError(f"{where}: a {e.kind} experiment takes no "
                                f"node_counts, so stating them would mislead")
        if spec["scenarios"] and not e.scenarios:
            raise ManifestError(f"{where}: scenarios must be stated")
        if not spec["scenarios"] and e.scenarios:
            raise ManifestError(f"{where}: a {e.kind} experiment names its "
                                f"scenario in options, not in scenarios")
        missing = [k for k in spec["required"] if k not in e.options]
        if missing:
            raise ManifestError(f"{where}: options {missing} are required")
        unknown = set(e.options) - set(spec["required"]) - set(spec["allowed"])
        if unknown:
            raise ManifestError(f"{where}: unknown options {sorted(unknown)}")
        if e.kind == "compare" and e.options["variant"] not in (
                "terrain", "exponent_only"):
            raise ManifestError(f"{where}: variant must be 'terrain' or "
                                f"'exponent_only'")
        if e.kind != "run" and len(e.variants) != 1:
            raise ManifestError(f"{where}: only run experiments take variants")
        names = set()
        for v in e.variants:
            if v.scenarios and not set(v.scenarios) <= set(e.scenarios):
                raise ManifestError(f"{where}: variant {v.name!r} names "
                                    f"scenarios the experiment does not run")
            if v.name and not _NAME.match(v.name):
                raise ManifestError(f"{where}: variant {v.name!r} is not a "
                                    f"safe directory name")
            if v.name in names:
                raise ManifestError(f"{where}: variant {v.name!r} appears twice")
            names.add(v.name)
            for overrides in (e.overrides, v.overrides):
                bad = set(overrides) - study_fields
                if bad:
                    raise ManifestError(f"{where}: {sorted(bad)} are not "
                                        f"Study fields")
                clash = set(overrides) & set(_EXPLICIT)
                if clash:
                    raise ManifestError(f"{where}: {sorted(clash)} are stated "
                                        f"on the experiment itself, not "
                                        f"overridden")
        if len(e.variants) > 1 and "" in names:
            raise ManifestError(f"{where}: with several variants every one "
                                f"needs a name")
        for t in e.tables:
            if t not in RENDERERS:
                raise ManifestError(f"{where}: unknown table {t!r}")
        if e.figure and e.kind not in ("run", "validate"):
            raise ManifestError(f"{where}: only a run or a validation draws "
                                f"a figure")
        if e.figure and len(e.variants) > 1 and not e.figure_panels:
            raise ManifestError(f"{where}: with several variants a figure "
                                f"must name its figure_panels, since one "
                                f"figure per variant would overwrite one file")
        if e.figure_panels:
            if not e.figure or e.kind != "run":
                raise ManifestError(f"{where}: figure_panels needs a run "
                                    f"experiment with figure=True")
            unknown_p = [p for p in e.figure_panels if p not in names or not p]
            if unknown_p:
                raise ManifestError(f"{where}: figure_panels {unknown_p} are "
                                    f"not variants of this experiment")
            if len(set(e.figure_panels)) != len(e.figure_panels):
                raise ManifestError(f"{where}: a panel appears twice in "
                                    f"figure_panels")
        if e.figure_marks:
            if not e.figure or e.kind != "run":
                raise ManifestError(f"{where}: figure_marks needs a run "
                                    f"experiment with figure=True")
            for m in e.figure_marks:
                ok = (isinstance(m, tuple) and len(m) == 2
                      and isinstance(m[0], (int, float)) and m[0] > 0
                      and isinstance(m[1], str) and m[1].strip())
                if not ok:
                    raise ManifestError(f"{where}: each figure mark must be "
                                        f"(positive node count, label), "
                                        f"got {m!r}")
        missing_n = set(e.options.get("energy_nodes", ())) - set(e.node_counts)
        if missing_n:
            raise ManifestError(f"{where}: energy_nodes {sorted(missing_n)} are "
                                f"not in node_counts, so there is no row to "
                                f"read them from")


# ---------------------------------------------------------------------------
# Resolving an experiment against its study
# ---------------------------------------------------------------------------

def effective_study(study: Study, exp: Experiment, variant: Variant) -> Study:
    """The study exactly as this experiment variant runs it."""
    changes = dict(n_runs=exp.n_runs, sim_time_s=exp.sim_time_s,
                   base_seed=exp.base_seed)
    # A validation ladder's node counts are the points it checks, not a
    # capacity curve, so they are not the study's grid and stay off it.
    if exp.node_counts and exp.kind in ("run", "compare"):
        changes["node_counts"] = tuple(exp.node_counts)
    if exp.scenarios:
        changes["scenarios"] = tuple(variant.scenarios or exp.scenarios)
    changes.update(exp.overrides)
    changes.update(variant.overrides)
    return dataclasses.replace(study, **changes)


def experiment_dir(study_name: str, exp: Experiment, variant: Variant = None,
                   root=None) -> str:
    d = os.path.join(output_dir(study_name, root), exp.name)
    if variant is not None and variant.name:
        d = os.path.join(d, variant.name)
    return d


def code_digest() -> str:
    """SHA-256 over the package source.

    The version string is not enough: it is changed by hand, and the package
    went through most of its development at one version. A digest changes
    whenever the code does, so a result can be matched to the exact source.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256()
    for fn in sorted(os.listdir(here)):
        if fn.endswith(".py"):
            h.update(fn.encode())
            with open(os.path.join(here, fn), "rb") as f:
                h.update(f.read())
    return h.hexdigest()


def _environment() -> dict:
    return {
        "loracap_version": __version__,
        "code_sha256": code_digest(),
        "python": platform.python_version(),
        "generated": datetime.datetime.now(datetime.timezone.utc)
                     .replace(microsecond=0).isoformat(),
    }


def provenance(study_name: str, study: Study, exp: Experiment,
               variant: Variant) -> dict:
    """What a file needs to say about itself to be checked without us."""
    rec = {
        "source": "manifest",
        "manifest": f"studies/{study_name}/{MANIFEST_FILENAME}",
        "experiment": exp.name,
        "kind": exp.kind,
        "description": exp.description,
        "variant": variant.name or None,
        "variant_label": variant.label or None,
        "overrides": {**exp.overrides, **variant.overrides},
        "n_runs": exp.n_runs,
        "sim_time_s": exp.sim_time_s,
        "base_seed": exp.base_seed,
        "node_counts": list(exp.node_counts),
        "scenarios": list(variant.scenarios or exp.scenarios),
        "n_bootstrap": exp.n_bootstrap,
        "options": dict(exp.options),
        "regenerate": f"python3 run.py reproduce {study_name} --only {exp.name}",
        "study": experiment_mod.study_record(study),
    }
    rec.update(_environment())
    return rec


def adhoc_provenance(study: Study, argv: Sequence[str]) -> dict:
    """Provenance for a command run by hand, outside any manifest.

    Recorded so that a file found in outputs/ says it was a one-off, and with
    which arguments, instead of passing for a canonical result.
    """
    rec = {
        "source": "ad hoc",
        "command": "python3 run.py " + " ".join(argv),
        "study": experiment_mod.study_record(study),
    }
    rec.update(_environment())
    return rec


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

def run_experiment(study_name: str, exp: Experiment, root=None,
                   log=print, plot=True) -> dict:
    """Run one experiment and write its files. Returns a summary.

    `summary["passes"]` is False only for a validation that failed, which
    `run.py reproduce` turns into a non-zero exit.
    """
    from .study import load_study
    base = load_study(study_name, root)
    written = []
    passes = True

    for variant in exp.variants:
        s = effective_study(base, exp, variant)
        errors, _warnings, _info = validate_study(s)
        if errors:
            raise ManifestError(
                f"experiment {exp.name!r}"
                + (f", variant {variant.name!r}" if variant.name else "")
                + " does not validate:\n  " + "\n  ".join(errors))
        out = experiment_dir(study_name, exp, variant, root)
        os.makedirs(out, exist_ok=True)
        prov = provenance(study_name, s, exp, variant)
        tag = exp.name + (f"/{variant.name}" if variant.name else "")
        log(f"  {tag}: {exp.kind}, {exp.n_runs} runs, "
            f"{exp.sim_time_s:g} s simulated")

        if exp.kind == "run":
            rows = experiment_mod.run_study(s, progress=False)
            written += list(experiment_mod.write_results(
                s, rows, out_dir=out, provenance=prov))
            cap = analysis.capacity_with_ci(rows, threshold=s.der_threshold,
                                            n_boot=exp.n_bootstrap)
            fleet = analysis.capacity_with_ci(
                [dict(r, der_mean=r["der_fleet_mean"], der_runs=r["der_fleet_runs"])
                 for r in rows], threshold=s.der_threshold, n_boot=exp.n_bootstrap)
            written.append(analysis.write_capacity(
                s.name, cap, s.der_threshold, out_dir=out, provenance=prov,
                fleet_capacity=fleet))
            if plot and exp.figure and not exp.figure_panels:
                written += _plot_run(s, rows, out, log, exp.figure_marks)

        elif exp.kind == "sweep":
            from . import sweep as sweep_mod
            o = exp.options
            exps = sweep_mod.exponent_range(o["low"], o["high"], o["steps"])
            sw = sweep_mod.sweep_propagation(
                s, exponents=exps, scenario=o["scenario"], n_runs=exp.n_runs,
                progress=False)
            written.append(sweep_mod.write_sweep(s.name, sw, out_dir=out,
                                                 provenance=prov))

        elif exp.kind == "intercept":
            from . import sweep as sweep_mod
            o = exp.options
            inv = sweep_mod.verify_intercept_invariance(
                s, offsets_db=tuple(o["offsets_db"]), scenario=o["scenario"],
                n_runs=exp.n_runs, n_nodes=o["n_nodes"])
            written.append(sweep_mod.write_invariance(s.name, inv, out_dir=out,
                                                      provenance=prov))

        elif exp.kind == "validate":
            from . import validation as val
            ladder = val.run_ladder(
                s.to_sim_config(), exp.options["scenario"], list(exp.node_counts),
                sim_time_s=exp.sim_time_s, n_runs=exp.n_runs,
                base_seed=exp.base_seed)
            verdict = val.assess(ladder)
            passes = passes and verdict["passes"]
            written.append(val.write_ladder(s.name, ladder, verdict, out_dir=out,
                                            provenance=prov))
            if plot and exp.figure:
                written += _plot_validation(s, ladder, out, log)

        elif exp.kind == "compare":
            from . import compare as cmp_mod
            o = exp.options
            if o["variant"] == "exponent_only":
                label, overrides, _p = cmp_mod.exponent_only_variant(
                    s, o["terrain"], exponent=o.get("exponent"))
            else:
                label, overrides, _p = cmp_mod.terrain_variant(
                    s, o["terrain"], range_m=o.get("range_m"),
                    anchor_sf=o.get("anchor_sf"), exponent=o.get("exponent"))
            result = cmp_mod.compare_models(
                s, [("fitted (field)", {}), (label, overrides)],
                n_runs=exp.n_runs, n_boot=exp.n_bootstrap)
            written.append(cmp_mod.write_comparison(s.name, result, out_dir=out,
                                                    provenance=prov))

    if plot and exp.figure_panels:
        written += _plot_panels(study_name, base, exp, root, log)

    return {"experiment": exp.name, "written": written, "passes": passes}


def _plot_run(s, rows, out, log, marks=()):
    try:
        from . import plotting
    except ImportError:
        log("    matplotlib is not installed, so no figure was drawn.")
        return []
    return plotting.plot_study(s, rows, out_dir=out, marks=marks)


def panel_data(study_name: str, base: Study, exp: Experiment, root=None):
    """What each panel of a multi-variant figure is drawn from, read from the
    saved files only.

    The capacity printed on a panel is the one `capacity.json` holds, the
    same number the experiment's table prints, rather than a crossing the
    plotting code recomputes, so the figure and the table cannot disagree.
    """
    by_name = {v.name: v for v in exp.variants}
    panels = []
    for name in exp.figure_panels:
        v = by_name[name]
        s = effective_study(base, exp, v)
        out = experiment_dir(study_name, exp, v, root)
        rows = experiment_mod.load_results(study_name, out_dir=out)
        cap = _load_json(os.path.join(out, "capacity.json"))["capacity"]
        panels.append({"study": s, "label": v.label, "rows": rows,
                       "capacity": cap})
    return panels


def _plot_panels(study_name, base, exp, root, log):
    try:
        from . import plotting
    except ImportError:
        log("    matplotlib is not installed, so no figure was drawn.")
        return []
    panels = panel_data(study_name, base, exp, root)
    out = experiment_dir(study_name, exp, None, root)
    return plotting.plot_panels(
        panels, out_dir=out,
        basename=f"{base.figure_basename}_{exp.name}")


def _plot_validation(s, ladder, out, log):
    try:
        from . import plotting
    except ImportError:
        log("    matplotlib is not installed, so no figure was drawn.")
        return []
    return plotting.plot_validation(s, ladder, out_dir=out)


def replot(study_name: str, root=None, log=print) -> List[str]:
    """Redraw every manifest figure from its saved JSON, simulating nothing."""
    from .study import load_study
    base = load_study(study_name, root)
    written = []
    for exp in load_manifest(study_name, root):
        if not exp.figure:
            continue
        variant = exp.variants[0]
        s = effective_study(base, exp, variant)
        out = experiment_dir(study_name, exp, variant, root)
        if exp.kind == "run" and exp.figure_panels:
            written += _plot_panels(study_name, base, exp, root, log)
        elif exp.kind == "run":
            rows = experiment_mod.load_results(study_name, out_dir=out)
            written += _plot_run(s, rows, out, log, exp.figure_marks)
        elif exp.kind == "validate":
            with open(os.path.join(out, "validation.json"), encoding="utf-8") as f:
                ladder = json.load(f)["ladder"]
            written += _plot_validation(s, ladder, out, log)
    return written


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
#
# Each renderer reads saved files only. They are markdown because that is what
# the README is written in, and each ends with the line that says
# where its numbers came from.

def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _fmt(x, nd=1):
    return "no crossing" if x is None else f"{x:.{nd}f}"


def _ci(c):
    if c.get("ci_low") is None:
        return "-"
    return f"[{c['ci_low']:.1f}, {c['ci_high']:.1f}]"


def _grid_text(counts):
    counts = list(counts)
    if not counts:
        return ""
    if len(counts) <= 6:
        return f"N = {', '.join(str(c) for c in counts)}"
    return f"{len(counts)} node counts from {counts[0]} to {counts[-1]}"


def provenance_line(study_name: str, exp: Experiment) -> str:
    bits = [f"{exp.n_runs} runs per point"]
    g = _grid_text(exp.node_counts)
    if g:
        bits.append(g)
    elif exp.kind == "sweep":
        bits.append("capacity by bisection on node count")
    elif exp.kind == "intercept":
        bits.append(f"N = {exp.options['n_nodes']}")
    bits.append(f"{exp.sim_time_s:g} s simulated")
    bits.append(f"seed {exp.base_seed}")
    if exp.kind in ("run", "compare"):
        bits.append(f"{exp.n_bootstrap} bootstrap replicates")
    return (f"*Source: experiment `{exp.name}` of "
            f"`studies/{study_name}/{MANIFEST_FILENAME}`, "
            + ", ".join(bits)
            + f". Data in `studies/{study_name}/outputs/{exp.name}/`. "
            f"Regenerate with `python3 run.py reproduce {study_name} "
            f"--only {exp.name}`.*")


def _run_variant_data(study_name, exp, root):
    out = []
    for v in exp.variants:
        d = experiment_dir(study_name, exp, v, root)
        rows = _load_json(os.path.join(d, experiment_mod.RESULTS_JSON))["results"]
        cap = _load_json(os.path.join(d, analysis.CAPACITY_JSON))
        out.append((v, rows, cap))
    return out


def _row_near(rows, scenario, n):
    pool = [r for r in rows if r["scenario"] == scenario]
    if not pool:
        return None
    target = n if n is not None else pool[-1]["n_nodes"]
    return min(pool, key=lambda r: abs(r["n_nodes"] - target))


def _max_excluded(rows, scenario=None):
    vals = [r.get("unreachable_fraction_mean", 0.0) for r in rows
            if scenario is None or r["scenario"] == scenario]
    return max(vals) if vals else 0.0


def table_capacity(study_name, exp, root=None) -> str:
    """Scenario, capacity and interval, one row per variant and scenario."""
    data = _run_variant_data(study_name, exp, root)
    multi = len(data) > 1
    head = (["Configuration"] if multi else []) + ["Scenario",
                                                    f"Capacity at DER = {_threshold(data)}",
                                                    "95% CI"]
    lines = [_md_row(head), _md_rule(len(head))]
    for v, rows, cap in data:
        for scen, c in cap["capacity"].items():
            cells = ([v.label] if multi else []) + [scen, _fmt(c["capacity"]),
                                                    _ci(c)]
            lines.append(_md_row(cells))
    return "\n".join(lines)


def table_detail(study_name, exp, root=None) -> str:
    """Capacity with the quantities that explain it: received-power spread
    and mean transmit power at the simulated node count nearest the
    capacity, and the share of nodes on each spreading factor at the largest
    node count."""
    data = _run_variant_data(study_name, exp, root)
    head = ["Configuration", "Scenario", "Capacity", "95% CI", "RSSI spread",
            "Mean power", "Nodes per SF at N max"]
    lines = [_md_row(head), _md_rule(len(head))]
    for v, rows, cap in data:
        for scen, c in cap["capacity"].items():
            near = _row_near(rows, scen, c["capacity"])
            top = _row_near(rows, scen, None)
            per_sf = top.get("nodes_per_sf_mean", {})
            sf_text = ", ".join(f"SF{k} {per_sf[k]:.1f}" for k in sorted(
                per_sf, key=int)) or "-"
            lines.append(_md_row([
                v.label or "-", scen, _fmt(c["capacity"]), _ci(c),
                f"{near['rssi_spread_db_mean']:.1f} dB",
                f"{near['mean_tx_power_dbm']:.1f} dBm",
                f"{sf_text} (N = {top['n_nodes']})"]))
    lines.append("")
    lines.append("RSSI spread is the largest range of received power within one "
                 "spreading factor, and it and mean power are taken at the "
                 "simulated node count nearest each capacity. Nodes per SF are "
                 "means over the runs.")
    return "\n".join(lines)


def table_pivot(study_name, exp, root=None) -> str:
    """One row per variant, one capacity column per scenario, plus the
    largest share of nodes any scenario left with no usable data rate."""
    data = _run_variant_data(study_name, exp, root)
    scens = list(data[0][2]["capacity"])
    head = ["Configuration"] + scens + ["Excluded, worst case"]
    lines = [_md_row(head), _md_rule(len(head))]
    for v, rows, cap in data:
        cells = [v.label]
        for s in scens:
            c = cap["capacity"][s]
            cells.append(f"{_fmt(c['capacity'])} {_ci(c)}")
        cells.append(f"{100 * _max_excluded(rows):.1f}%")
        lines.append(_md_row(cells))
    return "\n".join(lines)


def table_fleet(study_name, exp, root=None) -> str:
    """Capacity over the nodes that transmitted against capacity over the
    whole intended fleet, which counts excluded nodes as lost traffic."""
    data = _run_variant_data(study_name, exp, root)
    head = ["Configuration", "Scenario", "Capacity, `der`",
            "Capacity, `der_fleet`", "Excluded, worst case"]
    lines = [_md_row(head), _md_rule(len(head))]
    for v, rows, cap in data:
        fleet = cap.get("fleet_capacity", {})
        for scen, c in cap["capacity"].items():
            f = fleet.get(scen, {})
            lines.append(_md_row([v.label, scen, _fmt(c["capacity"]),
                                  _fmt(f.get("capacity")),
                                  f"{100 * _max_excluded(rows, scen):.1f}%"]))
    return "\n".join(lines)


def table_losses(study_name, exp, root=None) -> str:
    """Why a capacity moved: weak-signal and collision losses as a share of
    transmitted packets at the simulated node count nearest the capacity,
    and the width of the capacity interval."""
    data = _run_variant_data(study_name, exp, root)
    # The inter-SF column appears only when some variant ran with the rule,
    # so that every table written before it existed comes out unchanged.
    inter = any("lost_inter_sf_mean" in r for _v, rows, _c in data for r in rows)
    head = ["Configuration", "Scenario", "At N", "Weak signal", "Collided"]
    if inter:
        head.append("of which another SF")
    head.append("CI width")
    lines = [_md_row(head), _md_rule(len(head))]
    for v, rows, cap in data:
        for scen, c in cap["capacity"].items():
            r = _row_near(rows, scen, c["capacity"])
            tx = r["transmitted_mean"] or float("nan")
            width = (c["ci_high"] - c["ci_low"]) if c.get("ci_low") is not None \
                else None
            cells = [v.label, scen, str(r["n_nodes"]),
                     f"{100 * r['lost_signal_mean'] / tx:.2f}%",
                     f"{100 * r['collided_mean'] / tx:.2f}%"]
            if inter:
                cells.append(f"{100 * r['lost_inter_sf_mean'] / tx:.2f}%"
                             if "lost_inter_sf_mean" in r else "off")
            cells.append(_fmt(width))
            lines.append(_md_row(cells))
    lines.append("")
    lines.append("Losses are shares of transmitted packets at the simulated node "
                 "count nearest each capacity.")
    if inter:
        lines.append("\"Of which another SF\" counts collided packets that an "
                     "overlap with another spreading factor took, alone or "
                     "together with a same-SF overlap. \"Off\" marks a "
                     "configuration with orthogonal spreading factors.")
    return "\n".join(lines)


def table_energy(study_name, exp, root=None) -> str:
    """Energy per extracted message relative to a reference scenario, at the
    node counts in `options['energy_nodes']`, then the figures quoted
    alongside it."""
    from .study import load_study
    (v, rows, _cap), = _run_variant_data(study_name, exp, root)[:1]
    ref = exp.options.get("energy_reference", exp.scenarios[0])
    nodes = exp.options.get("energy_nodes", exp.node_counts)
    others = [s for s in exp.scenarios if s != ref]
    head = ["N"] + [f"{s} vs {ref}" for s in others]
    lines = [_md_row(head), _md_rule(len(head))]
    by = {(r["scenario"], r["n_nodes"]): r for r in rows}
    for n in nodes:
        base = by[(ref, n)]["nec_j_per_message_mean"]
        cells = [str(n)]
        for s in others:
            val = by[(s, n)]["nec_j_per_message_mean"]
            cells.append(f"{100 * (val / base - 1):+.0f}%")
        lines.append(_md_row(cells))

    s = effective_study(load_study(study_name, root), exp, v)
    notes = []
    for sc in others:
        drop = [s.tx_power_dbm - by[(sc, n)]["mean_tx_power_dbm"] for n in nodes]
        notes.append(f"Mean transmit-power reduction under {sc}: "
                     f"{sum(drop) / len(drop):.1f} dB, averaged over those N.")
    first = by[(ref, nodes[0])]
    notes.append(f"Transmit energy per run under {ref}: "
                 + ", ".join(f"N = {n}: {by[(ref, n)]['tx_energy_j_mean']:.1f} J"
                             for n in nodes) + ".")
    life = analysis.service_life(first, s)
    if life:
        # Transmit current scales as 1/interval, sleep current does not, so
        # the interval at which the two are equal follows directly.
        cross_s = s.send_interval_s * life["tx_current_ma"] / life["sleep_current_ma"]
        notes.append(
            f"At a {s.send_interval_s:g} s interval with {s.sleep_current_ua:g} uA "
            f"of sleep draw, transmitting is {100 * life['transmit_share']:.1f}% "
            f"of the average current under {ref}. Sleep overtakes it past "
            f"{cross_s / 3600:.1f} h.")
    return "\n".join(lines) + "\n\n" + "\n".join(f"- {n}" for n in notes)


def table_sweep(study_name, exp, root=None) -> str:
    d = experiment_dir(study_name, exp, None, root)
    sw = _load_json(os.path.join(d, "propagation_sweep.json"))
    head = ["Exponent", "Reach", "Covers site", "Capacity"]
    lines = [_md_row(head), _md_rule(len(head))]
    covered = []
    for r in sw["results"]:
        mark = " (this study)" if abs(r["path_loss_exponent"]
                                      - sw["fitted_exponent"]) < 1e-9 else ""
        cov = "-" if r["covers_site"] is None else ("yes" if r["covers_site"] else "NO")
        if r["covers_site"] and r["capacity"]:
            covered.append(r["capacity"])
        lines.append(_md_row([f"{r['path_loss_exponent']:.2f}{mark}",
                              f"{r['reach_m']:.0f} m", cov,
                              _fmt(r["capacity"])]))
    text = "\n".join(lines)
    if len(covered) > 1:
        text += (f"\n\nWhile the site is covered, capacity spans "
                 f"{min(covered):.1f} to {max(covered):.1f}, "
                 f"{100 * (max(covered) / min(covered) - 1):.0f}% of the lower "
                 f"value. Site radius {sw['site_radius_m']:.0f} m, scenario "
                 f"{sw['scenario']}.")
    return text


def table_intercept(study_name, exp, root=None) -> str:
    d = experiment_dir(study_name, exp, None, root)
    inv = _load_json(os.path.join(d, "intercept_invariance.json"))
    head = ["Intercept shift", "L(d0)", "DER", "Weak-signal losses"]
    lines = [_md_row(head), _md_rule(len(head))]
    for r in inv["results"]:
        lines.append(_md_row([f"{r['offset_db']:+.0f} dB",
                              f"{r['path_loss_ref_db']:.2f} dB",
                              f"{r['der_mean']:.6f}",
                              f"{r['lost_signal_mean']:g}"]))
    return ("\n".join(lines)
            + f"\n\nLargest DER difference {inv['max_der_difference']:.2e}, "
              f"{inv['scenario']} at N = {inv['n_nodes']}. "
              f"Invariant: {'yes' if inv['invariant'] else 'NO'}.")


def table_validation(study_name, exp, root=None) -> str:
    from . import validation as val
    d = experiment_dir(study_name, exp, None, root)
    data = _load_json(os.path.join(d, "validation.json"))
    ladder, verdict = data["ladder"], data["verdict"]
    labels = ladder["rung_labels"]
    head = ["N", "G"] + labels + ["ALOHA"]
    lines = [_md_row(head), _md_rule(len(head))]
    for row in ladder["rows"]:
        lines.append(_md_row([str(row["n_nodes"]), f"{row['offered_load']:.3f}"]
                             + [f"{row['rungs'][lab]['der_mean']:.4f}"
                                for lab in labels]
                             + [f"{row['aloha_der']:.4f}"]))
    contrib = val.contributions(ladder)
    lines.append("")
    lines.append(f"What each mechanism is worth at N = {contrib['n_nodes']}, "
                 f"as the DER it adds:")
    lines.append("")
    for c in contrib["steps"]:
        lines.append(f"- {c['mechanism']}: {c['worth']:+.4f} "
                     f"({c['der_above']:.4f} with it, {c['der_below']:.4f} "
                     f"without)")
    lines.append(f"- residual against ALOHA: {contrib['residual']:+.4f}")
    if any(c["direction"] == "either" for c in contrib["steps"]):
        lines.append("")
        lines.append("The receiver lock is checked for no direction: it saves the "
                     "first of two equal-power packets and loses both when the "
                     "later one is stronger, so its sign depends on the site.")
    lock = verdict.get("lock_agreement")
    if lock:
        lines.append("")
        lines.append("The lock rule's own bound, on one channel with no capture "
                     "and no preamble allowance:")
        lines.append("")
        lines += [_md_row(["N", "first-come", "exp(-G)"]), _md_rule(3)]
        for a in lock:
            lines.append(_md_row([str(a["n_nodes"]), f"{a['first_come']:.4f}",
                                  f"{a['bound']:.4f}"]))
    lines.append("")
    tail = ""
    if lock:
        tail = (f" {verdict['n_lock_agree']} of {len(lock)} first-come points "
                f"within {verdict['sigmas']:g} standard errors of exp(-G).")
    lines.append(f"Verdict: directions {'hold' if verdict['directions_hold'] else 'FAIL'}, "
                 f"{verdict['n_agree']} of {verdict['n_points']} points within "
                 f"{verdict['sigmas']:g} standard errors of the bound.{tail} "
                 f"{'PASS' if verdict['passes'] else 'FAIL'}.")
    return "\n".join(lines)


def table_compare(study_name, exp, root=None) -> str:
    d = experiment_dir(study_name, exp, None, root)
    res = _load_json(os.path.join(d, "model_comparison.json"))["comparison"]
    scens = res["scenarios"]
    head = ["Model"] + scens
    lines = [_md_row(head), _md_rule(len(head))]
    for v in res["variants"]:
        cells = [v["label"]]
        for s in scens:
            c = v["capacity"][s]
            cells.append(f"{_fmt(c['capacity'])} {_ci(c)}")
        lines.append(_md_row(cells))
    lines.append("")
    lines.append("Reach as a multiple of the site radius:")
    lines.append("")
    for v in res["variants"]:
        rr = v.get("reach_ratio") or {}
        lines.append(f"- {v['label']}: " + ", ".join(
            f"{s} {rr[s]:.2f}" for s in scens if s in rr))
    return "\n".join(lines)


def _threshold(data):
    return data[0][2].get("der_threshold", 0.9)


def _md_row(cells):
    return "| " + " | ".join(cells) + " |"


def _md_rule(n):
    return "|" + "---|" * n


RENDERERS = {
    "capacity": table_capacity,
    "detail": table_detail,
    "pivot": table_pivot,
    "fleet": table_fleet,
    "losses": table_losses,
    "energy": table_energy,
    "sweep": table_sweep,
    "intercept": table_intercept,
    "validation": table_validation,
    "compare": table_compare,
}

_DEFAULT_TABLE = {"run": "capacity", "sweep": "sweep", "intercept": "intercept",
                  "validate": "validation", "compare": "compare"}


def render_tables(study_name: str, exp: Experiment, root=None) -> str:
    names = exp.tables or (_DEFAULT_TABLE[exp.kind],)
    parts = [f"### {study_name} / {exp.name}", "", exp.description, ""]
    for name in names:
        parts.append(RENDERERS[name](study_name, exp, root))
        parts.append("")
    parts.append(provenance_line(study_name, exp))
    return "\n".join(parts) + "\n"


def write_tables(study_name: str, exp: Experiment, root=None) -> str:
    """Save the rendered tables next to the data they came from."""
    text = render_tables(study_name, exp, root)
    path = os.path.join(experiment_dir(study_name, exp, None, root), "tables.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# ---------------------------------------------------------------------------
# Reference tables that need no simulation
# ---------------------------------------------------------------------------

def reference_tables() -> str:
    """Tables computed from `presets`, which carries the sources itself."""
    from . import presets
    from .presets import sensitivity_derivation_error

    lines = ["### reference / terrain exponents", ""]
    head = ["Environment", "Observed range", "Median", "Studies", "Frequencies"]
    lines += [_md_row(head), _md_rule(len(head))]
    for env in presets.TERRAIN_EXPONENTS:
        lo, hi, med, n, freqs = presets.terrain_range(env)
        lines.append(_md_row([env, f"{lo:.2f} – {hi:.2f}", f"{med:.2f}", str(n),
                              ", ".join(str(f) for f in freqs) + " MHz"]))
    lines += ["", f"*Source: `presets.TERRAIN_EXPONENTS`, from "
                  f"{presets.TERRAIN_SOURCE}. Print with "
                  f"`python3 run.py reproduce reference`.*", ""]

    lines += ["### reference / bandwidth derivation error", ""]
    head = ["Bandwidth", "Mean error", "Worst"]
    lines += [_md_row(head), _md_rule(len(head))]
    for bw, mean, worst in sensitivity_derivation_error():
        lines.append(_md_row([f"{bw} kHz", f"{mean:+.2f} dB", f"{worst:+.2f} dB"]))
    lines += ["", "*Source: each of Bor et al.'s measured 250 and 500 kHz "
                  "columns derived from their 125 kHz column by "
                  "`10·log10(BW₂/BW₁)` and compared with the measured value. "
                  "Computed by `presets.sensitivity_derivation_error`. Print "
                  "with `python3 run.py reproduce reference`.*", ""]
    return "\n".join(lines)
