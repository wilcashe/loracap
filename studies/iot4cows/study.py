#!/usr/bin/env python3
"""
IoT4Cows: LoRaWAN cattle-monitoring deployment, Guamal, Meta, Colombia.

This is a worked example. It is the configuration behind the scalability
analysis published with the IoT4Cows paper, kept in the repository for two
reasons: it shows every field filled with a real, sourced value, and it lets
anyone confirm the engine still reproduces the published figures.

Expected result at DER = 0.9, with the parameters below:

    SF9    ~34 nodes     conservative bound (the slowest US915 125 kHz data
                         rate that can carry a 32-byte payload)
    SF8    ~62 nodes     the deployed configuration
    SF7   ~115 nodes     optimistic bound (shortest airtime)

The published article (Smart Agricultural Technology,
doi:10.1016/j.atech.2026.102644) used SF10 as the conservative bound and
reports about 18 nodes for it, from the code at commit 8779a30 of
github.com/wilcashe/loracap. SF10 is US915 DR0, whose ceiling is eleven bytes
of application payload, so a 32-byte reading cannot be sent at that rate and
the study now uses SF9. The error was conservative and SF8, the headline
figure, is unaffected. See the comment on `scenarios` below.

Run `python3 run.py reproduce iot4cows --only headline` and compare. A
difference means the engine changed, not the configuration. Every other
result quoted for this site is in experiments.py.
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

    # The same fit gives a residual sigma of 7.41 dB, which is the log-normal
    # shadowing term. It is deliberately NOT applied here, because this study
    # exists to reproduce a published analysis that used a deterministic
    # model, and turning it on would change every number. `check` warns about
    # the discarded residual, which is correct: it is being discarded, for a
    # stated reason.
    #
    # Set shadowing_sigma_db=7.41 to see what it costs. On a fixed spreading
    # factor it is not a small correction: SF8 capacity falls from 62.6 to
    # 53.2, and the confidence interval widens from about 3 nodes to 25,
    # because whether an unlucky node lands below sensitivity starts to
    # dominate the answer.
    shadowing_sigma_db=0.0,

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
    # The published figure used SF7, SF8 and SF10, SF10 standing as the
    # conservative bound. SF10 is US915 DR0, which carries at most 11 bytes of
    # application payload, so a 32-byte reading cannot be sent at that data
    # rate: the band would refuse it. The error is conservative, because the
    # airtime computed for 32 bytes at SF10 is longer than any legal SF10
    # uplink, so the published SF10 capacity is lower than the true bound.
    # Nothing else moves. SF8 is DR2 with a 125-byte ceiling, and the network
    # was deployed at SF9, DR1, with 53 bytes.
    #
    # SF9 replaces SF10 here, so the conservative bound is now the slowest data
    # rate this payload can legally carry, and it is also the rate the network
    # actually ran at. The third curve moves a long way as a result: SF10 with
    # this payload crosses the threshold at 17.5 nodes, SF9 at 33.9, because
    # airtime nearly halves, from 453 ms to 247 ms. SF7 and SF8 are untouched,
    # and SF8, the headline figure, still crosses at 61.8.
    scenarios=("SF7", "SF8", "SF9"),
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
