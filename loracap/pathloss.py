#!/usr/bin/env python3
"""
loracap.pathloss
================

Fitting a log-distance path-loss model to field measurements.

    L(d) = L(d0) + 10 * n * log10(d / d0)

This is the one parameter group that cannot be borrowed from another site, and
the one most worth getting right, so this module does two things beyond the
arithmetic. It reports the fit both with and without distance binning, because
the choice between them changes the answer and belongs to the user. And it
checks the file for the three contaminations that produce a healthy-looking
but wrong fit: several spreading factors, several gateways, or measurements
from somewhere other than the site.

Standard library only.
"""
from __future__ import annotations

import csv
import io
import math
from typing import Dict, List, Optional, Sequence, Tuple

from . import presets

RSSI_NAMES = ["rssi", "rssi_dbm", "rssi(dbm)", "signal", "rx_rssi", "snr_rssi"]
LAT_NAMES = ["latitude", "lat", "gps_lat", "device_lat"]
LON_NAMES = ["longitude", "lon", "lng", "long", "gps_lon", "device_lon"]
SF_NAMES = ["spreading factor", "spreading_factor", "sf", "datarate", "data_rate"]
GATEWAY_NAMES = ["gateway_id", "gateway", "gw_id", "gweui", "gateway_eui"]


def read_csv(source: str, is_text: bool = False):
    """Returns (header, rows). `source` is a path, or CSV text when is_text."""
    handle = io.StringIO(source) if is_text else open(source, newline="", encoding="utf-8-sig")
    try:
        reader = csv.DictReader(handle)
        return (reader.fieldnames or []), list(reader)
    finally:
        handle.close()


