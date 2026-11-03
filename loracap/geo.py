#!/usr/bin/env python3
"""
loracap.geo
===========

Turning a site boundary into the metric polygons the engine places nodes in.

A KML exported from Google Earth gives latitude and longitude. The engine works
in metres on a plane centred on the gateway, so this module projects, measures,
and checks the three things that silently ruin a study: that the gateway really
sits inside the boundary, that the polygons do not overlap, and that the area
is what the user believes it is.

Only the standard library is used, so there is no geometry dependency to
install.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from typing import List, Sequence, Tuple

KML_NS = "{http://www.opengis.net/kml/2.2}"
_NS = {"k": "http://www.opengis.net/kml/2.2"}

Ring = Sequence[Tuple[float, float]]


# ---------------------------------------------------------------------------
# KML
# ---------------------------------------------------------------------------

def parse_kml(source: str, is_text: bool = False):
    """Returns [(placemark_name, [(lon, lat), ...]), ...] for every Polygon.

    `source` is a file path, or the KML document itself when is_text is True.
    """
    root = ET.fromstring(source) if is_text else ET.parse(source).getroot()
    out = []
    for pm in root.iter(KML_NS + "Placemark"):
        name_el = pm.find("k:name", _NS)
        name = name_el.text.strip() if name_el is not None and name_el.text else "(unnamed)"
        for poly in pm.iter(KML_NS + "Polygon"):
            coord_el = poly.find(".//k:coordinates", _NS)
            if coord_el is None or not coord_el.text:
                continue
            pts = []
            for token in coord_el.text.split():
                parts = token.split(",")
                if len(parts) < 2:
                    continue
                try:
                    pts.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    continue
            if len(pts) >= 3:
                if pts[0] == pts[-1]:        # KML repeats the first vertex
                    pts = pts[:-1]
                out.append((name, pts))
    return out


def to_local_metres(lon: float, lat: float, gw_lon: float, gw_lat: float):
    """Equirectangular projection centred on the gateway. x east, y north.

    Sub-metre error over the few kilometres a single gateway covers, which is
    far finer than a boundary traced over satellite imagery.
    """
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(gw_lat))
    return ((lon - gw_lon) * m_per_deg_lon, (lat - gw_lat) * m_per_deg_lat)


def project_rings(placemarks, gw_lat: float, gw_lon: float):
    """[(name, ring_in_metres), ...] from parse_kml output."""
    return [
        (name, [to_local_metres(lon, lat, gw_lon, gw_lat) for lon, lat in pts])
        for name, pts in placemarks
    ]


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

def shoelace_area_m2(ring: Ring) -> float:
    s = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def point_in_ring(x: float, y: float, ring: Ring) -> bool:
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


def approx_overlap_m2(a: Ring, b: Ring, samples: int = 4000) -> float:
    """Approximate overlap area between two rings, by lattice sampling.

    Not exact, and not meant to be. Its job is to catch polygons that genuinely
    overlap, because an overlap inflates the total area and concentrates nodes
    in the repeated region, and neither failure announces itself later.
    Sampling is deterministic so repeated runs agree.
    """
    xs = [p[0] for p in a] + [p[0] for p in b]
    ys = [p[1] for p in a] + [p[1] for p in b]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    box = (maxx - minx) * (maxy - miny)
    if box <= 0:
        return 0.0
    side = max(2, int(math.sqrt(samples)))
    hits = 0
    for i in range(side):
        x = minx + (i + 0.5) * (maxx - minx) / side
        for j in range(side):
            y = miny + (j + 0.5) * (maxy - miny) / side
            if point_in_ring(x, y, a) and point_in_ring(x, y, b):
                hits += 1
    return box * hits / (side * side)


def inspect(rings) -> dict:
    """Everything worth checking about a converted boundary, in one call.

    `rings` is [(name, ring_in_metres), ...] with the gateway at the origin.
    """
    per_polygon = [
        {"name": name, "area_ha": shoelace_area_m2(r) / 10000.0, "vertices": len(r)}
        for name, r in rings
    ]
    overlaps = []
    for i in range(len(rings)):
        for j in range(i + 1, len(rings)):
            ov = approx_overlap_m2(rings[i][1], rings[j][1]) / 10000.0
            if ov > 0.01:
                overlaps.append({"a": rings[i][0], "b": rings[j][0], "area_ha": ov})
    all_pts = [p for _, r in rings for p in r]
    return {
        "polygons": per_polygon,
        "total_area_ha": sum(p["area_ha"] for p in per_polygon),
        "gateway_inside": any(point_in_ring(0.0, 0.0, r) for _, r in rings),
        "overlaps": overlaps,
        "max_radius_m": max(math.hypot(x, y) for x, y in all_pts) if all_pts else 0.0,
        "bounds_m": {
            "min_x": min(p[0] for p in all_pts), "max_x": max(p[0] for p in all_pts),
            "min_y": min(p[1] for p in all_pts), "max_y": max(p[1] for p in all_pts),
        } if all_pts else None,
    }


# ---------------------------------------------------------------------------
# Emitting site_polygon.py
# ---------------------------------------------------------------------------

def render_site_polygon(rings, gw_lat: float, gw_lon: float,
                        site_name: str = "the deployment site",
                        source_note: str = "") -> str:
    """The text of a site_polygon.py module for a study directory."""
    info = inspect(rings)
    lines = [
        '"""',
        "site_polygon.py",
        "===============",
        "",
        f"Boundary of {site_name}.",
    ]
    if source_note:
        lines.append(source_note)
    lines += [
        "",
        f"{len(rings)} polygon(s), {info['total_area_ha']:.2f} ha in total, farthest",
        f"vertex {info['max_radius_m']:.0f} m from the gateway.",
        "",
        "Coordinates are in METRES on a local east/north plane centred on the",
        f"gateway ({gw_lat}, {gw_lon}), via an equirectangular approximation.",
        "x = east, y = north. Generated by loracap, do not edit by hand.",
        '"""',
        "",
        f"GATEWAY_LAT = {gw_lat}",
        f"GATEWAY_LON = {gw_lon}",
        "",
        "# list of polygons; each is a list of (x_east_m, y_north_m) vertices",
        "FARM_POLYGONS_M = [",
    ]
    for name, ring in rings:
        lines.append(f"    # {name}")
        lines.append("    [")
        for x, y in ring:
            lines.append(f"        ({x:.2f}, {y:.2f}),")
        lines.append("    ],")
    lines.append("]")
    return "\n".join(lines) + "\n"
