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
from typing import Dict, Optional, Sequence, Tuple, Union

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
    # Standard deviation of the log-normal variation about the mean path loss.
    # `shadowing_sigma_db` is fixed per node, which is obstruction belonging to
    # where the node is. `fading_sigma_db` is drawn per packet, which is the
    # channel changing between transmissions. A residual sigma from a field fit
    # mixes the two and cannot tell them apart, so assigning all of it to
    # shadowing is the conservative reading for a static deployment.
    shadowing_sigma_db: float = 0.0
    fading_sigma_db: float = 0.0
    path_loss_source: str = ""

    # --- traffic ------------------------------------------------------------
    # Required in AU915 and AS923, ignored elsewhere. Those plans publish two
    # sets of payload ceilings and the slow data rates differ by more than
    # tenfold between them, so there is no safe default to assume. 0 means no
    # dwell limit, 400 means the 400 ms limit.
    uplink_dwell_time_ms: Optional[int] = None

    payload_bytes: int = 32
    coding_rate: int = 1                # CR index; airtime uses 4/(4+CR)
    send_interval_s: float = 60.0
    capture_threshold_db: float = 6.0
    # 'lorasim' or 'lock'. See `core.resolve_overlap`. LoRaSim's rule stays
    # the default so that no existing study changes unless it says so.
    receiver_model: str = "lorasim"
    # Packets on different spreading factors in one channel. None treats them
    # as orthogonal, LoRaSim's assumption and the default. A name from
    # presets.INTER_SF_REJECTION_DB, or a table of your own as
    # {reference SF: {interfering SF: minimum SIR in dB}}, applies measured
    # rejection instead. See `core.inter_sf_losses`.
    inter_sf_rejection: Optional[Union[str, Dict[int, Dict[int, float]]]] = None
    # Refinements of the lock rule, valid only with receiver_model="lock".
    # `lock_survival` names a table in presets.LOCK_SURVIVAL_DB, or gives one
    # as {SF: minimum SIR in dB}. `header_recapture` lets a stronger packet
    # arriving during the locked packet's header take the receiver over. See
    # `core.resolve_overlap`.
    lock_survival: Optional[Union[str, Dict[int, float]]] = None
    header_recapture: bool = False

    # --- energy, all optional ---
    # `radio` names a transmit-current table in presets, or give the table
    # directly. Leave both unset and no energy figure is produced, which is
    # the default: current draw is a property of the node radio and a guessed
    # one yields a battery estimate that reads as authoritative and is not.
    radio: Optional[str] = None
    tx_current_ma: Optional[Dict[int, float]] = None
    supply_voltage_v: float = 3.0
    # Sleep draw and battery size, needed only for a service-life estimate.
    # Transmit energy ALONE is not a battery life, because the node also
    # draws while idle. Which term dominates depends on the reporting
    # interval and cannot be assumed either way: at a one-minute interval
    # transmitting is nearly all of it, at an interval of hours the sleep
    # draw overtakes it. Without these, `run` reports energy per extracted
    # message and declines to turn it into days.
    sleep_current_ua: Optional[float] = None
    battery_capacity_mah: Optional[float] = None

    # --- steady-state ADR, used only by an 'ADR' scenario ---
    adr_margin_db: float = 10.0
    # None takes the plan's own offsets. An explicit empty tuple disables
    # power control, which isolates the margin's effect from the power
    # control's and is worth running once if you care which is which.
    tx_power_offsets_db: Optional[Sequence[float]] = None

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
        return self.resolved_sensitivity_with_provenance()[0]

    def resolved_sensitivity_with_provenance(self):
        """(table, derived_from). `derived_from` is None when the figures are
        tabulated at this study's bandwidth, and the bandwidth they were
        scaled from otherwise."""
        sfs = self.resolved_spreading_factors()
        if self.sensitivity_dbm:
            return dict(self.sensitivity_dbm), None
        if self.chip:
            return presets.sensitivity_for(self.chip, sfs, self.bw_khz)
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
            receiver_model=self.receiver_model,
            inter_sf_rejection_db=self.resolved_inter_sf_rejection(),
            lock_survival_db=self.resolved_lock_survival(),
            header_recapture=self.header_recapture,
            placement=self.placement,
            placement_polygons_m=self.polygons_m,
            adaptive_sf_options=self.resolved_adaptive_sf_options(),
            adr_margin_db=self.adr_margin_db,
            tx_power_offsets_db=self.resolved_tx_power_offsets(),
            shadowing_sigma_db=self.shadowing_sigma_db,
            fading_sigma_db=self.fading_sigma_db,
            tx_current_ma=self.resolved_tx_current(),
            supply_voltage_v=self.supply_voltage_v,
        )

    def resolved_inter_sf_rejection(self):
        """The inter-SF rejection table, or None for orthogonal spreading
        factors. A named table comes from presets, a given one is used as is
        with its keys made integers."""
        spec = self.inter_sf_rejection
        if spec is None:
            return None
        if isinstance(spec, str):
            return presets.inter_sf_rejection(spec)
        return {int(ref): {int(i): float(v) for i, v in row.items()}
                for ref, row in spec.items()}

    def resolved_lock_survival(self):
        """The locked-packet survival table, or None to keep the capture
        threshold for that decision."""
        spec = self.lock_survival
        if spec is None:
            return None
        if isinstance(spec, str):
            return presets.lock_survival(spec)
        return {int(sf): float(v) for sf, v in spec.items()}

    def resolved_tx_current(self):
        """Transmit current table, or None when no energy figure was asked
        for. An explicit table wins over a named radio."""
        if self.tx_current_ma:
            return {int(k): float(v) for k, v in self.tx_current_ma.items()}
        if self.radio:
            return dict(presets.TX_CURRENT_MA[self.radio.upper()])
        return None

    def resolved_adaptive_sf_options(self):
        """Spreading factors an adaptive scenario may assign, with the ones the
        payload cannot legally use removed.

        A network server does not hand a node a data rate that cannot carry
        its payload, so neither does this. Without the filter, an adaptive
        scenario in US915 with a 32-byte payload would happily place distant
        nodes on DR0, whose ceiling is eleven bytes, and the fixed-SF check
        would be the only thing to catch it.

        Filtering is silent when the plan has no transcribed table, since
        there is then nothing to filter against."""
        opts = tuple(self.adaptive_sf_options or sorted(self.resolved_sensitivity()))
        if presets.region_data_rates(self.region) is None:
            return opts
        keep = []
        for sf in opts:
            found = presets.data_rate_for(self.region, sf, self.bw_khz,
                                          self.uplink_dwell_time_ms)
            if found is None:
                continue
            _dr, max_n = found
            if max_n is None or max_n >= self.payload_bytes:
                keep.append(sf)
        return tuple(keep)

    def dropped_adaptive_sf_options(self):
        """(sf, data rate, ceiling) for each option the payload rules out."""
        opts = tuple(self.adaptive_sf_options or sorted(self.resolved_sensitivity()))
        kept = set(self.resolved_adaptive_sf_options())
        out = []
        for sf in opts:
            if sf in kept:
                continue
            found = presets.data_rate_for(self.region, sf, self.bw_khz,
                                          self.uplink_dwell_time_ms)
            out.append((sf, found[0] if found else None,
                        found[1] if found else None))
        return out

    def resolved_tx_power_offsets(self):
        """Power offsets for an ADR scenario: the study's, else the plan's.

        An explicit empty tuple is not the same as None. It says the nodes
        cannot reduce power, which is a configuration worth simulating, so it
        is passed through rather than replaced by the regional default."""
        if self.tx_power_offsets_db is not None:
            return tuple(self.tx_power_offsets_db)
        return presets.region_tx_power_offsets(self.region, self.tx_power_dbm)

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
    # The data-rate table, where one exists, supersedes this list: it knows
    # which bandwidth each spreading factor runs at, so it can check the pair
    # rather than assuming 125 kHz. See the data-rate block further down.
    has_dr_table = presets.region_data_rates(study.region) is not None
    if not has_dr_table:
        try:
            allowed = presets.region_sfs(study.region)
            outside = [sf for sf in sfs if sf not in allowed]
            if outside:
                errors.append(
                    f"SF{outside} are not 125 kHz uplink data rates in "
                    f"{study.region} (allowed: SF{list(allowed)}). Simulating "
                    f"them would not represent a system that can actually be "
                    f"deployed there."
                )
        except KeyError as e:
            warnings.append(str(e))
    if study.bw_khz != 125 and not has_dr_table:
        warnings.append(
            f"bw_khz = {study.bw_khz} and {study.region} has no transcribed "
            f"data-rate table, so nothing checked that this bandwidth carries "
            f"the spreading factors you are simulating."
        )

    # --- sensitivity ---
    try:
        sens, derived_from = study.resolved_sensitivity_with_provenance()
    except (ValueError, KeyError) as e:
        return errors + [str(e)], warnings, info
    if derived_from is not None:
        warnings.append(
            f"No sensitivity table for {study.chip} at {study.bw_khz} kHz, so "
            f"the figures were derived from its {derived_from} kHz column by "
            f"{10 * math.log10(study.bw_khz / derived_from):+.2f} dB. "
            f"Measured against the one table here that covers several "
            f"bandwidths, that derivation is conservative by 1 to 2 dB "
            f"typically and up to 5 dB, always understating sensitivity and "
            f"so understating range. Report them as derived, or read the "
            f"datasheet and set sensitivity_dbm."
        )
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
    except (ValueError, KeyError) as e:
        # KeyError reaches here from a preset that does not exist, such as an
        # unknown radio. It is reported like any other configuration error
        # rather than escaping as a traceback, so `check` can list it beside
        # the others instead of dying on the first one.
        errors.append(str(e).strip('"\''))
    if cfg is not None:
        for scen in study.scenarios:
            try:
                parse_scenario(scen, cfg)
            except ValueError as e:
                errors.append(str(e))
    # --- data rates: is each scenario a real uplink DR, and does the payload fit? ---
    if not has_dr_table:
        info.append(
            f"{study.region} has no transcribed data-rate table, so the payload "
            f"ceiling was not checked. Confirm by hand that payload_bytes = "
            f"{study.payload_bytes} fits the data rates you are simulating."
        )
    elif cfg is not None:
        used = set()
        for scen in study.scenarios:
            try:
                _, opts = parse_scenario(scen, cfg)
            except ValueError:
                continue
            used.update(opts)

        dwell = study.uplink_dwell_time_ms
        if presets.needs_dwell_time(study.region):
            allowed_dwell = sorted(
                k for k in presets.MAX_APP_PAYLOAD_BYTES[study.region.upper()])
            if dwell is None:
                errors.append(
                    f"{study.region} publishes a different payload ceiling for "
                    f"each uplink dwell-time setting, and at the slow data rates "
                    f"they differ by more than tenfold, so set "
                    f"uplink_dwell_time_ms to one of {allowed_dwell}. There is "
                    f"no safe value to assume on your behalf."
                )
            elif dwell not in allowed_dwell:
                errors.append(
                    f"uplink_dwell_time_ms = {dwell} is not a setting "
                    f"{study.region} defines. Use one of {allowed_dwell}."
                )

        mapped, unchecked = [], []
        for sf in sorted(used):
            found = presets.data_rate_for(study.region, sf, study.bw_khz, dwell)
            if found is None:
                errors.append(
                    f"SF{sf} at {study.bw_khz} kHz is not an uplink data rate in "
                    f"{study.region}. A scenario using it would measure a "
                    f"configuration the band would refuse to carry."
                )
                continue
            dr, max_n = found
            mapped.append(f"SF{sf}=DR{dr}")
            if max_n is None:
                unchecked.append(f"SF{sf}")
            elif max_n == 0:
                errors.append(
                    f"SF{sf} at {study.bw_khz} kHz is {study.region} DR{dr}, "
                    f"which carries no application payload at all under this "
                    f"configuration. A transmission at that data rate cannot "
                    f"exist, so a scenario using it has nothing to measure."
                )
            elif study.payload_bytes > max_n:
                errors.append(
                    f"payload_bytes = {study.payload_bytes}, but SF{sf} at "
                    f"{study.bw_khz} kHz is {study.region} DR{dr}, which carries "
                    f"at most {max_n} bytes of application payload. That packet "
                    f"cannot be sent at this data rate, so its airtime, and every "
                    f"capacity figure derived from it, would describe a "
                    f"transmission the band does not permit."
                )
        if mapped:
            info.append(f"Data rates: {', '.join(mapped)} "
                        f"(payload {study.payload_bytes} B)")
        if unchecked:
            # With every plan's ceilings transcribed this is reachable only
            # when the dwell time is missing or wrong, which has already been
            # reported above as an error. Kept so a future plan added with a
            # partial table degrades to a warning rather than to silence.
            warnings.append(
                f"No payload ceiling available for {', '.join(unchecked)} in "
                f"{study.region}, so it was not checked."
            )

    # --- energy ---
    if study.radio and study.radio.upper() not in presets.TX_CURRENT_MA:
        errors.append(
            f"No transmit current table for radio {study.radio!r}. Known: "
            f"{sorted(presets.TX_CURRENT_MA)}. Give tx_current_ma directly, "
            f"from your radio's datasheet."
        )
    else:
        table = study.resolved_tx_current()
        if table is None:
            if study.sleep_current_ua or study.battery_capacity_mah:
                warnings.append(
                    "sleep_current_ua or battery_capacity_mah is set but no "
                    "radio or tx_current_ma is, so no energy figure can be "
                    "produced and neither will be used."
                )
        else:
            if study.supply_voltage_v <= 0:
                errors.append("supply_voltage_v must be positive.")
            powers = [study.tx_power_dbm]
            offsets = study.resolved_tx_power_offsets()
            if offsets and any(s.upper() == "ADR" for s in study.scenarios):
                powers += [study.tx_power_dbm + o for o in offsets]
            outside = sorted({int(round(p)) for p in powers} - set(table))
            if outside:
                errors.append(
                    f"The transmit current table covers {min(table)} to "
                    f"{max(table)} dBm, but this study transmits at "
                    f"{outside} dBm. Power amplifier stages switch inside the "
                    f"table's range, so a figure outside it cannot be "
                    f"interpolated: extend the table or change the power."
                )
            src = presets.TX_CURRENT_SOURCE.get((study.radio or "").upper())
            info.append(
                f"Energy: {min(table)} to {max(table)} dBm tabulated at "
                f"{study.supply_voltage_v:g} V"
                + (f". {src}" if src else ". Table supplied by the study."))
            if not study.sleep_current_ua:
                info.append(
                    "No sleep_current_ua, so transmit energy and energy per "
                    "extracted message are reported but battery life is not. "
                    "Transmit energy alone is not a service life, and which "
                    "of the two terms dominates depends on the reporting "
                    "interval rather than being the same for every "
                    "deployment."
                )

    # --- adaptive scenarios ---
    if any(s.upper() in ("ADR", "MULTI") for s in study.scenarios):
        try:
            dropped = study.dropped_adaptive_sf_options()
        except (ValueError, KeyError):
            dropped = []
        if dropped:
            info.append(
                "Adaptive scenarios will not use "
                + ", ".join(
                    f"SF{sf}" + (f" (DR{dr}, {n} B ceiling)" if dr is not None
                                 and n is not None else " (not a data rate here)")
                    for sf, dr, n in dropped)
                + f": a {study.payload_bytes} B payload does not fit. A network "
                  f"server would not assign them either."
            )
        if not study.resolved_adaptive_sf_options():
            errors.append(
                f"No spreading factor can carry a {study.payload_bytes} B payload "
                f"in {study.region} at {study.bw_khz} kHz, so an adaptive scenario "
                f"has nothing to assign."
            )

    if any(s.upper() == "ADR" for s in study.scenarios):
        offsets = study.resolved_tx_power_offsets()
        if offsets is None:
            warnings.append(
                f"An ADR scenario is configured but no transmit power offsets "
                f"are available for {study.region} and none were given, so "
                f"nodes will transmit at full power. The scenario then differs "
                f"from MULTI only by its {study.adr_margin_db:g} dB margin, "
                f"which is a legitimate configuration but not what ADR means."
            )
        elif len(offsets) == 0:
            info.append(
                f"ADR with power control disabled: margin {study.adr_margin_db:g} dB, "
                f"every node at {study.tx_power_dbm:g} dBm."
            )
        else:
            info.append(
                f"ADR: margin {study.adr_margin_db:g} dB, transmit power from "
                f"{study.tx_power_dbm:g} down to "
                f"{study.tx_power_dbm + min(offsets):g} dBm in "
                f"{abs(offsets[1] - offsets[0]):g} dB steps."
                if len(offsets) > 1 else
                f"ADR: margin {study.adr_margin_db:g} dB, one power level only."
            )
        if study.adr_margin_db < 0:
            errors.append("adr_margin_db cannot be negative.")

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
    for name, value in (("shadowing_sigma_db", study.shadowing_sigma_db),
                        ("fading_sigma_db", study.fading_sigma_db)):
        if value < 0:
            errors.append(f"{name} is a standard deviation and cannot be negative.")
        elif value > 20:
            warnings.append(
                f"{name} = {value:g} dB. Published log-normal sigmas for LoRa sit "
                f"roughly between 2 and 12 dB. A value this large usually means a "
                f"fit residual that is absorbing something structural, such as a "
                f"mix of spreading factors or two different gateways."
            )
    if study.shadowing_sigma_db == 0 and study.fading_sigma_db == 0:
        info.append(
            "Propagation is deterministic: two nodes the same distance away "
            "receive identical power. Set shadowing_sigma_db to the residual "
            "spread of your fit to model obstruction."
        )
    if (study.path_loss_r_squared is not None and study.path_loss_r_squared < 0.8
            and study.shadowing_sigma_db == 0):
        warnings.append(
            f"The fit explains only {100 * study.path_loss_r_squared:.0f}% of the "
            f"spread in RSSI, and shadowing_sigma_db is 0, so the rest is being "
            f"discarded rather than modelled. `fit_path_loss` reports the "
            f"residual sigma to put here."
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
        info.append(f"Receiver rule: {cfg.receiver_model}, capture threshold "
                    f"{cfg.capture_threshold_db:g} dB")
        table = cfg.inter_sf_rejection_db
        if table is None:
            info.append("Spreading factors: treated as orthogonal "
                        "(inter_sf_rejection is not set)")
        else:
            # Every pair the study could put on one channel needs an entry,
            # or the engine would fail mid-run on the first such overlap.
            missing = [f"SF{a} by SF{b}" for a in sfs for b in sfs
                       if a != b and b not in table.get(a, {})]
            if missing:
                errors.append(
                    f"inter_sf_rejection has no threshold for "
                    f"{', '.join(missing)}. It must cover every pair of "
                    f"spreading factors the study uses.")
            name = study.inter_sf_rejection
            src = (presets.INTER_SF_REJECTION_SOURCE.get(name.upper())
                   if isinstance(name, str) else None)
            info.append("Spreading factors: inter-SF rejection on, "
                        + (src if src else "table supplied by the study."))
        survival = cfg.lock_survival_db
        refined = survival is not None or cfg.header_recapture
        if refined and cfg.receiver_model != "lock":
            # The engine would ignore them, so a study asking for them under
            # LoRaSim's rule has a mistake in it, not a preference.
            errors.append(
                "lock_survival and header_recapture refine the lock receiver "
                "rule and have no effect under receiver_model="
                f"{cfg.receiver_model!r}. Set receiver_model='lock' or remove "
                "them.")
        if survival is not None:
            missing = [f"SF{sf}" for sf in sfs if sf not in survival]
            if missing:
                errors.append(
                    f"lock_survival has no threshold for {', '.join(missing)}. "
                    f"It must cover every spreading factor the study uses.")
            name = study.lock_survival
            src = (presets.LOCK_SURVIVAL_SOURCE.get(name.upper())
                   if isinstance(name, str) else None)
            info.append("Lock survival: per-SF thresholds, "
                        + (src if src else "table supplied by the study."))
        if cfg.header_recapture:
            info.append("Header recapture: on, a later packet stronger by the "
                        "capture threshold arriving in the eight header "
                        "symbols takes the receiver over.")
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


STUDY_FIELD_ORDER = [
    ("name", "identification"), ("site", None), ("description", None),
    ("region", "band and spreading factors"), ("bw_khz", None),
    ("spreading_factors", None),
    ("chip", "gateway"), ("sensitivity_dbm", None), ("n_channels", None),
    ("max_simultaneous_demodulations", None), ("n_gateways", None),
    ("tx_power_dbm", "link budget"), ("tx_antenna_gain_db", None),
    ("rx_antenna_gain_db", None), ("cable_loss_db", None),
    ("path_loss_exponent", "propagation"), ("path_loss_ref_db", None),
    ("path_loss_ref_distance_m", None), ("min_valid_distance_m", None),
    ("path_loss_r_squared", None),
    ("shadowing_sigma_db", None), ("fading_sigma_db", None), ("path_loss_source", None),
    ("uplink_dwell_time_ms", None),
    ("payload_bytes", "traffic"), ("coding_rate", None),
    ("send_interval_s", None), ("capture_threshold_db", None),
    ("receiver_model", None), ("inter_sf_rejection", None),
    ("lock_survival", None), ("header_recapture", None),
    ("adr_margin_db", None), ("tx_power_offsets_db", None),
    ("radio", None), ("tx_current_ma", None), ("supply_voltage_v", None),
    ("sleep_current_ua", None), ("battery_capacity_mah", None),
    ("placement", "node placement"),
    ("scenarios", "experiment design"), ("adaptive_sf_options", None),
    ("node_counts", None), ("sim_time_s", None), ("n_runs", None),
    ("base_seed", None), ("der_threshold", None),
    ("highlight_scenario", "figure"), ("highlight_color", None),
    ("plot_full_xlim", None), ("plot_zoom_xlim", None), ("plot_zoom_ylim", None),
    ("figure_basename", None),
]


def render_study_module(values: dict, use_site_polygon: bool = True,
                        generated_note: str = "") -> str:
    """The text of a study.py from a plain dict of field values.

    Every value is written with repr(), so a quote or newline in a free-text
    field cannot break out of the literal and become code. The generated file
    is an ordinary study.py: it is the record of the run, editable by hand
    afterwards, and nothing about it depends on how it was produced.
    """
    lines = [
        "#!/usr/bin/env python3",
        '"""',
        f"Study definition for {values.get('name', 'this site')}.",
    ]
    if generated_note:
        lines += ["", generated_note]
    lines += [
        "",
        "This is an ordinary study file. Edit it by hand like any other, and",
        "check it into version control: it is the record of how the numbers",
        "were produced.",
        '"""',
        "from loracap import Study",
        "",
    ]
    if use_site_polygon:
        lines.append("from site_polygon import FARM_POLYGONS_M, GATEWAY_LAT, GATEWAY_LON")
        lines.append("")

    lines.append("STUDY = Study(")
    for field, heading in STUDY_FIELD_ORDER:
        if field not in values:
            continue
        v = values[field]
        if v is None and field in ("sensitivity_dbm", "n_channels",
                                   "max_simultaneous_demodulations", "chip",
                                   "adaptive_sf_options", "plot_full_xlim",
                                   "plot_zoom_xlim", "path_loss_r_squared",
                                   "highlight_scenario"):
            continue    # leave the dataclass default rather than writing None
        if heading:
            lines.append(f"    # --- {heading} ---")
        if field == "node_counts" and isinstance(v, (list, tuple)) and len(v) > 8:
            lines.append(f"    {field}=(")
            for i in range(0, len(v), 12):
                lines.append("        " + ", ".join(str(x) for x in v[i:i + 12]) + ",")
            lines.append("    ),")
        else:
            lines.append(f"    {field}={v!r},")
    if use_site_polygon:
        lines += [
            "    polygons_m=FARM_POLYGONS_M,",
            "    gateway_lat=GATEWAY_LAT,",
            "    gateway_lon=GATEWAY_LON,",
        ]
    lines.append(")")
    return "\n".join(lines) + "\n"


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
