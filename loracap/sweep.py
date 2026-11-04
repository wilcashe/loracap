#!/usr/bin/env python3
"""
loracap.sweep
=============

Propagation sensitivity sweep: how much does the capacity estimate depend on
the propagation model you assumed?

Why this exists
---------------
The propagation model is the one parameter that cannot be borrowed from
another site, and the one most often unavailable, because fitting it needs a
field campaign. That looks like a blocker. Measurement on the IoT4Cows
deployment shows it usually is not, for a reason worth understanding.

Capacity is set by collisions, and collisions depend on how many nodes
transmit and on how different their received powers are, since the capture
effect lets a strong packet survive a weak one. The propagation model enters
only through that spread, and only while every node stays within range.

Two consequences follow, and both are verifiable with this module:

  - The reference loss (the model's intercept) has NO effect on capacity in
    that regime. Shifting it moves every node's RSSI by the same amount and
    leaves the spread untouched.
  - The path-loss exponent has a mild effect, because it does change the
    spread. Over 2.0 to 3.0 the measured change on one real site was about
    11%.

What dominates instead is a binary question: does the assumed model leave the
whole site within range? While the answer is yes, the capacity estimate is
robust and an assumed model is defensible if declared. Once the answer is no,
the deployment is coverage-limited, the model decides the result, and no
assumed exponent can settle it. Then you need measurements.

This module sweeps the exponent, reports capacity across it, and says which
regime the site is in.

On the default range
--------------------
The default span of 2.0 to 3.5 is a BRACKET, wide enough to contain most
terrestrial environments. It is not a recommendation for any particular site,
and this module deliberately ships no terrain-to-exponent lookup table: such
values are site- and frequency-specific, and a plausible-looking default would
be used without being checked.

Narrow the range using a published model for terrain comparable to yours, and
cite that source in your write-up.

`presets.TERRAIN_EXPONENTS` holds ranges observed in published LoRa campaigns
per environment, and `--terrain rural` uses them. They are context for how wide
the plausible span really is, not values to adopt: see the cautions recorded
alongside them.

Two measured results worth knowing when judging a range. Urban campaigns have
fitted exponents below 2, so free space is not a floor. And an almond orchard
at 904.3 MHz, essentially the US915 frequency, fitted 2.95 (Yang, Chen, Chen
and Du, "Link Quality Modeling for LoRa Networks in Orchards", IPSN 2023,
doi 10.1145/3583120.3586969), high enough that a wooded or planted site can
fall into the coverage-limited regime where an assumed model settles nothing.
"""
from __future__ import annotations

import dataclasses
import json
import os
from typing import Dict, List, Optional, Sequence

from .core import SimConfig, max_distance_m, polygons_max_radius_m, run_batch
from .study import Study, output_dir

SWEEP_JSON = "propagation_sweep.json"

# Free-space propagation.
#
# It is tempting to treat this as a hard floor, and an earlier version of this
# module did. That is wrong. Exponents below 2 are measured in practice where
# the environment guides the signal rather than letting it spread freely: a
# large-scale urban LoRa campaign in Bonn at 868 MHz fitted n = 1.58
# (Rademacher et al., "Path Loss in Urban LoRa Networks", arXiv:2109.07768),
# which the authors attribute to an elevated gateway and street-canyon
# waveguiding over multi-kilometre links.
#
# So a value below 2 is unusual and worth questioning, but it is not
# impossible, and the sweep warns rather than refusing.
FREE_SPACE_EXPONENT = 2.0


def exponent_range(low: float = 2.0, high: float = 3.5, steps: int = 7) -> List[float]:
    """Evenly spaced exponents. See the module docstring on choosing a range."""
    if steps < 2:
        raise ValueError("steps must be at least 2")
    if high <= low:
        raise ValueError("high must exceed low")
    if low < FREE_SPACE_EXPONENT:
        import warnings
        warnings.warn(
            f"low = {low} is below free-space propagation (n = {FREE_SPACE_EXPONENT}). "
            f"That is measured in waveguiding environments such as urban canyons "
            f"with an elevated gateway, but it is unusual over open terrain. "
            f"Check that it is what you meant.",
            stacklevel=2,
        )
    step = (high - low) / (steps - 1)
    return [round(low + i * step, 3) for i in range(steps)]


