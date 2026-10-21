#!/usr/bin/env python3
"""
Study definition.

This is the ONLY file you need to edit for a new site. Fields marked TODO have
no sensible default and must be filled from your own hardware and measurements.
Everything else has a default that is either standard or harmless.

Two tools in tools/ produce the inputs that are tedious by hand:

    tools/kml_to_polygon.py   site boundary  ->  site_polygon.py
    tools/fit_path_loss.py    field RSSI     ->  the propagation block below

When you are done:  python3 run.py check <name>
"""
from loracap import Study, node_counts_logspace

# Uncomment once you have generated site_polygon.py with tools/kml_to_polygon.py
# from site_polygon import FARM_POLYGONS_M, GATEWAY_LAT, GATEWAY_LON

STUDY = Study(
    # ------------------------------------------------------------------ #
    # Identification. Free text, used in reports and file names.
    # ------------------------------------------------------------------ #
    name="_template",
    site="TODO: where this deployment is",
    description="TODO: one sentence on what this study answers",

    # ------------------------------------------------------------------ #
    # Band and spreading factors
    #
    # `region` is checked against the spreading factors you simulate, which
    # catches the most common configuration error in this kind of study:
    # simulating data rates the band does not offer on uplink. Leave
    # `spreading_factors` empty to take the region's full 125 kHz uplink range.
    # ------------------------------------------------------------------ #
    region="US915",
    bw_khz=125,
    spreading_factors=(),

    # ------------------------------------------------------------------ #
    # Gateway
    #
    # Naming a `chip` fills sensitivity, channel count and demodulation limit
    # from loracap/presets.py, where every value carries its datasheet
    # reference. Only chips actually verified against a datasheet are listed
    # there. For anything else, leave `chip=None` and fill the three fields
    # below from your own datasheet. There is no default sensitivity, because
    # a guessed one would silently change every result.
    # ------------------------------------------------------------------ #
    chip="SX1301",
    # sensitivity_dbm={7: -126.5, 8: -129.0, 9: -131.5, 10: -134.0},
    # n_channels=8,
    # max_simultaneous_demodulations=8,
    n_gateways=1,

    # ------------------------------------------------------------------ #
    # Link budget. TODO: from your node, antennas and installation.
    # ------------------------------------------------------------------ #
    tx_power_dbm=14.0,
    tx_antenna_gain_db=0.0,
    rx_antenna_gain_db=0.0,
    cable_loss_db=0.0,

    # ------------------------------------------------------------------ #
    # Propagation model:  L(d) = path_loss_ref_db + 10*n*log10(d / d0)
    #
    # TODO, and this is the field you cannot borrow from another site. Path
    # loss depends on terrain, vegetation and antenna height, so a model fitted
    # elsewhere does not transfer. Run tools/fit_path_loss.py on your own
    # RSSI-versus-distance measurements and paste the block it prints.
    #
    # Keep d0 INSIDE the range your data covers. Quoting the same line at
    # d0 = 1 m is algebraically identical but gives a reference value far below
    # free-space loss, which is an extrapolation no reviewer should accept.
    #
    # `min_valid_distance_m` is the lower bound of the fit. Closer distances are
    # clamped rather than extrapolated.
    # ------------------------------------------------------------------ #
    path_loss_exponent=2.0,
    path_loss_ref_db=0.0,
    path_loss_ref_distance_m=100.0,
    min_valid_distance_m=30.0,
    path_loss_r_squared=None,
    path_loss_source="TODO: where this model came from",

    # ------------------------------------------------------------------ #
    # Traffic
    #
    # Use the worst case the deployment can produce, not the nominal setting.
    # Capacity scales with channel occupancy, so a figure obtained at the
    # shortest interval is a lower bound you can defend.
    # ------------------------------------------------------------------ #
    payload_bytes=32,
    coding_rate=1,              # CR index; airtime uses 4/(4+CR), so 1 is 4/5
    send_interval_s=60.0,
    capture_threshold_db=6.0,

    # ------------------------------------------------------------------ #
    # Node placement
    #
    # "polygon" spreads nodes over the real site boundary and answers "what
    # does THIS deployment support?". "disc" uses the theoretical coverage
    # circle implied by the link budget, the classic assumption in the LoRa
    # scalability literature, and answers "what can this gateway support in the
    # abstract?".
    #
    # Reporting the polygon result as the headline and the disc result as a
    # sensitivity check is the strongest arrangement: it answers the question
    # that matters and simultaneously shows how much the spatial assumption
    # changed the answer.
    # ------------------------------------------------------------------ #
    placement="polygon",
    # polygons_m=FARM_POLYGONS_M,
    # gateway_lat=GATEWAY_LAT,
    # gateway_lon=GATEWAY_LON,

    # ------------------------------------------------------------------ #
    # Experiment design
    #
    # Name scenarios "SF<n>" for a fixed spreading factor, or "MULTI" for
    # adaptive selection by distance. Include the configuration you actually
    # deploy, plus bounds either side of it. Remember which direction is which:
    # a LOWER SF has shorter time-on-air and therefore HIGHER capacity, so the
    # low SF is the optimistic bound and the high SF the conservative one.
    #
    # If a scenario's curve never crosses the threshold, widen node_counts.
    # ------------------------------------------------------------------ #
    scenarios=("SF7", "SF10", "MULTI"),
    adaptive_sf_options=None,
    node_counts=node_counts_logspace(3, 300),
    sim_time_s=3600.0,
    n_runs=30,
    base_seed=99,
    der_threshold=0.9,

    # ------------------------------------------------------------------ #
    # Figure. Everything else about the plot is automatic.
    # ------------------------------------------------------------------ #
    highlight_scenario=None,     # the deployed configuration, drawn in colour
    figure_basename="capacity",
)
