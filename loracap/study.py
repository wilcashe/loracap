#!/usr/bin/env python3
"""
loracap.study
======================

A `Study` is one simulation campaign: one site, one radio configuration, one
set of scenarios. Everything a study needs is declared in a single
`studies/<name>/study.py`, which this module loads, validates and converts into
the `SimConfig` the engine consumes.

Times are given in SECONDS here, because that is how deployments are described.
The engine works in milliseconds, and the conversion happens in one place.
"""
from __future__ import annotations

import importlib.util
import math
import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple

from . import presets
from .core import (
    SimConfig, max_distance_m, parse_scenario, point_in_polygons,
    polygons_area_m2, polygons_bounds, polygons_max_radius_m,
)

STUDIES_DIRNAME = "studies"


def node_counts_logspace(low: int, high: int, count: int = 27):
    """Log-spaced, de-duplicated integer node counts.

    Log spacing is the sensible default because scenarios cross the DER
    threshold at very different node counts. A linear grid either wastes most
    of its points above the crossing of the slowest scenario, or resolves the
    fastest one poorly.
    """
    if low < 1 or high <= low or count < 2:
        raise ValueError("need 1 <= low < high and count >= 2")
    raw = [low * (high / low) ** (i / (count - 1)) for i in range(count)]
    return sorted({int(round(v)) for v in raw})