def find_capacity(
    cfg: SimConfig,
    scenario: str,
    sim_time_ms: float,
    n_runs: int,
    base_seed: int,
    threshold: float = 0.9,
    max_nodes: int = 20000,
) -> Optional[float]:
    """Node count at which mean DER crosses `threshold`, found by bisection.

    DER falls monotonically with node count, so bisection reaches the crossing
    in far fewer simulations than a fixed grid, and is not limited to the grid's
    resolution. Returns None when the curve does not cross within max_nodes, or
    when it is already below threshold at a single node.
    """
    cache: Dict[int, float] = {}

    def der(n: int) -> float:
        if n not in cache:
            cache[n] = run_batch(cfg, n, sim_time_ms, scenario, n_runs, base_seed)["der_mean"]
        return cache[n]

    if der(1) < threshold:
        return None     # cannot sustain even one node: out of range, not congested

    lo, hi = 1, 2
    while der(hi) >= threshold:
        lo = hi
        hi *= 2
        if hi > max_nodes:
            return None     # no crossing within the searched range
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if der(mid) >= threshold:
            lo = mid
        else:
            hi = mid

    d_lo, d_hi = der(lo), der(hi)
    if d_lo == d_hi:
        return float(lo)
    return lo + (d_lo - threshold) / (d_lo - d_hi) * (hi - lo)


def sweep_propagation(
    study: Study,
    exponents: Optional[Sequence[float]] = None,
    scenario: Optional[str] = None,
    n_runs: Optional[int] = None,
    threshold: Optional[float] = None,
    progress: bool = True,
) -> dict:
    """Runs the capacity search once per exponent, holding everything else fixed.

    Only the exponent is swept. The reference loss is left alone deliberately:
    it provably does not affect capacity while the site is covered, and sweeping
    it would add runtime while teaching nothing. `verify_intercept_invariance`
    checks that claim rather than asking you to take it on faith.
    """
    base = study.to_sim_config()
    scenario = scenario or study.highlight_scenario or study.scenarios[0]
    n_runs = n_runs or study.n_runs
    threshold = threshold if threshold is not None else study.der_threshold
    exponents = list(exponents) if exponents else exponent_range()
    # Always include the study's own exponent, so the table shows where the
    # configured model sits relative to the alternatives.
    if not any(abs(e - study.path_loss_exponent) < 1e-9 for e in exponents):
        if min(exponents) < study.path_loss_exponent < max(exponents):
            exponents = sorted(exponents + [study.path_loss_exponent])

    if study.placement == "polygon" and study.polygons_m:
        site_radius = polygons_max_radius_m(study.polygons_m)
        placement_note = None
    else:
        site_radius = None
        placement_note = (
            "placement is 'disc', so the simulated area is derived from the link "
            "budget and changes with every exponent. Node density therefore varies "
            "across the sweep and the comparison is not like-for-like. Run the "
            "sweep against a polygon site for an interpretable result."
        )

    rows = []
    for i, n_exp in enumerate(exponents, 1):
        cfg = dataclasses.replace(base, path_loss_exponent=n_exp)
        reach = max_distance_m(cfg, min(cfg.sensitivity_dbm[sf]
                                        for sf in _scenario_sfs(scenario, cfg)))
        covered = None if site_radius is None else bool(reach >= site_radius)
        capacity = find_capacity(cfg, scenario, study.sim_time_ms, n_runs,
                                 study.base_seed, threshold)
        rows.append({
            "path_loss_exponent": n_exp,
            "reach_m": reach,
            "site_radius_m": site_radius,
            "covers_site": covered,
            "capacity": capacity,
        })
        if progress:
            cov = "-" if covered is None else ("yes" if covered else "NO")
            cap = f"{capacity:.1f}" if capacity else "no crossing"
            print(f"  [{i}/{len(exponents)}] n={n_exp:<5} reach={reach:>7.0f} m  "
                  f"covers={cov:<3}  capacity={cap}", flush=True)

    return {
        "study": study.name,
        "scenario": scenario,
        "der_threshold": threshold,
        "n_runs": n_runs,
        "site_radius_m": site_radius,
        "placement": study.placement,
        "placement_note": placement_note,
        "fitted_exponent": study.path_loss_exponent,
        "results": rows,
    }


