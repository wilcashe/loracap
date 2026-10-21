#!/usr/bin/env python3
"""
kml_to_polygon.py
=================

Converts the polygons of a KML file (as exported from Google Earth) into the
`farm_polygon.py` module consumed by the simulation package.

Coordinates are projected onto a local east/north plane in metres, centred on
the gateway, using an equirectangular approximation. Over distances of a few
kilometres at low latitude the error is well below a metre, which is far finer
than the boundary itself is drawn.

Only standard-library modules are used, so nothing needs installing.

Usage
-----
    python3 kml_to_polygon.py FARM.kml --lat <gateway_lat> --lon <gateway_lon>

Options
-------
    -o, --output      Output file (default: farm_polygon.py)
    --name            Site name written into the generated docstring
    --include         Only convert polygons whose placemark name contains this
                      text (repeatable). By default every polygon is converted.
    --list            List the polygons found and exit, converting nothing.

Before trusting the output, check the three validations it prints: the total
area, whether the gateway falls inside the boundary, and whether any polygons
overlap (overlapping polygons would be double-counted by the area figure and
would bias node placement toward the overlap).

For a KMZ file, unzip it first; the KML is inside.
"""
import argparse
import math
import sys
import xml.etree.ElementTree as ET

KML_NS = "{http://www.opengis.net/kml/2.2}"
NS = {"k": "http://www.opengis.net/kml/2.2"}


def parse_placemarks(kml_path):
    """Returns [(name, [(lon, lat), ...]), ...] for every Polygon found."""
    tree = ET.parse(kml_path)
    out = []
    for pm in tree.getroot().iter(KML_NS + "Placemark"):
        name_el = pm.find("k:name", NS)
        name = name_el.text.strip() if name_el is not None and name_el.text else "(unnamed)"
        for poly in pm.iter(KML_NS + "Polygon"):
            coord_el = poly.find(".//k:coordinates", NS)
            if coord_el is None or not coord_el.text:
                continue
            pts = []
            for token in coord_el.text.split():
                parts = token.split(",")
                if len(parts) < 2:
                    continue
                pts.append((float(parts[0]), float(parts[1])))
            if len(pts) >= 3:
                # KML closes rings by repeating the first vertex; drop the repeat
                if pts[0] == pts[-1]:
                    pts = pts[:-1]
                out.append((name, pts))
    return out


def to_local_metres(lon, lat, gw_lon, gw_lat):
    """Equirectangular projection centred on the gateway. x = east, y = north."""
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(gw_lat))
    return ((lon - gw_lon) * m_per_deg_lon, (lat - gw_lat) * m_per_deg_lat)


def shoelace_area_m2(ring):
    s = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def rings_overlap(a, b, samples=4000):
    """Monte Carlo overlap check. Not exact, but enough to catch a real overlap:
    if any sampled point of one ring's bounding box falls inside both, they
    intersect. Returns an approximate overlap area in m^2."""
    xs = [p[0] for p in a] + [p[0] for p in b]
    ys = [p[1] for p in a] + [p[1] for p in b]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    box = (maxx - minx) * (maxy - miny)
    if box <= 0:
        return 0.0
    hits = 0
    # deterministic lattice sampling, so repeated runs agree
    side = int(math.sqrt(samples))
    for i in range(side):
        for j in range(side):
            x = minx + (i + 0.5) * (maxx - minx) / side
            y = miny + (j + 0.5) * (maxy - miny) / side
            if point_in_ring(x, y, a) and point_in_ring(x, y, b):
                hits += 1
    return box * hits / (side * side)


