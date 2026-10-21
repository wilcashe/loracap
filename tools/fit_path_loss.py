#!/usr/bin/env python3
"""
fit_path_loss.py
================

Fits a log-distance path-loss model to field measurements, and prints the block
you paste into your study.

    L(d) = L(d0) + 10 * n * log10(d / d0)

This is the one parameter group that cannot be borrowed from another site. Path
loss depends on terrain, vegetation, antenna height and the gateway's position
within the site, so a model fitted elsewhere will not transfer, however similar
the two places look.

Input
-----
A CSV with, at minimum, columns for RSSI, latitude and longitude, one row per
received message:

    rssi,latitude,longitude
    -83,3.917401,-73.820015
    -91,3.918220,-73.821540
    -124,3.919180,-73.803000

RSSI in dBm as the gateway reports it, coordinates in decimal degrees. Any
other columns are ignored, so an unmodified gateway or network-server export
usually works as is. Column names are auto-detected from common spellings
(rssi / rssi_dbm / signal, latitude / lat, longitude / lon / lng) and can be
overridden with --rssi-col, --latitude-col and --longitude-col. Run with
--columns to see what is in your file.

WHAT YOU MUST FILTER OUT FIRST
------------------------------
The file should contain only messages from the deployment you are modelling,
at ONE spreading factor and ONE gateway. Mixing in bench tests from another
location, several spreading factors, or several gateways produces a fit that
looks perfectly healthy and is wrong, because each of those changes the RSSI
for reasons that have nothing to do with distance.

This script checks for all three and warns, but it cannot know which subset
you meant to keep, so the filtering is yours to do.

Method
------
Two fits are reported, because the choice between them changes the answer and
is yours to make, not the tool's.

The UNBINNED fit uses every retained measurement. It is what most published
LoRa path-loss studies do, so it is the comparable choice, but it is dominated
by wherever the campaign happened to spend the most time.

The BINNED fit averages measurements within distance bins first, so each
distance band counts once regardless of how many samples fell in it. This is
more robust when sampling is very uneven, which it usually is, since a mobile
campaign lingers near the gateway and passes quickly through the far field.

Pick one, paste it, and say in your write-up which you used and why. They can
differ by enough to matter: on one real dataset the exponent moved from 2.07
binned to 2.17 unbinned.

Points closer than --min-distance are excluded: very near the gateway the
receiver front-end compresses, so reported RSSI understates the true level and
would bias the fit. The same floor is then recorded in the study, so the model
is never evaluated below the range it was fitted over.

Usage
-----
    python3 fit_path_loss.py field.csv --lat 3.91915 --lon -73.82184 \\
        --tx-power 22 --net-gain 9

    # inspect the columns first if unsure
    python3 fit_path_loss.py field.csv --columns

Only the standard library is used, so nothing needs installing.
"""
import argparse
import csv
import math
import sys

RSSI_NAMES = ["rssi", "rssi_dbm", "rssi(dbm)", "signal", "rx_rssi", "snr_rssi"]
LAT_NAMES = ["latitude", "lat", "gps_lat", "device_lat"]
LON_NAMES = ["longitude", "lon", "lng", "long", "gps_lon", "device_lon"]


