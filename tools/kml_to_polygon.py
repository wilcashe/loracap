#!/usr/bin/env python3
"""
kml_to_polygon.py
=================

Converts the polygons of a KML file, as exported from Google Earth, into the
site_polygon.py module a study imports.

Usage
-----
    python3 tools/kml_to_polygon.py FARM.kml --lat <gw_lat> --lon <gw_lon>

    --list            show the polygons in the file and exit
    --include TEXT    keep only polygons whose name contains TEXT (repeatable)
    -o PATH           output file (default: site_polygon.py)
    --name TEXT       site name for the generated docstring

Check the three validations it prints before trusting the output: the total
area, whether the gateway falls inside the boundary, and whether any polygons
overlap. An overlap inflates the area and concentrates nodes in the repeated
region, and neither failure announces itself later.

For a KMZ, unzip it first: the KML is inside.

The logic lives in loracap/geo.py, so the web interface and this script agree
by construction.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loracap import geo


def main():
    ap = argparse.ArgumentParser(description="Convert KML polygons to site_polygon.py")
    ap.add_argument("kml")
    ap.add_argument("--lat", type=float, help="gateway latitude")
    ap.add_argument("--lon", type=float, help="gateway longitude")
    ap.add_argument("-o", "--output", default="site_polygon.py")
    ap.add_argument("--name", default="the deployment site")
    ap.add_argument("--include", action="append", default=[])
    ap.add_argument("--list", action="store_true", help="list polygons and exit")
    args = ap.parse_args()

    try:
        placemarks = geo.parse_kml(args.kml)
    except Exception as e:
        sys.exit(f"Could not read {args.kml}: {e}")
    if not placemarks:
        sys.exit("No polygons found in that KML. If it is a KMZ, unzip it first.")

    if args.list:
        print(f"Polygons in {args.kml}:")
        for name, pts in placemarks:
            print(f"  {name!r}: {len(pts)} vertices")
        return

    if args.lat is None or args.lon is None:
        sys.exit("--lat and --lon (the gateway position) are required. "
                 "Use --list to inspect the file first.")

    if args.include:
        kept = [(n, p) for n, p in placemarks
                if any(inc.lower() in n.lower() for inc in args.include)]
        if not kept:
            sys.exit(f"No polygon name matched {args.include}. Use --list to see them.")
        placemarks = kept

    rings = geo.project_rings(placemarks, args.lat, args.lon)
    info = geo.inspect(rings)

    print(f"\nConverted {len(rings)} polygon(s), gateway at ({args.lat}, {args.lon})\n")
    for p in info["polygons"]:
        print(f"  {p['name']:<20} {p['area_ha']:8.2f} ha   {p['vertices']:3d} vertices")
    print(f"  {'TOTAL':<20} {info['total_area_ha']:8.2f} ha")

    print(f"\n  Gateway inside the boundary: "
          f"{'yes' if info['gateway_inside'] else 'NO'}")
    if not info["gateway_inside"]:
        print("  WARNING: the gateway falls outside every polygon. Check the")
        print("           coordinates, or confirm this is intentional.")

    if info["overlaps"]:
        print("\n  WARNING: polygons appear to overlap. The total above double-counts")
        print("           the overlap, and node placement would be biased toward it.")
        for o in info["overlaps"]:
            print(f"           {o['a']} and {o['b']}: about {o['area_ha']:.2f} ha")
    else:
        print("  Polygons overlap: none detected")
    print(f"  Farthest vertex from gateway: {info['max_radius_m']:.0f} m")

    text = geo.render_site_polygon(
        rings, args.lat, args.lon, args.name,
        source_note=f"Converted from {os.path.basename(args.kml)}.")
    with open(args.output, "w") as f:
        f.write(text)
    print(f"\nWrote {args.output}\n")


if __name__ == "__main__":
    main()