def main():
    ap = argparse.ArgumentParser(description="Convert KML polygons to farm_polygon.py")
    ap.add_argument("kml")
    ap.add_argument("--lat", type=float, help="gateway latitude")
    ap.add_argument("--lon", type=float, help="gateway longitude")
    ap.add_argument("-o", "--output", default="farm_polygon.py")
    ap.add_argument("--name", default="the deployment site")
    ap.add_argument("--include", action="append", default=[])
    ap.add_argument("--list", action="store_true", help="list polygons and exit")
    args = ap.parse_args()

    placemarks = parse_placemarks(args.kml)
    if not placemarks:
        sys.exit("No polygons found in that KML. Check the file, or unzip it if it is a KMZ.")

    if args.list:
        print(f"Polygons found in {args.kml}:")
        for name, pts in placemarks:
            print(f"  {name!r}: {len(pts)} vertices")
        return

    if args.lat is None or args.lon is None:
        sys.exit("--lat and --lon (the gateway position) are required. Use --list to inspect first.")

    if args.include:
        kept = [(n, p) for n, p in placemarks
                if any(inc.lower() in n.lower() for inc in args.include)]
        if not kept:
            sys.exit(f"No polygon name matched {args.include}. Use --list to see the names.")
        placemarks = kept

    rings = []
    for name, pts in placemarks:
        ring = [to_local_metres(lon, lat, args.lon, args.lat) for lon, lat in pts]
        rings.append((name, ring))

    # ---- validations -----------------------------------------------------
    print(f"\nConverted {len(rings)} polygon(s), gateway at ({args.lat}, {args.lon})\n")
    total = 0.0
    for name, ring in rings:
        a = shoelace_area_m2(ring)
        total += a
        print(f"  {name:<20} {a/10000:8.2f} ha   {len(ring):3d} vertices")
    print(f"  {'TOTAL':<20} {total/10000:8.2f} ha")

    gw_inside = any(point_in_ring(0.0, 0.0, r) for _, r in rings)
    print(f"\n  Gateway inside the boundary: {'yes' if gw_inside else 'NO'}")
    if not gw_inside:
        print("  WARNING: the gateway falls outside every polygon. Check the coordinates,")
        print("           or confirm this is intentional for your deployment.")

    overlaps = []
    for i in range(len(rings)):
        for j in range(i + 1, len(rings)):
            ov = rings_overlap(rings[i][1], rings[j][1])
            if ov / 10000 > 0.01:
                overlaps.append((rings[i][0], rings[j][0], ov / 10000))
    if overlaps:
        print("\n  WARNING: polygons appear to overlap. The total area above double-counts")
        print("           the overlap, and node placement would be biased toward it.")
        for a, b, ha in overlaps:
            print(f"           {a} and {b}: about {ha:.2f} ha")
    else:
        print("  Polygons overlap: none detected")

    dmax = max(math.hypot(x, y) for _, r in rings for (x, y) in r)
    print(f"  Farthest vertex from gateway: {dmax:.0f} m")

    # ---- write the module ------------------------------------------------
    with open(args.output, "w") as f:
        f.write('"""\n')
        f.write("farm_polygon.py\n===============\n\n")
        f.write(f"Boundary of {args.name}, digitised in Google Earth and converted\n")
        f.write(f"from {args.kml} by kml_to_polygon.py. Do not edit by hand.\n\n")
        f.write(f"{len(rings)} polygon(s), {total/10000:.2f} ha in total, farthest vertex\n")
        f.write(f"{dmax:.0f} m from the gateway.\n\n")
        f.write("Coordinates are in METRES on a local east/north plane centred on the\n")
        f.write(f"gateway ({args.lat}, {args.lon}), via an equirectangular approximation.\n")
        f.write("x = east, y = north.\n")
        f.write('"""\n\n')
        f.write(f"GATEWAY_LAT = {args.lat}\nGATEWAY_LON = {args.lon}\n\n")
        f.write("# list of polygons; each is a list of (x_east_m, y_north_m) vertices\n")
        f.write("FARM_POLYGONS_M = [\n")
        for name, ring in rings:
            f.write(f"    # {name}\n    [\n")
            for (x, y) in ring:
                f.write(f"        ({x:.2f}, {y:.2f}),\n")
            f.write("    ],\n")
        f.write("]\n")

    print(f"\nWrote {args.output}\n")


if __name__ == "__main__":
    main()
