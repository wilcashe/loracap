"""
Resolving one study under more than one propagation model.
==========================================================

The question this answers is the one every reader without a measurement
campaign is actually asking: what does not measuring cost?

It can only be answered at a site that DOES have measurements, because the
fitted model is the ground truth the assumed one gets checked against. That
is the opposite of who it serves. A site with no campaign is served by
`sweep`, which reports how far capacity moves across a plausible exponent
range. This module exists to validate that route, not to substitute for it.

The comparison runs each model over the study's own node-count grid and
derives capacity exactly as `run` does, so what comes out is comparable with
the headline figure rather than with a separate bisection. Both get
confidence intervals, because the verdict is whether the assumed model's
estimate falls inside the fitted model's interval, and that question has no
meaning without one.

One site proves nothing a reviewer will accept. Two, with different geometry
and terrain, make it evidence.
"""
from __future__ import annotations

import dataclasses
import json
import os
from typing import Dict, List, Optional, Sequence, Tuple

from . import analysis, presets
from .core import max_distance_m, parse_scenario, ref_loss_for_range, run_batch
from .geo import inspect as inspect_rings
from .study import Study, output_dir

# Propagation fields a variant may override. Nothing else may differ, or the
# comparison stops being about propagation.
PROPAGATION_FIELDS = (
    "path_loss_exponent", "path_loss_ref_db", "path_loss_ref_distance_m",
    "min_valid_distance_m", "shadowing_sigma_db",
)


def site_radius_m(study: Study) -> Optional[float]:
    """Farthest point of the deployment from the gateway, or None for a
    study placed over the coverage disc rather than a boundary."""
    if study.placement != "polygon" or not study.polygons_m:
        return None
    return inspect_rings([("site", r) for r in study.polygons_m])["max_radius_m"]


def terrain_variant(
    study: Study,
    terrain: str,
    range_m: Optional[float] = None,
    anchor_sf: Optional[int] = None,
    exponent: Optional[float] = None,
) -> Tuple[str, dict, dict]:
    """Build the assumed-model variant: a published exponent for a comparable
    environment, with the intercept anchored to an expected reach.

    Published measurements give the slope and say nothing about the
    intercept, and free-space loss is not a usable stand-in. So the intercept
    is anchored to the one quantity a deployer can state without a campaign,
    which is roughly how far the link is expected to work. The site's own
    radius is the default, being the minimum assumption under which the
    deployment works at all.

    Returns (label, field overrides, provenance).
    """
    low, high, median, n_studies, freqs = presets.terrain_range(terrain)
    gamma = median if exponent is None else exponent

    if range_m is None:
        range_m = site_radius_m(study)
        if range_m is None:
            raise ValueError(
                "This study places nodes over the coverage disc, so it has no "
                "site radius to anchor the intercept to. Give range_m, the "
                "distance the link is expected to reach."
            )

    sens = study.resolved_sensitivity()
    if anchor_sf is None:
        # The slowest data rate the study ACTUALLY SIMULATES, not the slowest
        # the chip can do. Anchoring to a data rate no scenario uses puts the
        # whole ladder out of reach: anchor SF10 on a study running SF7 to
        # SF9 and every one of them falls short of the site, for a reason
        # that has nothing to do with the terrain being modelled.
        cfg = study.to_sim_config()
        in_play = set()
        for scen in study.scenarios:
            try:
                in_play.update(parse_scenario(scen, cfg)[1])
            except ValueError:
                continue
        anchor_sf = max(in_play) if in_play else max(sens)
    if anchor_sf not in sens:
        raise ValueError(f"anchor_sf=SF{anchor_sf} has no sensitivity defined.")

    d0 = study.path_loss_ref_distance_m
    ref_db = ref_loss_for_range(
        study.tx_power_dbm, study.net_antenna_gain_db, sens[anchor_sf],
        gamma, range_m, d0)

    overrides = {
        "path_loss_exponent": gamma,
        "path_loss_ref_db": ref_db,
        "path_loss_ref_distance_m": d0,
    }
    provenance = {
        "terrain": terrain, "exponent": gamma,
        "range_low": low, "range_high": high, "median": median,
        "n_studies": n_studies, "study_frequencies_mhz": list(freqs),
        "anchor_range_m": range_m, "anchor_sf": anchor_sf,
        "path_loss_ref_db": ref_db,
        "source": presets.TERRAIN_SOURCE,
    }
    return f"assumed ({terrain})", overrides, provenance


