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

RSSI_NAMES = ["rssi", "rssi_dbm", "rssi(dbm)", "signal", "rx_rssi", "snr_rssi"]
LAT_NAMES = ["latitude", "lat", "gps_lat", "device_lat"]
LON_NAMES = ["longitude", "lon", "lng", "long", "gps_lon", "device_lon"]
SF_NAMES = ["spreading factor", "spreading_factor", "sf", "datarate", "data_rate"]
GATEWAY_NAMES = ["gateway_id", "gateway", "gw_id", "gweui", "gateway_eui"]


def read_csv(source: str, is_text: bool = False):
    """Returns (header, rows). `source` is a path, or CSV text when is_text."""
    handle = io.StringIO(source) if is_text else open(source, newline="")
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

    pts, skipped = [], 0
    for r in rows:
        try:
            rssi = float(r[rc])
            lat = float(r[lac])
            lon = float(r[loc])
        except (TypeError, ValueError):
            skipped += 1
            continue
        pts.append((haversine_m(gw_lat, gw_lon, lat, lon), rssi))

    if not pts:
        raise ValueError("No rows had usable RSSI and coordinates.")

    warnings = sanity_checks(rows, header, [d for d, _ in pts])

    kept = [(d, v) for d, v in pts
            if d >= min_distance_m and (max_distance_m is None or d <= max_distance_m)]
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

    # Checks that need the fitted model. The commonest cause of an absurd
    # exponent is a mistyped gateway position: distances are then unrelated to
    # the real geometry, the regression finds no trend, and nothing upstream
    # notices. A wrong sign is the same failure read the other way, with RSSI
    # apparently improving with distance.
    exponents = [f["path_loss_exponent"] for f in fits]
    if any(e < 0 for e in exponents):
        warnings.append({
            "kind": "negative_exponent",
            "message": ("The fit says the signal gets STRONGER with distance "
                        "(a negative path-loss exponent), which is physically "
                        "impossible. Check the gateway coordinates and that the "
                        "latitude and longitude columns are the right way round."),
        })
    elif any(e > 8 for e in exponents):
        warnings.append({
            "kind": "implausible_exponent",
            "message": (f"The fitted exponent, {max(exponents):.1f}, is far outside "
                        f"the 1.4 to 6.0 range reported in the LoRa propagation "
                        f"literature. Check the gateway coordinates before using "
                        f"this model."),
        })
    if max(f["r_squared"] for f in fits) < 0.15:
        warnings.append({
            "kind": "no_trend",
            "message": (f"The best fit explains only "
                        f"{100 * max(f['r_squared'] for f in fits):.0f}% of the "
                        f"variation in RSSI, so distance barely predicts the signal "
                        f"here. Either the gateway position is wrong or these "
                        f"measurements cannot support a distance-based model."),
        })

    return {
        "columns": {"rssi": rc, "latitude": lac, "longitude": loc},
        "n_rows": len(rows), "n_usable": len(pts), "n_skipped": skipped,
        "n_kept": len(kept), "n_bins": len(binned),
        "distance_min_m": min(d for d, _ in pts),
        "distance_max_m": max(d for d, _ in pts),
        "warnings": warnings,
        "fits": fits,
        "binned": [{"distance_m": d, "rssi_dbm": v, "n": n} for d, v, n in binned],
    }


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
        f"    shadowing_sigma_db={fit['shadowing_sigma_db']:.2f},\n"
        f"    path_loss_source=\"Field fit ({fit['label']}), {fit['n_points']} points, "
        f"{fit['min_distance_m']:.0f} m to {fit['max_distance_m']:.0f} m\",\n"
    )