def pick_column(header, candidates, override=None):
    """Matches a column by common spellings. Returns None when nothing matches,
    so the caller can report it rather than guessing a column."""
    if override:
        return override if override in header else None
    lowered = {h.strip().lower(): h for h in header}
    for c in candidates:
        if c in lowered:
            return lowered[c]
    return None


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def linear_fit(xs, ys):
    """Least squares y = a + b*x. Returns (a, b, r_squared, residual_std).

    The residual standard deviation is the part R^2 reports as a fraction and
    then throws away. It is the sigma of the log-normal shadowing term in the
    usual propagation model, so it is a parameter in its own right rather
    than a goodness-of-fit statistic, and `core` can simulate with it."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        raise ValueError(
            "Every retained point is at the same distance, so there is no slope "
            "to fit. The surviving rows probably all come from one spot."
        )
    b = sxy / sxx
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    # two degrees of freedom are spent on the slope and the intercept
    resid_std = math.sqrt(ss_res / (n - 2)) if n > 2 else float("nan")
    return a, b, (1 - ss_res / ss_tot if ss_tot > 0 else float("nan")), resid_std


def distinct_values(rows, header, candidates):
    """(column, set of non-empty values), or (None, None) if absent."""
    lowered = {h.strip().lower(): h for h in header}
    for c in candidates:
        if c in lowered:
            col = lowered[c]
            return col, {str(r[col]).strip() for r in rows
                         if r.get(col) not in (None, "")}
    return None, None


def sanity_checks(rows, header, distances) -> List[dict]:
    """Flags the contaminations that make a wrong fit look healthy. Warnings,
    not errors: only the user knows which subset of the file was intended."""
    out = []

    col, vals = distinct_values(rows, header, SF_NAMES)
    if col and vals and len(vals) > 1:
        out.append({
            "kind": "mixed_spreading_factors",
            "message": (f"Column '{col}' holds {len(vals)} distinct values "
                        f"({', '.join(sorted(vals)[:6])}). Different spreading "
                        f"factors have different receiver sensitivity and are not "
                        f"comparable in one fit. Filter to a single one."),
        })

    col, vals = distinct_values(rows, header, GATEWAY_NAMES)
    if col and vals and len(vals) > 1:
        out.append({
            "kind": "mixed_gateways",
            "message": (f"Column '{col}' holds {len(vals)} distinct values, so the "
                        f"file mixes several gateways. Each has its own position, "
                        f"antenna and height. Filter to the one you are modelling."),
        })

    if distances:
        ds = sorted(distances)
        if ds[-1] > 50000:
            out.append({
                "kind": "implausible_distance",
                "message": (f"The farthest point is {ds[-1]/1000:.0f} km away, far "
                            f"beyond any LoRa link. Those rows are probably from a "
                            f"different site, such as bench testing, or the gateway "
                            f"coordinates are wrong."),
            })
        far = sum(1 for d in ds if d > 30)
        if far < 0.05 * len(ds):
            out.append({
                "kind": "few_far_points",
                "message": (f"Only {far} of {len(ds)} points lie beyond 30 m. A fit "
                            f"resting on so few far points is weak however good its "
                            f"R^2 looks, and the model will be extrapolated across "
                            f"most of the range you simulate."),
            })
    return out


def analyse(
    header,
    rows,
    gw_lat: float,
    gw_lon: float,
    tx_power_dbm: Optional[float] = None,
    net_gain_db: float = 0.0,
    d0_m: float = 100.0,
    min_distance_m: float = 30.0,
    max_distance_m: Optional[float] = None,
    bin_width_m: float = 10.0,
    rssi_col: Optional[str] = None,
    lat_col: Optional[str] = None,
    lon_col: Optional[str] = None,
) -> dict:
    """Full analysis of a measurement file. Raises ValueError with a readable
    message when the file cannot be used."""
    rc = pick_column(header, RSSI_NAMES, rssi_col)
    lac = pick_column(header, LAT_NAMES, lat_col)
    loc = pick_column(header, LON_NAMES, lon_col)
    missing = [n for n, c in (("rssi", rc), ("latitude", lac), ("longitude", loc))
               if c is None]
    if missing:
        raise ValueError(
            f"Could not find a column for {', '.join(missing)}. "
            f"Columns in the file: {header}"
        )

    pts, places, skipped = [], [], 0
    for r in rows:
        try:
            rssi = float(r[rc])
            lat = float(r[lac])
            lon = float(r[loc])
        except (TypeError, ValueError):
            skipped += 1
            continue
        pts.append((haversine_m(gw_lat, gw_lon, lat, lon), rssi))
        places.append((lat, lon))

    if not pts:
        raise ValueError("No rows had usable RSSI and coordinates.")

    warnings = sanity_checks(rows, header, [d for d, _ in pts])

    keep = [i for i, (d, _v) in enumerate(pts)
            if d >= min_distance_m and (max_distance_m is None or d <= max_distance_m)]
    kept = [pts[i] for i in keep]
    if len(kept) < 10:
        raise ValueError(
            f"Only {len(kept)} points survive the {min_distance_m:.0f} m floor. "
            f"That is too few to fit anything meaningful."
        )

    bins: Dict[int, list] = {}
    for d, v in kept:
        bins.setdefault(int(d // bin_width_m), []).append((d, v))
    binned = [
        (sum(d for d, _ in b) / len(b), sum(v for _, v in b) / len(b), len(b))
        for _, b in sorted(bins.items())
    ]

    far = max(d for d, _ in kept)

    def make_fit(points, label, note):
        a, b, r2, resid = linear_fit([math.log10(d) for d, _ in points],
                                     [v for _, v in points])
        n_exp = -b / 10.0
        out = {
            "label": label, "note": note, "n_points": len(points),
            "intercept_dbm": a, "slope": b,
            "path_loss_exponent": n_exp, "r_squared": r2,
            "shadowing_sigma_db": resid,
            "min_distance_m": min_distance_m, "max_distance_m": far,
        }
        if tx_power_dbm is not None:
            rssi_d0 = a + b * math.log10(d0_m)
            l_d0 = tx_power_dbm + net_gain_db - rssi_d0
            l_far = l_d0 + 10 * n_exp * math.log10(far / d0_m)
            out.update({
                "path_loss_ref_db": l_d0,
                "path_loss_ref_distance_m": d0_m,
                "predicted_loss_at_max_db": l_far,
                "predicted_rssi_at_max_dbm": tx_power_dbm + net_gain_db - l_far,
            })
        return out

    fits = [
        make_fit(kept, "unbinned",
                 "every retained measurement; the usual choice in the literature, "
                 "but weighted by sampling density"),
        make_fit([(d, v) for d, v, _ in binned], f"binned ({bin_width_m:.0f} m)",
                 "distance bands averaged first; robust to uneven sampling"),
    ]

    # Fading apart from shadowing (design item 40). A position measured more
    # than once, the same coordinates written for several packets, shows how
    # much the signal varies over time at one place: that is fading. Pooled
    # over every such position, weighted by its degrees of freedom, it needs
    # no threshold on how many packets make a position count. Each position
    # then enters a third fit once, with the mean of its packets, so the
    # spread about that line is shadowing plus what is left of fading in a
    # mean of n packets, fading^2 / n.
    by_place: Dict[Tuple[float, float], list] = {}
    for i in keep:
        by_place.setdefault(places[i], []).append(pts[i])
    fading = pooled_fading(by_place)
    if fading is not None:
        positions = [(sum(d for d, _ in g) / len(g), sum(v for _, v in g) / len(g), len(g))
                     for g in by_place.values()]
        if len({round(d, 6) for d, _v, _n in positions}) >= 3:
            fit = make_fit([(d, v) for d, v, _n in positions], "per position",
                           "each position once, its packets averaged; the spread is "
                           "split into fading, from the positions measured more than "
                           "once, and shadowing")
            residual = fit["shadowing_sigma_db"]
            left = residual ** 2 - fading["sigma_db"] ** 2 * (
                sum(1 / n for _d, _v, n in positions) / len(positions))
            fit.update({
                "n_points": len(positions), "residual_sigma_db": residual,
                "fading_sigma_db": fading["sigma_db"],
                "shadowing_sigma_db": math.sqrt(left) if left > 0 else 0.0,
            })
            fits.append(fit)
            if left <= 0:
                warnings.append({
                    "kind": "no_shadowing_left", "fit": "per position",
                    "message": (f"Across {len(positions)} positions the spread about the "
                                f"line, {residual:.2f} dB, is no larger than the spread "
                                f"between packets at one position, "
                                f"{fading['sigma_db']:.2f} dB, so no shadowing can be told "
                                f"apart from fading. The per position fit sets shadowing "
                                f"to 0 and puts the whole spread in fading."),
                })

    # Checks that need the fitted model, made for each fit on its own (design
    # item 38). They were made on the pair, so one sound fit covered the other:
    # CowNet's unbinned fit, n = 0.64 with R² = 0.06, passed in silence
    # because the binned one had R² = 0.45, and adopting it gave SF7 a reach
    # of 453 209 km.
    for fit in fits:
        found = fit_warnings(fit)
        fit["doubtful"] = bool(found)
        warnings.extend(found)

    return {
        "columns": {"rssi": rc, "latitude": lac, "longitude": loc},
        "n_rows": len(rows), "n_usable": len(pts), "n_skipped": skipped,
        "n_kept": len(kept), "n_bins": len(binned),
        "distance_min_m": min(d for d, _ in pts),
        "distance_max_m": max(d for d, _ in pts),
        "warnings": warnings,
        "fits": fits,
        "fading": fading,
        "binned": [{"distance_m": d, "rssi_dbm": v, "n": n} for d, v, n in binned],
    }


# Below this share of the RSSI spread explained, distance barely predicts the
# signal. A judgement, not a measured value: it is the threshold this check
# has used since it was written, now applied to each fit (design item 38).
NO_TREND_R2 = 0.15

# Above this the exponent is not a terrain at all. Also a judgement, kept from
# the first version of the check: well beyond the highest exponent measured.
IMPLAUSIBLE_EXPONENT = 8.0


def pooled_fading(by_place) -> Optional[dict]:
    """The spread between packets at one position, pooled over every position
    measured more than once, or None when none was (design item 40).

    by_place maps a position to its (distance, rssi) rows. Each position adds
    n - 1 degrees of freedom, so a position measured twice weighs little and
    a node left standing for a hundred packets weighs a hundred."""
    groups, ss, dof = [], 0.0, 0
    for rows in by_place.values():
        n = len(rows)
        if n < 2:
            continue
        mean = sum(v for _, v in rows) / n
        s = sum((v - mean) ** 2 for _, v in rows)
        ss += s
        dof += n - 1
        groups.append({"distance_m": sum(d for d, _ in rows) / n, "n": n,
                       "sigma_db": math.sqrt(s / (n - 1))})
    if dof == 0:
        return None
    return {"sigma_db": math.sqrt(ss / dof), "dof": dof,
            "groups": sorted(groups, key=lambda g: -g["n"])}


def fit_warnings(fit: dict) -> List[dict]:
    """What makes one fit doubtful. The commonest cause of an absurd exponent
    is a mistyped gateway position: distances are then unrelated to the real
    geometry, the regression finds no trend, and nothing upstream notices. A
    wrong sign is the same failure read the other way, with RSSI apparently
    improving with distance."""
    label, n = fit["label"], fit["path_loss_exponent"]
    lo, hi = presets.measured_exponent_span()
    out = []
    if n < 0:
        out.append({
            "kind": "negative_exponent", "fit": label,
            "message": (f"The {label} fit says the signal gets STRONGER with distance "
                        f"(exponent {n:.2f}), which is physically impossible. Check "
                        f"the gateway coordinates and that the latitude and longitude "
                        f"columns are the right way round."),
        })
    elif n > IMPLAUSIBLE_EXPONENT:
        out.append({
            "kind": "implausible_exponent", "fit": label,
            "message": (f"The {label} fit's exponent, {n:.1f}, is far outside the "
                        f"{lo:g} to {hi:g} measured for LoRa across environments. "
                        f"Check the gateway coordinates before using this model."),
        })
    elif not lo <= n <= hi:
        out.append({
            "kind": "exponent_outside_measured", "fit": label,
            "message": (f"The {label} fit's exponent, {n:.2f}, lies outside the "
                        f"{lo:g} to {hi:g} measured for LoRa across environments "
                        f"({presets.TERRAIN_SOURCE}). Every reach it gives rests on "
                        f"that slope, so check the gateway coordinates and the spread "
                        f"of distances before using it."),
        })
    if fit["r_squared"] < NO_TREND_R2:
        out.append({
            "kind": "no_trend", "fit": label,
            "message": (f"The {label} fit explains only {100 * fit['r_squared']:.0f}% "
                        f"of the variation in RSSI, so distance barely predicts the "
                        f"signal. Either the gateway position is wrong or these "
                        f"measurements cannot support a distance-based model."),
        })
    return out


def study_snippet(fit: dict) -> str:
    """The block to paste into a study.py, for one of the fits."""
    if "path_loss_ref_db" not in fit:
        return "# supply tx_power and net_gain to get the path-loss block"
    return (
        f"    path_loss_exponent={fit['path_loss_exponent']:.3f},\n"
        f"    path_loss_ref_db={fit['path_loss_ref_db']:.2f},\n"
        f"    path_loss_ref_distance_m={fit['path_loss_ref_distance_m']:.1f},\n"
        f"    min_valid_distance_m={fit['min_distance_m']:.1f},\n"
        f"    path_loss_r_squared={fit['r_squared']:.3f},\n"
        f"    max_measured_distance_m={fit['max_distance_m']:.1f},\n"
        f"    shadowing_sigma_db={fit['shadowing_sigma_db']:.2f},\n"
        + (f"    fading_sigma_db={fit['fading_sigma_db']:.2f},\n"
           if "fading_sigma_db" in fit else "") +
        f"    path_loss_source=\"Field fit ({fit['label']}), {fit['n_points']} points, "
        f"{fit['min_distance_m']:.0f} m to {fit['max_distance_m']:.0f} m\",\n"
    )