def exponent_only_variant(study: Study, terrain: str,
                          exponent: Optional[float] = None) -> Tuple[str, dict, dict]:
    """A variant that changes the exponent and KEEPS the fitted intercept.

    This asks a narrower question than `terrain_variant`: what if the slope
    were wrong but the intercept right? Nobody without measurements is in
    that position, so it is not the realistic case. It is the useful one for
    separating two effects that `terrain_variant` combines, because changing
    the exponent alone barely moves coverage, while re-anchoring the
    intercept moves it a great deal.
    """
    low, high, median, n_studies, freqs = presets.terrain_range(terrain)
    gamma = median if exponent is None else exponent
    return (
        f"exponent only ({terrain})",
        {"path_loss_exponent": gamma},
        {"terrain": terrain, "exponent": gamma, "range_low": low,
         "range_high": high, "median": median, "n_studies": n_studies,
         "study_frequencies_mhz": list(freqs),
         "path_loss_ref_db": study.path_loss_ref_db,
         "anchor_range_m": None, "anchor_sf": None,
         "source": presets.TERRAIN_SOURCE},
    )


def _reach(study: Study, overrides: dict, scenario: str) -> float:
    cfg = dataclasses.replace(study.to_sim_config(), **overrides)
    _fixed, opts = parse_scenario(scenario, cfg)
    return max_distance_m(cfg, min(cfg.sensitivity_dbm[sf] for sf in opts))


def compare_models(
    study: Study,
    variants: Sequence[Tuple[str, dict]],
    n_runs: Optional[int] = None,
    n_boot: int = 2000,
    progress=None,
) -> dict:
    """Resolve `study` once per variant and collect the capacities.

    `variants` is a sequence of (label, propagation overrides). The first is
    the baseline, normally the study exactly as configured. Only propagation
    fields may be overridden: anything else and the two runs would differ for
    reasons the comparison then attributes to propagation.
    """
    for label, overrides in variants:
        bad = set(overrides) - set(PROPAGATION_FIELDS)
        if bad:
            raise ValueError(
                f"variant {label!r} overrides {sorted(bad)}, which is not a "
                f"propagation field. Only {list(PROPAGATION_FIELDS)} may "
                f"differ, or the comparison is not about propagation."
            )

    runs = n_runs or study.n_runs
    radius = site_radius_m(study)
    base_cfg = study.to_sim_config()
    out_variants = []
    total = len(variants) * len(study.scenarios) * len(study.node_counts)
    done = 0

    for label, overrides in variants:
        cfg = dataclasses.replace(base_cfg, **overrides)
        rows = []
        for scen in study.scenarios:
            for n in study.node_counts:
                r = run_batch(cfg, n, study.sim_time_ms, scen, runs,
                              study.base_seed)
                rows.append({**r, "scenario": scen, "n_nodes": n})
                done += 1
                if progress:
                    progress(done, total, label, scen, n, r["der_mean"])
        cap = analysis.capacity_with_ci(rows, threshold=study.der_threshold,
                                        n_boot=n_boot)
        reach = {scen: _reach(study, overrides, scen) for scen in study.scenarios}
        out_variants.append({
            "label": label,
            "overrides": overrides,
            "capacity": cap,
            "reach_m": reach,
            # A ratio, not a flag. Anchoring the intercept to the site
            # radius puts reach exactly at the boundary, where a boolean is
            # decided by floating-point noise and tells the reader nothing.
            # 1.0 is marginal coverage, 3.2 is the margin the fitted model
            # turns out to have.
            "reach_ratio": (None if not radius
                            else {s: reach[s] / radius for s in reach}),
            "covers_site": (None if not radius
                            else {s: reach[s] >= radius * 0.999 for s in reach}),
            "unreachable_fraction": {
                scen: max(r["unreachable_fraction_mean"] for r in rows
                          if r["scenario"] == scen)
                for scen in study.scenarios
            },
        })

    return {
        "study": study.name,
        "baseline_model": {f: getattr(study, f) for f in PROPAGATION_FIELDS},
        "threshold": study.der_threshold,
        "n_runs": runs,
        "scenarios": list(study.scenarios),
        "site_radius_m": radius,
        "variants": out_variants,
    }


def assess(result: dict) -> dict:
    """Does each variant's estimate land inside the baseline's interval?"""
    base = result["variants"][0]
    out = []
    for variant in result["variants"][1:]:
        for scen in result["scenarios"]:
            b = base["capacity"].get(scen, {})
            v = variant["capacity"].get(scen, {})
            bc, vc = b.get("capacity"), v.get("capacity")
            inside = (None if bc is None or vc is None
                      else b["ci_low"] <= vc <= b["ci_high"])
            out.append({
                "variant": variant["label"], "scenario": scen,
                "baseline": bc, "baseline_ci": (b.get("ci_low"), b.get("ci_high")),
                "estimate": vc, "estimate_ci": (v.get("ci_low"), v.get("ci_high")),
                "inside": inside,
                "relative_error": (None if not bc or vc is None
                                   else (vc - bc) / bc),
                "covers_site": (variant["covers_site"] or {}).get(scen),
            })
    return {"comparisons": out,
            "all_inside": all(c["inside"] for c in out if c["inside"] is not None)
                          and any(c["inside"] is not None for c in out)}