@dataclass
class Study:
    """One simulation campaign. See studies/_template/study.py for a commented
    starting point."""

    # --- identification -----------------------------------------------------
    name: str
    site: str = ""                      # free text: where this is, for the report
    description: str = ""

    # --- band and spreading factors ----------------------------------------
    region: str = "US915"               # used to validate the SFs below
    bw_khz: int = 125
    spreading_factors: Sequence[int] = ()   # empty -> taken from the region

    # --- gateway -----------------------------------------------------------
    chip: Optional[str] = None          # e.g. "SX1301"; fills the three fields
                                        # below from presets when they are None
    sensitivity_dbm: Optional[Dict[int, float]] = None
    n_channels: Optional[int] = None
    max_simultaneous_demodulations: Optional[int] = None
    n_gateways: int = 1

    # --- link budget --------------------------------------------------------
    tx_power_dbm: float = 14.0
    tx_antenna_gain_db: float = 0.0
    rx_antenna_gain_db: float = 0.0
    cable_loss_db: float = 0.0

    # --- propagation: L(d) = path_loss_ref_db + 10*n*log10(d/d0) ------------
    path_loss_exponent: float = 2.0
    path_loss_ref_db: float = 0.0
    path_loss_ref_distance_m: float = 100.0
    min_valid_distance_m: float = 30.0
    path_loss_r_squared: Optional[float] = None   # recorded for the report only
    path_loss_source: str = ""

    # --- traffic ------------------------------------------------------------
    payload_bytes: int = 32
    coding_rate: int = 1                # CR index; airtime uses 4/(4+CR)
    send_interval_s: float = 60.0
    capture_threshold_db: float = 6.0

    # --- node placement -----------------------------------------------------
    placement: str = "polygon"          # "polygon" or "disc"
    polygons_m: Optional[Sequence[Sequence[Tuple[float, float]]]] = None
    gateway_lat: Optional[float] = None
    gateway_lon: Optional[float] = None

    # --- experiment design --------------------------------------------------
    scenarios: Sequence[str] = ("SF7", "SF10", "MULTI")
    adaptive_sf_options: Optional[Sequence[int]] = None
    node_counts: Sequence[int] = field(default_factory=lambda: node_counts_logspace(3, 300))
    sim_time_s: float = 3600.0
    n_runs: int = 30
    base_seed: int = 99
    der_threshold: float = 0.9

    # --- figure -------------------------------------------------------------
    highlight_scenario: Optional[str] = None     # drawn in colour; others grey
    highlight_color: str = "#1f6fb2"
    plot_full_xlim: Optional[Tuple[float, float]] = None   # None -> from node_counts
    plot_zoom_xlim: Optional[Tuple[float, float]] = None   # None -> around crossings
    plot_zoom_ylim: Tuple[float, float] = (0.75, 1.0)
    figure_basename: str = "capacity"

    # ------------------------------------------------------------------ #

    @property
    def net_antenna_gain_db(self) -> float:
        return self.tx_antenna_gain_db + self.rx_antenna_gain_db - self.cable_loss_db

    def resolved_spreading_factors(self):
        if self.spreading_factors:
            return tuple(sorted(self.spreading_factors))
        return presets.region_sfs(self.region)

    def resolved_sensitivity(self):
        sfs = self.resolved_spreading_factors()
        if self.sensitivity_dbm:
            return dict(self.sensitivity_dbm)
        if self.chip:
            return presets.sensitivity_for(self.chip, sfs)
        raise ValueError(
            f"study {self.name!r}: set either sensitivity_dbm or chip. There is "
            f"no default sensitivity, because guessing one would silently change "
            f"every result."
        )

    def resolved_n_channels(self) -> int:
        if self.n_channels is not None:
            return self.n_channels
        if self.chip and self.chip in presets.N_UPLINK_CHANNELS:
            return presets.N_UPLINK_CHANNELS[self.chip]
        raise ValueError(f"study {self.name!r}: set n_channels (or a known chip).")

    def resolved_max_demod(self) -> Optional[int]:
        if self.max_simultaneous_demodulations is not None:
            return self.max_simultaneous_demodulations
        if self.chip and self.chip in presets.MAX_SIMULTANEOUS_DEMODULATIONS:
            return presets.MAX_SIMULTANEOUS_DEMODULATIONS[self.chip]
        return None     # None disables the limit, which is a valid choice

    def to_sim_config(self) -> SimConfig:
        return SimConfig(
            payload_bytes=self.payload_bytes,
            coding_rate=self.coding_rate,
            tx_power_dbm=self.tx_power_dbm,
            net_antenna_gain_db=self.net_antenna_gain_db,
            path_loss_exponent=self.path_loss_exponent,
            path_loss_ref_db=self.path_loss_ref_db,
            path_loss_ref_distance_m=self.path_loss_ref_distance_m,
            min_valid_distance_m=self.min_valid_distance_m,
            sensitivity_dbm=self.resolved_sensitivity(),
            bw_khz=self.bw_khz,
            n_channels=self.resolved_n_channels(),
            max_simultaneous_demodulations=self.resolved_max_demod(),
            avg_send_interval_ms=self.send_interval_s * 1000.0,
            capture_threshold_db=self.capture_threshold_db,
            placement=self.placement,
            placement_polygons_m=self.polygons_m,
            adaptive_sf_options=self.adaptive_sf_options,
        )

    @property
    def sim_time_ms(self) -> float:
        return self.sim_time_s * 1000.0


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def studies_root(start: Optional[str] = None) -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(start or here, STUDIES_DIRNAME)


def list_studies(root: Optional[str] = None):
    root = root or studies_root()
    if not os.path.isdir(root):
        return []
    return sorted(
        d for d in os.listdir(root)
        if os.path.isfile(os.path.join(root, d, "study.py"))
    )


