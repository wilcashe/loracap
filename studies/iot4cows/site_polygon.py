"""
site_polygon.py
===============

Grazing-area boundary of the IoT4Cows deployment site (Guamal, Meta, Colombia),
digitised in Google Earth by the authors over satellite imagery.

Three disjoint polygons (grazing paddocks plus the farmstead) totalling 88.54 ha.
Note this is the instrumented grazing area, not the full 150 ha cadastral property
(which also includes the Guamal riverbed and wooded land).

Coordinates are in METRES in a local east/north plane centred on the gateway
(3.91915 N, -73.82184 W), converted with a local equirectangular approximation
(valid over these distances, sub-metre error). x = east, y = north.

Generated from Farm_IoT4Cows.kml by tools/kml_to_polygon.py; do not edit by hand.
"""

GATEWAY_LAT = 3.91915
GATEWAY_LON = -73.82184

# list of polygons; each polygon is a list of (x_east_m, y_north_m) vertices
FARM_POLYGONS_M = [
    # Farm
    [
        (-664.66, -556.25),
        (-486.23, -694.36),
        (-318.2, -852.13),
        (-123.98, -820.43),
        (132.61, -732.02),
        (262.61, -762.69),
        (392.55, -316.52),
        (530.31, 41.94),
        (431.21, 53.0),
        (305.87, 27.82),
        (168.14, 100.44),
        (-52.8, 65.96),
        (-78.29, 54.33),
        (-122.58, -0.65),
        (-157.89, -41.82),
        (-250.47, -83.71),
        (-292.05, -141.99),
        (-353.45, -223.49),
        (-433.35, -287.27),
        (-529.19, -374.8),
        (-689.74, -438.82),
        (-844.04, -452.16),
    ],
    # Farm_part2
    [
        (161.31, 107.94),
        (-104.69, 271.62),
        (-273.54, 183.79),
        (-293.41, 160.79),
        (-410.06, 114.13),
        (-372.92, 56.19),
        (-655.78, -213.51),
        (-472.95, -288.79),
        (-453.58, -284.45),
        (-411.62, -256.35),
        (-368.6, -221.91),
        (-312.86, -147.52),
        (-264.86, -81.91),
        (-182.35, -40.11),
        (-155.56, -24.03),
        (-94.85, 46.62),
        (-78.77, 69.1),
        (-33.59, 82.01),
    ],
    # Farm_part3
    [
        (-662.7, -223.87),
        (-768.65, -287.13),
        (-546.16, -367.19),
        (-477.49, -296.07),
    ],
]