def pick_column(header, candidates, override=None, what=""):
    if override:
        if override not in header:
            sys.exit(f"Column {override!r} is not in the file. Columns: {header}")
        return override
    lowered = {h.strip().lower(): h for h in header}
    for c in candidates:
        if c in lowered:
            return lowered[c]
    sys.exit(
        f"Could not find a {what} column automatically. Columns in the file: "
        f"{header}. Pass it explicitly, e.g. --{what}-col <name>."
    )


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def linear_fit(xs, ys):
    """Least squares y = a + b*x. Returns (a, b, r_squared)."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        sys.exit(
            "Every retained point is at the same distance, so there is no slope "
            "to fit. This usually means the surviving rows all come from one "
            "spot: check the warnings above, and check that the right rows "
            "survived --min-distance."
        )
    b = sxy / sxx
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return a, b, r2


SF_NAMES = ["spreading factor", "spreading_factor", "sf", "datarate", "data_rate"]
GATEWAY_NAMES = ["gateway_id", "gateway", "gw_id", "gweui", "gateway_eui"]


def _distinct(rows, header, candidates):
    """Distinct non-empty values of the first matching column, or None if the
    file has no such column."""
    lowered = {h.strip().lower(): h for h in header}
    for c in candidates:
        if c in lowered:
            col = lowered[c]
            vals = {str(r[col]).strip() for r in rows if r.get(col) not in (None, "")}
            return col, vals
    return None, None


def sanity_checks(rows, header, pts):
    """Flags the mistakes that produce a healthy-looking but wrong fit. These
    are warnings, not errors: only you know which subset of the file you meant."""
    warned = False

    col, vals = _distinct(rows, header, SF_NAMES)
    if col and vals and len(vals) > 1:
        warned = True
        print(f"\n  WARNING: column {col!r} holds {len(vals)} distinct values "
              f"({', '.join(sorted(vals)[:6])}{'...' if len(vals) > 6 else ''}).")
        print("           Different spreading factors have different receiver")
        print("           sensitivity and are not directly comparable in one fit.")
        print("           Filter to a single spreading factor first.")

    col, vals = _distinct(rows, header, GATEWAY_NAMES)
    if col and vals and len(vals) > 1:
        warned = True
        print(f"\n  WARNING: column {col!r} holds {len(vals)} distinct values, so "
              f"the file mixes several gateways.")
        print("           Each gateway has its own position, antenna and height.")
        print("           Filter to the one you are modelling.")

    ds = sorted(d for d, _ in pts)
    med = ds[len(ds) // 2]
    print(f"\n  Distance to gateway: median {med:.0f} m, "
          f"p95 {ds[int(0.95 * (len(ds) - 1))]:.0f} m, max {ds[-1]:.0f} m")
    if ds[-1] > 50000:
        warned = True
        print(f"\n  WARNING: the farthest point is {ds[-1] / 1000:.0f} km away, which "
              f"is far beyond any")
        print("           LoRa link. Those rows are almost certainly from a different")
        print("           site, such as bench testing before deployment, or the")
        print("           gateway coordinates passed in are wrong.")
    far_count = sum(1 for d in ds if d > 30)
    if far_count < 0.05 * len(ds):
        warned = True
        print(f"\n  WARNING: only {far_count} of {len(ds)} points lie beyond 30 m. A fit")
        print("           resting on so few far points is weak however good its R^2")
        print("           looks, and the model will be extrapolated across most of")
        print("           the range you then simulate.")

    if not warned:
        print("  Sanity checks passed.")


def main():
    ap = argparse.ArgumentParser(description="Fit a log-distance path-loss model")
    ap.add_argument("csv_file")
    ap.add_argument("--lat", type=float, help="gateway latitude")
    ap.add_argument("--lon", type=float, help="gateway longitude")
    ap.add_argument("--tx-power", type=float, default=None,
                    help="node transmit power [dBm]; with --net-gain, converts "
                         "the RSSI fit into a path-loss model")
    ap.add_argument("--net-gain", type=float, default=0.0,
                    help="Gtx + Grx - cable losses [dB]")
    ap.add_argument("--d0", type=float, default=100.0,
                    help="reference distance for the reported model [m] (default 100)")
    ap.add_argument("--min-distance", type=float, default=30.0,
                    help="exclude points closer than this [m] (default 30)")
    ap.add_argument("--max-distance", type=float, default=None,
                    help="exclude points beyond this [m]")
    ap.add_argument("--bin-width", type=float, default=10.0,
                    help="distance bin width for averaging [m] (default 10)")
    ap.add_argument("--rssi-col"), ap.add_argument("--latitude-col")
    ap.add_argument("--longitude-col")
    ap.add_argument("--columns", action="store_true",
                    help="list the file's columns and exit")
    args = ap.parse_args()

    with open(args.csv_file, newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = list(reader)

    if args.columns:
        print(f"Columns in {args.csv_file}:")
        for h in header:
            print(f"  {h}")
        print(f"\n{len(rows)} data rows")
        return

    if args.lat is None or args.lon is None:
        sys.exit("--lat and --lon (the gateway position) are required.")

    rssi_col = pick_column(header, RSSI_NAMES, args.rssi_col, "rssi")
    lat_col = pick_column(header, LAT_NAMES, args.latitude_col, "latitude")
    lon_col = pick_column(header, LON_NAMES, args.longitude_col, "longitude")
    print(f"Using columns: rssi={rssi_col!r}, lat={lat_col!r}, lon={lon_col!r}")

    pts, skipped = [], 0
    for r in rows:
        try:
            rssi = float(r[rssi_col])
            lat = float(r[lat_col])
            lon = float(r[lon_col])
        except (TypeError, ValueError):
            skipped += 1
            continue
        d = haversine_m(args.lat, args.lon, lat, lon)
        pts.append((d, rssi))

    print(f"Read {len(pts)} usable rows ({skipped} skipped for unparseable values)")
    if not pts:
        sys.exit("No usable rows.")

    sanity_checks(rows, header, pts)

    kept = [(d, r) for d, r in pts if d >= args.min_distance
            and (args.max_distance is None or d <= args.max_distance)]
    print(f"Kept {len(kept)} rows between {args.min_distance:.0f} m and "
          f"{args.max_distance if args.max_distance else max(d for d, _ in pts):.0f} m")
    if len(kept) < 10:
        sys.exit("Too few points after filtering to fit anything meaningful.")

    # bin by distance and average
    bins = {}
    for d, rssi in kept:
        k = int(d // args.bin_width)
        bins.setdefault(k, []).append((d, rssi))
    binned = []
    for k in sorted(bins):
        ds = [d for d, _ in bins[k]]
        rs = [r for _, r in bins[k]]
        binned.append((sum(ds) / len(ds), sum(rs) / len(rs), len(rs)))

    far = max(d for d, _ in kept)

    def do_fit(points):
        xs = [math.log10(d) for d, _ in points]
        ys = [r for _, r in points]
        a, b, r2 = linear_fit(xs, ys)
        return a, b, r2, -b / 10.0      # RSSI(d) = a + b*log10(d), b negative

    fits = {
        "unbinned": (do_fit(kept), len(kept),
                     "every retained measurement; the usual choice in the "
                     "literature, but weighted by sampling density"),
        f"binned ({args.bin_width:.0f} m)": (
            do_fit([(d, r) for d, r, _ in binned]), len(binned),
            "distance bands averaged first; robust to uneven sampling"),
    }

    for label, ((a, b, r2, n_exp), npts, why) in fits.items():
        print(f"\n--- {label} fit ".ljust(63, "-"))
        print(f"  {why}")
        print(f"  RSSI(d) = {b:.2f} * log10(d) + {a:.2f}   dBm, d in metres")
        print(f"  path-loss exponent n = {n_exp:.3f}")
        print(f"  R^2 = {r2:.3f}   over {npts} points")
        if r2 < 0.5:
            print("  NOTE: a low R^2 is common in vegetated terrain, but it does")
            print("        mean the mean trend explains little of the spread.")
            print("        Say so when you report the model.")

        if args.tx_power is None:
            continue
        rssi_d0 = a + b * math.log10(args.d0)
        l_d0 = args.tx_power + args.net_gain - rssi_d0
        l_far = l_d0 + 10 * n_exp * math.log10(far / args.d0)
        print("\n  paste into study.py:")
        print(f"""
    path_loss_exponent={n_exp:.3f},
    path_loss_ref_db={l_d0:.2f},
    path_loss_ref_distance_m={args.d0:.1f},
    min_valid_distance_m={args.min_distance:.1f},
    path_loss_r_squared={r2:.3f},
    path_loss_source="Field fit ({label}), {npts} points, "
                     "{args.min_distance:.0f} m to {far:.0f} m",
""")
        print(f"  Sanity check: this model predicts L({far:.0f} m) = {l_far:.1f} dB, "
              f"RSSI {args.tx_power + args.net_gain - l_far:.1f} dBm.")
        print("  Compare that against the weakest link you actually observed. A")
        print("  large disagreement means the model is being extrapolated, or the")
        print("  link budget passed in here does not match the deployed hardware.")

    if args.tx_power is None:
        print("\n  (run again with --tx-power and --net-gain to get the path-loss")
        print("   block to paste; without them only the RSSI fits can be computed)")

    print(f"\n--- binned points ({args.bin_width:.0f} m bins) ----------------")
    print("     distance_m  mean_rssi_dbm  n_samples")
    for d, r, n in binned[:40]:
        print(f"  {d:11.1f}  {r:13.1f}  {n:9d}")
    if len(binned) > 40:
        print(f"  ... {len(binned) - 40} more bins")


if __name__ == "__main__":
    main()