def load_study(name: str, root: Optional[str] = None) -> Study:
    root = root or studies_root()
    path = os.path.join(root, name, "study.py")
    if not os.path.isfile(path):
        available = list_studies(root)
        raise FileNotFoundError(
            f"No study named {name!r} (looked for {path}). "
            f"Available: {', '.join(available) if available else 'none'}"
        )
    # The study's own directory goes on sys.path while it loads, so that
    # `from site_polygon import ...` resolves to the file sitting next to it.
    import sys
    directory = os.path.join(root, name)
    spec = importlib.util.spec_from_file_location(f"study_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, directory)
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(directory)
        except ValueError:
            pass
        # drop the site module too, so two studies in one process do not share it
        sys.modules.pop("site_polygon", None)
    if not hasattr(module, "STUDY"):
        raise AttributeError(f"{path} must define a module-level STUDY = Study(...)")
    study = module.STUDY
    if not isinstance(study, Study):
        raise TypeError(f"{path}: STUDY must be a Study instance, got {type(study)}")
    return study


def study_dir(name: str, root: Optional[str] = None) -> str:
    return os.path.join(root or studies_root(), name)


def output_dir(name: str, root: Optional[str] = None) -> str:
    d = os.path.join(study_dir(name, root), "outputs")
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(study: Study):
    """Returns (errors, warnings, info). Errors must be fixed before running.
    Warnings are things worth a second look that are not necessarily wrong."""
    errors, warnings, info = [], [], []

    # --- band and spreading factors ---
    try:
        sfs = study.resolved_spreading_factors()
    except KeyError as e:
        return [str(e)], warnings, info
    try:
        allowed = presets.region_sfs(study.region)
        outside = [sf for sf in sfs if sf not in allowed]
        if outside:
            errors.append(
                f"SF{outside} are not uplink data rates at {study.bw_khz} kHz in "
                f"{study.region} (allowed: SF{list(allowed)}). Simulating them "
                f"would not represent a system that can actually be deployed there."
            )
    except KeyError as e:
        warnings.append(str(e))
    if study.bw_khz != 125:
        warnings.append(
            f"bw_khz = {study.bw_khz}. The regional SF check and the preset "
            f"sensitivity tables both assume 125 kHz. Confirm your sensitivity "
            f"values correspond to {study.bw_khz} kHz."
        )

    # --- sensitivity ---
    try:
        sens = study.resolved_sensitivity()
    except (ValueError, KeyError) as e:
        return errors + [str(e)], warnings, info
    for sf in sfs:
        if sf not in sens:
            errors.append(f"sensitivity_dbm has no entry for SF{sf}.")
    if sens:
        ordered = sorted(sens)
        for a, b in zip(ordered, ordered[1:]):
            if sens[b] >= sens[a]:
                warnings.append(
                    f"sensitivity at SF{b} ({sens[b]} dBm) is not better than at "
                    f"SF{a} ({sens[a]} dBm). A higher SF should be more sensitive. "
                    f"Check the table."
                )

    # --- scenarios ---
    cfg = None
    try:
        cfg = study.to_sim_config()
    except ValueError as e:
        errors.append(str(e))
    if cfg is not None:
        for scen in study.scenarios:
            try:
                parse_scenario(scen, cfg)
            except ValueError as e:
                errors.append(str(e))
    if study.highlight_scenario and study.highlight_scenario not in study.scenarios:
        warnings.append(
            f"highlight_scenario {study.highlight_scenario!r} is not in scenarios "
            f"{list(study.scenarios)}, so nothing will be highlighted."
        )

    # --- propagation model ---
    if study.path_loss_ref_db <= 0:
        errors.append("path_loss_ref_db must be positive (path loss at d0, in dB).")
    if study.min_valid_distance_m > study.path_loss_ref_distance_m:
        warnings.append(
            f"d0 = {study.path_loss_ref_distance_m} m is below the fit's validity "
            f"floor of {study.min_valid_distance_m} m, so the reference point lies "
            f"outside the range the model was fitted over. The model still works, "
            f"but quoting L(d0) in a paper would be quoting an extrapolation."
        )
    if not study.path_loss_source:
        warnings.append(
            "path_loss_source is empty. Record where the propagation model came "
            "from: it is the single most site-specific parameter here, and the "
            "first thing a reviewer will ask about."
        )

    # --- placement ---
    if study.placement == "polygon":
        if not study.polygons_m:
            errors.append("placement='polygon' but polygons_m is empty.")
        else:
            area_ha = polygons_area_m2(study.polygons_m) / 10000.0
            rmax = polygons_max_radius_m(study.polygons_m)
            info.append(f"Deployment area: {area_ha:.2f} ha, "
                        f"farthest point {rmax:.0f} m from the gateway")
            if not point_in_polygons(0.0, 0.0, study.polygons_m):
                warnings.append(
                    "The gateway (origin) falls outside the polygon. If that is "
                    "not intentional, the gateway coordinates used when converting "
                    "the KML were probably wrong."
                )
            if cfg is not None:
                for scen in study.scenarios:
                    try:
                        _, opts = parse_scenario(scen, cfg)
                    except ValueError:
                        continue
                    reach = max_distance_m(cfg, min(sens[sf] for sf in opts))
                    if reach < rmax:
                        warnings.append(
                            f"{scen} reaches {reach:.0f} m but the site extends to "
                            f"{rmax:.0f} m, so some nodes will be out of range and "
                            f"their packets counted as weak-signal losses."
                        )
                    elif scen != "MULTI" and reach > 3 * rmax:
                        info.append(
                            f"{scen} reaches {reach:.0f} m, well beyond the site's "
                            f"{rmax:.0f} m. Range is not the binding constraint here."
                        )
    elif study.placement != "disc":
        errors.append(f"placement must be 'polygon' or 'disc', not {study.placement!r}")

    # --- experiment design ---
    if len(study.node_counts) < 4:
        errors.append("node_counts needs at least four values to resolve a curve.")
    if list(study.node_counts) != sorted(set(study.node_counts)):
        errors.append("node_counts must be sorted and free of duplicates.")
    if min(study.node_counts, default=0) < 1:
        errors.append("node_counts must be positive.")
    if study.n_runs < 20:
        warnings.append(
            f"n_runs = {study.n_runs}. Below about 20 the standard deviation is "
            f"itself noisy, and reviewers of LoRa scalability work routinely ask "
            f"for 20 to 30 repetitions."
        )
    if study.sim_time_s < 600:
        tx_per_node = study.sim_time_s / study.send_interval_s
        warnings.append(
            f"sim_time_s = {study.sim_time_s:.0f} gives about {tx_per_node:.0f} "
            f"transmissions per node. Short runs under-represent collisions."
        )
    if not 0 < study.der_threshold < 1:
        errors.append("der_threshold must lie strictly between 0 and 1.")

    if cfg is not None:
        info.append(f"Channels: {cfg.n_channels}, simultaneous demodulations: "
                    f"{cfg.max_simultaneous_demodulations}, gateways: {study.n_gateways}")
        # Reach is only meaningful once the propagation model is real. With a
        # placeholder model it comes out in thousands of kilometres, which would
        # bury the actual error under nonsense.
        if study.path_loss_ref_db > 0:
            for sf in sfs:
                info.append(f"  SF{sf}: sensitivity {sens[sf]:+.1f} dBm -> "
                            f"reach {max_distance_m(cfg, sens[sf]):.0f} m")
        else:
            info.append("  (per-SF reach not shown: the propagation model is "
                        "not configured yet)")
    if study.n_gateways != 1:
        errors.append(
            f"n_gateways = {study.n_gateways}. The engine models a single "
            f"receiver. Multi-gateway reception would need core.py extended, "
            f"not just a configuration change."
        )

    return errors, warnings, info


def format_report(study: Study, errors, warnings, info) -> str:
    lines = [f"Study: {study.name}"]
    if study.site:
        lines.append(f"Site:  {study.site}")
    lines.append(f"Band:  {study.region}, {study.bw_khz} kHz, "
                 f"SF{list(study.resolved_spreading_factors())}")
    lines.append(f"Scenarios: {', '.join(study.scenarios)}")
    lines.append(f"Design: {len(study.node_counts)} node counts, {study.n_runs} runs "
                 f"each, {study.sim_time_s:.0f} s simulated")
    lines.append("")
    for item in info:
        lines.append(f"  {item}")
    if warnings:
        lines.append("")
        for w in warnings:
            lines.append(f"  WARNING: {w}")
    if errors:
        lines.append("")
        for e in errors:
            lines.append(f"  ERROR: {e}")
    lines.append("")
    lines.append("Configuration is valid." if not errors
                 else f"{len(errors)} error(s) must be fixed before running.")
    return "\n".join(lines)