def _scenario_sfs(scenario: str, cfg: SimConfig):
    from .core import parse_scenario
    _, opts = parse_scenario(scenario, cfg)
    return opts


def verify_intercept_invariance(
    study: Study,
    offsets_db: Sequence[float] = (-10.0, -5.0, 0.0, 5.0),
    scenario: Optional[str] = None,
    n_runs: Optional[int] = None,
    n_nodes: Optional[int] = None,
) -> dict:
    """Checks, rather than assumes, that the model's intercept does not change
    capacity while the site stays covered.

    Shifts the reference loss by each offset and reports the resulting DER at a
    fixed node count. Values that agree to several decimals confirm the
    invariance. A disagreement means some node has fallen out of range, which is
    itself the useful finding.
    """
    base = study.to_sim_config()
    scenario = scenario or study.highlight_scenario or study.scenarios[0]
    n_runs = n_runs or study.n_runs
    if n_nodes is None:
        n_nodes = max(10, int(len(study.node_counts) and study.node_counts[len(study.node_counts) // 2]))

    out = []
    for off in offsets_db:
        cfg = dataclasses.replace(base, path_loss_ref_db=base.path_loss_ref_db + off)
        r = run_batch(cfg, n_nodes, study.sim_time_ms, scenario, n_runs, study.base_seed)
        out.append({
            "offset_db": off,
            "path_loss_ref_db": cfg.path_loss_ref_db,
            "der_mean": r["der_mean"],
            "lost_signal_mean": r["lost_signal_mean"],
        })
    ders = [o["der_mean"] for o in out]
    return {
        "scenario": scenario,
        "n_nodes": n_nodes,
        "n_runs": n_runs,
        "results": out,
        "max_der_difference": max(ders) - min(ders),
        "invariant": (max(ders) - min(ders)) < 1e-6
                     and all(o["lost_signal_mean"] == 0 for o in out),
    }


INTERCEPT_JSON = "intercept_invariance.json"


def write_sweep(study_name: str, sweep: dict, root=None, out_dir=None,
                provenance=None) -> str:
    return _write(SWEEP_JSON, study_name, sweep, root, out_dir, provenance)


def write_invariance(study_name: str, inv: dict, root=None, out_dir=None,
                     provenance=None) -> str:
    return _write(INTERCEPT_JSON, study_name, inv, root, out_dir, provenance)


def _write(filename, study_name, data, root, out_dir, provenance):
    out = out_dir or output_dir(study_name, root)
    os.makedirs(out, exist_ok=True)
    payload = dict(data)
    if provenance is not None:
        payload["provenance"] = provenance
    path = os.path.join(out, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def format_sweep(sweep: dict) -> str:
    rows = sweep["results"]
    site_r = sweep["site_radius_m"]
    fitted = sweep["fitted_exponent"]

    lines = [
        f"Propagation sensitivity sweep: {sweep['study']}",
        f"  scenario {sweep['scenario']}, DER threshold {sweep['der_threshold']}, "
        f"{sweep['n_runs']} runs per point",
    ]
    if site_r is not None:
        lines.append(f"  site extends {site_r:.0f} m from the gateway")
    lines.append("")
    lines.append(f"  {'exponent':>9}{'reach':>11}{'covers site':>13}{'capacity':>14}")
    lines.append("  " + "-" * 47)
    for r in rows:
        cov = "-" if r["covers_site"] is None else ("yes" if r["covers_site"] else "NO")
        cap = f"{r['capacity']:.1f}" if r["capacity"] else "no crossing"
        mark = "   <- this study" if abs(r["path_loss_exponent"] - fitted) < 1e-9 else ""
        lines.append(f"  {r['path_loss_exponent']:>9.2f}{r['reach_m']:>9.0f} m"
                     f"{cov:>13}{cap:>14}{mark}")
    lines.append("")

    if sweep.get("placement_note"):
        import textwrap
        lines.append("  NOTE")
        lines.extend("    " + l for l in
                     textwrap.wrap(sweep["placement_note"], width=68))
        lines.append("")
        return "\n".join(lines)

    covered = [r for r in rows if r["covers_site"] and r["capacity"]]
    uncovered = [r for r in rows if r["covers_site"] is False]

    lines.append("  Verdict")
    if not covered:
        lines.append("    No exponent in the swept range leaves the whole site within")
        lines.append("    range. This deployment is coverage-limited, so the capacity")
        lines.append("    figure is decided by the propagation model rather than by")
        lines.append("    collisions. An assumed model cannot settle it: field")
        lines.append("    measurements are required.")
    else:
        caps = [r["capacity"] for r in covered]
        lo, hi = min(caps), max(caps)
        mid = (lo + hi) / 2
        spread_pct = 100 * (hi - lo) / mid if mid else 0
        ns = [r["path_loss_exponent"] for r in covered]
        lines.append(f"    While the site stays covered (n from {min(ns):.2f} to "
                     f"{max(ns):.2f}), capacity")
        lines.append(f"    runs from {lo:.0f} to {hi:.0f} nodes, a spread of "
                     f"{spread_pct:.0f}% about {mid:.0f}.")
        if spread_pct < 20:
            lines.append("    The estimate is robust to the propagation model in this")
            lines.append("    regime. An assumed model is defensible provided it is")
            lines.append("    declared as assumed and the coverage check is reported.")
        else:
            lines.append("    That spread is wide enough to matter. Narrow the exponent")
            lines.append("    range with a source for your terrain, or measure.")
        if uncovered:
            first_bad = min(r["path_loss_exponent"] for r in uncovered)
            lines.append("")
            lines.append(f"    From n = {first_bad:.2f} upward the site is no longer fully")
            lines.append("    covered and the regime changes: capacity there is limited by")
            lines.append("    range, not by collisions. If your terrain could plausibly be")
            lines.append("    that lossy, the sweep cannot settle the answer and you need")
            lines.append("    field measurements.")
    lines.append("")
    return "\n".join(lines)


def format_invariance(inv: dict) -> str:
    lines = [
        "Intercept invariance check",
        f"  scenario {inv['scenario']}, {inv['n_nodes']} nodes, {inv['n_runs']} runs",
        "",
        f"  {'offset':>8}{'L(d0)':>10}{'DER':>10}{'weak-signal losses':>21}",
        "  " + "-" * 49,
    ]
    for r in inv["results"]:
        lines.append(f"  {r['offset_db']:>+7.1f} dB{r['path_loss_ref_db']:>9.1f}"
                     f"{r['der_mean']:>10.4f}{r['lost_signal_mean']:>21.1f}")
    lines.append("")
    if inv["invariant"]:
        lines.append("  DER is identical across every offset, and no packet was lost to")
        lines.append("  weak signal. The model's intercept does not affect capacity in")
        lines.append("  this regime: shifting it moves every node's RSSI equally and")
        lines.append("  leaves the spread that drives the capture effect unchanged.")
        lines.append("  Only the exponent needs sweeping.")
    else:
        lines.append(f"  DER varies by {inv['max_der_difference']:.4f} across offsets, so the")
        lines.append("  intercept is NOT neutral here. That means some nodes fall out of")
        lines.append("  range at the lossier offsets: check the weak-signal column. The")
        lines.append("  site is close to its coverage limit, and the propagation model")
        lines.append("  matters for this deployment.")
    lines.append("")
    return "\n".join(lines)