def format_comparison(result: dict, verdict: Optional[dict] = None) -> str:
    if verdict is None:
        verdict = assess(result)
    L = []
    L.append(f"One study under {len(result['variants'])} propagation models: "
             f"{result['study']}")
    L.append(f"  DER threshold {result['threshold']:g}, "
             f"{result['n_runs']} runs per point")
    if result["site_radius_m"]:
        L.append(f"  site extends {result['site_radius_m']:.0f} m from the gateway")
    L.append("")

    wl = max(len(v["label"]) for v in result["variants"]) + 2
    for scen in result["scenarios"]:
        L.append(f"  {scen}")
        head = (f"    {'model':<{wl}}{'n':>8}{'ref dB':>9}{'reach':>9}"
                f"{'reach/site':>11}{'capacity':>11}{'95% CI':>17}")
        L.append(head)
        L.append("    " + "-" * (len(head) - 4))
        for v in result["variants"]:
            cap = v["capacity"].get(scen, {})
            c = cap.get("capacity")
            ci = ("" if cap.get("ci_low") is None
                  else f"[{cap['ci_low']:.1f}, {cap['ci_high']:.1f}]")
            cov = ("-" if v.get("reach_ratio") is None
                   else f"{v['reach_ratio'][scen]:.2f}x")
            # the baseline overrides nothing, so fall back to the study's own
            over = {**result["baseline_model"], **v["overrides"]}
            L.append(
                f"    {v['label']:<{wl}}"
                f"{over['path_loss_exponent']:>8.3f}"
                f"{over['path_loss_ref_db']:>9.1f}"
                f"{v['reach_m'][scen]:>8.0f}m{cov:>9}"
                f"{(f'{c:.1f}' if c else 'none'):>11}{ci:>17}")
        L.append("")

    L.append("  Verdict")
    for c in verdict["comparisons"]:
        if c["inside"] is None:
            L.append(f"    {c['scenario']}: no crossing under one of the models, "
                     f"so there is nothing to compare.")
            continue
        err = 100 * c["relative_error"]
        if c["inside"]:
            L.append(f"    {c['scenario']}: the assumed model gives "
                     f"{c['estimate']:.1f} against {c['baseline']:.1f} fitted, "
                     f"{err:+.1f}%, INSIDE the fitted model's interval.")
        else:
            L.append(f"    {c['scenario']}: the assumed model gives "
                     f"{c['estimate']:.1f} against {c['baseline']:.1f} fitted, "
                     f"{err:+.1f}%, OUTSIDE the fitted model's interval.")
        if c["covers_site"] is False:
            L.append(f"      It also fails to cover the site, so its answer is "
                     f"limited by range rather than by collisions.")
    # When a variant loses coverage everywhere, the exponent is not what the
    # comparison measured. Saying so matters: the reader would otherwise read
    # a coverage failure as a statement about terrain.
    for variant in result["variants"][1:]:
        covers = variant["covers_site"]
        if covers and not any(covers.values()):
            L.append(f"    {variant['label']} covers the site at no scenario, so "
                     f"its figures are")
            L.append(f"    about range and not about collisions. The anchor, not "
                     f"the exponent, is")
            L.append(f"    doing the work: the fitted model has margin that an "
                     f"expected-reach")
            L.append(f"    statement cannot know about. Vary it with --range, or "
                     f"isolate the")
            L.append(f"    exponent with --keep-intercept.")
            L.append("")

    if verdict["all_inside"]:
        L.append("    Every assumed estimate lands inside the measured interval at")
        L.append("    this site. That is evidence the assumed-model route is")
        L.append("    usable, not proof: one site establishes nothing a reviewer")
        L.append("    will accept. Run it wherever you have measurements.")
    else:
        L.append("    At least one assumed estimate falls outside the measured")
        L.append("    interval. Report the disagreement and its size: a method")
        L.append("    whose limits are stated is worth more than one whose")
        L.append("    failures are unreported.")
    return "\n".join(L)


def write_comparison(study_name: str, result: dict, verdict=None, root=None,
                     out_dir=None, provenance=None) -> str:
    if verdict is None:
        verdict = assess(result)
    out = out_dir or output_dir(study_name, root)
    os.makedirs(out, exist_ok=True)
    payload = {"comparison": result, "verdict": verdict}
    if provenance is not None:
        payload["provenance"] = provenance
    path = os.path.join(out, "model_comparison.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path
