#!/usr/bin/env python3
"""
fit_path_loss.py
================

Fits a log-distance path-loss model to field measurements and prints the block
you paste into your study.

    L(d) = L(d0) + 10 * n * log10(d / d0)

Input
-----
A CSV, one row per received message, with columns for RSSI, latitude and
longitude:

    rssi,latitude,longitude
    -83,3.917401,-73.820015
    -91,3.918220,-73.821540

RSSI in dBm as the gateway reports it, coordinates in decimal degrees. Other
columns are ignored, so an unmodified gateway or network-server export usually
works as is. Column names are auto-detected and can be overridden. Run with
--columns to see what your file contains.

Filter first
------------
The file should hold only messages from the deployment you are modelling, at
ONE spreading factor and ONE gateway. Mixing in bench tests from elsewhere,
several spreading factors or several gateways produces a fit that looks
perfectly healthy and is wrong. This script warns about all three, but it
cannot know which subset you meant to keep.

Two fits are reported, with and without distance binning, because the choice
changes the answer and is yours. On one real dataset the exponent moved from
2.07 binned to 2.17 unbinned.

Usage
-----
    python3 tools/fit_path_loss.py field.csv --lat <lat> --lon <lon> \\
        --tx-power 22 --net-gain 9

The logic lives in loracap/pathloss.py, so the web interface and this script
agree by construction.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loracap import pathloss


def main():
    ap = argparse.ArgumentParser(description="Fit a log-distance path-loss model")
    ap.add_argument("csv_file")
    ap.add_argument("--lat", type=float, help="gateway latitude")
    ap.add_argument("--lon", type=float, help="gateway longitude")
    ap.add_argument("--tx-power", type=float, default=None,
                    help="node transmit power [dBm]; with --net-gain, turns the "
                         "RSSI fit into a path-loss model")
    ap.add_argument("--net-gain", type=float, default=0.0,
                    help="Gtx + Grx - cable losses [dB]")
    ap.add_argument("--d0", type=float, default=100.0,
                    help="reference distance for the reported model [m]")
    ap.add_argument("--min-distance", type=float, default=30.0,
                    help="exclude points closer than this [m]")
    ap.add_argument("--max-distance", type=float, default=None)
    ap.add_argument("--bin-width", type=float, default=10.0)
    ap.add_argument("--rssi-col"), ap.add_argument("--latitude-col")
    ap.add_argument("--longitude-col")
    ap.add_argument("--columns", action="store_true",
                    help="list the file's columns and exit")
    args = ap.parse_args()

    try:
        header, rows = pathloss.read_csv(args.csv_file)
    except OSError as e:
        sys.exit(f"Could not read {args.csv_file}: {e}")

    if args.columns:
        print(f"Columns in {args.csv_file}:")
        for h in header:
            print(f"  {h}")
        print(f"\n{len(rows)} data rows")
        return

    if args.lat is None or args.lon is None:
        sys.exit("--lat and --lon (the gateway position) are required.")

    try:
        res = pathloss.analyse(
            header, rows, args.lat, args.lon,
            tx_power_dbm=args.tx_power, net_gain_db=args.net_gain,
            d0_m=args.d0, min_distance_m=args.min_distance,
            max_distance_m=args.max_distance, bin_width_m=args.bin_width,
            rssi_col=args.rssi_col, lat_col=args.latitude_col,
            lon_col=args.longitude_col)
    except ValueError as e:
        sys.exit(str(e))

    c = res["columns"]
    print(f"Using columns: rssi={c['rssi']!r}, lat={c['latitude']!r}, "
          f"lon={c['longitude']!r}")
    print(f"Read {res['n_usable']} usable rows "
          f"({res['n_skipped']} skipped for unparseable values)")

    if res["warnings"]:
        for w in res["warnings"]:
            print(f"\n  WARNING: {w['message']}")
    else:
        print("  Sanity checks passed.")

    print(f"\n  Distance to gateway: {res['distance_min_m']:.0f} m to "
          f"{res['distance_max_m']:.0f} m")
    print(f"  Kept {res['n_kept']} rows beyond {args.min_distance:.0f} m, "
          f"aggregated into {res['n_bins']} bins of {args.bin_width:.0f} m")

    for fit in res["fits"]:
        print(f"\n--- {fit['label']} fit ".ljust(63, "-"))
        print(f"  {fit['note']}")
        print(f"  RSSI(d) = {fit['slope']:.2f} * log10(d) + "
              f"{fit['intercept_dbm']:.2f}   dBm, d in metres")
        print(f"  path-loss exponent n = {fit['path_loss_exponent']:.3f}")
        print(f"  R^2 = {fit['r_squared']:.3f}   over {fit['n_points']} points")
        print(f"  residual sigma = {fit['shadowing_sigma_db']:.2f} dB   "
              f"(the log-normal shadowing term, not a goodness-of-fit number)")
        if fit["r_squared"] < 0.5:
            print("  NOTE: a low R^2 is common in vegetated terrain, but it does")
            print("        mean the mean trend explains little of the spread.")
            print("        Say so when you report the model.")
        if args.tx_power is None:
            continue
        print("\n  paste into study.py:\n")
        print(pathloss.study_snippet(fit))
        print(f"  Sanity check: predicts L({fit['max_distance_m']:.0f} m) = "
              f"{fit['predicted_loss_at_max_db']:.1f} dB, "
              f"RSSI {fit['predicted_rssi_at_max_dbm']:.1f} dBm.")
        print("  Compare against the weakest link you actually observed. A large")
        print("  disagreement means the model is being extrapolated, or the link")
        print("  budget here does not match the deployed hardware.")

    if args.tx_power is None:
        print("\n  (run again with --tx-power and --net-gain to get the path-loss")
        print("   block to paste; without them only the RSSI fits can be computed)")

    print(f"\n--- binned points ({args.bin_width:.0f} m bins) ----------------")
    print("     distance_m  mean_rssi_dbm  n_samples")
    for b in res["binned"][:40]:
        print(f"  {b['distance_m']:11.1f}  {b['rssi_dbm']:13.1f}  {b['n']:9d}")
    if len(res["binned"]) > 40:
        print(f"  ... {len(res['binned']) - 40} more bins")


if __name__ == "__main__":
    main()
