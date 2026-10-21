#!/usr/bin/env python3
"""
IoT4Cows: LoRaWAN cattle-monitoring deployment, Guamal, Meta, Colombia.

This is a worked example. It is the configuration behind the scalability
analysis published with the IoT4Cows paper, kept in the repository for two
reasons: it shows every field filled with a real, sourced value, and it lets
anyone confirm the engine still reproduces the published figures.

Expected result at DER = 0.9, with the parameters below:

    SF10   ~18 nodes     conservative bound (longest airtime of the US915
                         125 kHz uplink data rates, so the lowest capacity)
    SF8    ~62 nodes     the deployed configuration
    SF7   ~115 nodes     optimistic bound (shortest airtime)

Run `python3 run.py run iot4cows` and compare. A difference means the engine
changed, not the configuration.
"""
from loracap import Study

from site_polygon import FARM_POLYGONS_M, GATEWAY_LAT, GATEWAY_LON

STUDY = Study(
    name="iot4cows",
    site="Guamal, Meta, Colombia",
    description=(
        "Capacity of a single-gateway LoRaWAN network for collar-mounted cattle "
        "monitoring over an 88.54 ha grazing area."
    ),

    # US915 uplink at 125 kHz runs SF7 to SF10. SF11 and SF12 exist in other
    # regional plans but not on this band's 125 kHz uplink data rates.
    region="US915",
    bw_khz=125,
    spreading_factors=(7, 8, 9, 10),

    # RAK2245 concentrator, built on the Semtech SX1301 baseband with an
    # SX1257 front-end. Sensitivity, channel count and the demodulation limit
    # all come from the SX1301 datasheet via presets.py.
    chip="SX1301",
    n_gateways=1,

    # Link budget: node 22 dBm, node antenna 2 dBi, gateway antenna 8 dBi,
    # 1 dB cable and connector loss. Net gain 9 dB.
    tx_power_dbm=22.0,
    tx_antenna_gain_db=2.0,
    rx_antenna_gain_db=8.0,
    cable_loss_db=1.0,

    # Log-distance model fitted to RSSI measured across the site. Expressed at
    # d0 = 100 m, which lies inside the range the fit covers. The same line at
    # d0 = 1 m would read 87.1 dB, roughly 55 dB above free-space loss at
    # 915 MHz, because that is the fitted line extrapolated far outside its
    # validity range. Both forms give L(2210 m) = 159.3 dB.
    path_loss_exponent=2.16,
    path_loss_ref_db=130.30,
    path_loss_ref_distance_m=100.0,
    min_valid_distance_m=30.0,
    path_loss_r_squared=0.634,
    path_loss_source=(
        "Field fit over 1,229 aggregated RSSI points, 30 m to 2.21 km, "
        "IoT4Cows deployment"
    ),

    # 15 s is the shortest reporting interval the firmware supports, four times
    # the channel occupancy of the one-minute operational setting. Capacity
    # obtained here is therefore a lower bound for productive operation.
    payload_bytes=32,
    coding_rate=1,
    send_interval_s=15.0,
    capture_threshold_db=6.0,

    # Nodes are spread over the digitised grazing boundary: three disjoint
    # paddocks plus the farmstead, 88.54 ha, with the gateway at its surveyed
    # position. The farthest point of the site is 958 m away.
    placement="polygon",
    polygons_m=FARM_POLYGONS_M,
    gateway_lat=GATEWAY_LAT,
    gateway_lon=GATEWAY_LON,

    # An adaptive multi-SF scenario was evaluated and dropped. Over this site
    # every node falls within SF7 range (958 m against an SF7 reach of about
    # 1.8 km), so the adaptive scenario degenerates into fixed SF7 and carries
    # no information of its own.
    scenarios=("SF7", "SF8", "SF10"),
    # Written out rather than regenerated with node_counts_logspace(3, 300):
    # this is the exact grid behind the published figures, and the interpolated
    # crossing depends on which points bracket the threshold. A regenerated
    # grid would be equally valid but would shift the third digit, which would
    # defeat the purpose of keeping this study as a reproduction check.
    node_counts=(3, 4, 5, 6, 7, 8, 10, 12, 14, 17, 20, 23, 28, 33, 39, 46,
                 54, 65, 77, 91, 108, 128, 152, 180, 213, 253, 300),
    sim_time_s=3600.0,
    n_runs=30,
    base_seed=99,
    der_threshold=0.9,

    highlight_scenario="SF8",
    plot_zoom_xlim=(10, 160),
    figure_basename="iot4cows_capacity",
)
