#!/usr/bin/env python3
"""
Reproduction of Bor et al.'s Experiment Set 1, configuration SN1.
=================================================================

Source
------
Bor, Roedig, Voigt and Alonso, "Do LoRa Low-Power Wide-Area Networks Scale?",
MSWiM 2016. Use the UPDATED version: Mariusz Slabicki found a bug by which
already-collided packets were in some cases marked as not collided, which
overestimated goodput. The figures were corrected and the conclusions held.

SN1 is the most robust configuration in Table 2: SF12, 125 kHz, CR 4/8, the
longest airtime LoRa offers. Its published airtime, 1712.13 ms, is quoted in
the companion interference paper and is an exact check on the airtime formula:
this tool computes 1712.13 ms.

SN1 differs from SN3 only in the coding rate, so it is the cheapest possible
control: anything that moves between the two studies has to be the coding
rate and nothing else.

Why this study exists
---------------------
The degeneracy ladder in `run.py validate` checks the engine against ALOHA
theory. This checks it against an independent published simulation, which is
a different question: theory says what the floor is, Bor et al. say what
their simulator got for a specific configuration. Reproducing their number is
the cheapest strong external validation available, and after any substantial
change to the engine it is the thing to re-run.

Every value below is from the paper, not inferred. Table 2 gives the
transmitter settings, Section 3.2 gives the propagation model, Table 1 gives
the measured receiver sensitivity.

Three settings that are NOT this tool's defaults, and would quietly produce a
different number if left alone:

  * ONE channel. SN3 fixes CF at 868 MHz. This tool defaults to the gateway
    chip's channel count, which would be eight.
  * NO demodulator limit. LoRaSim does not model an SX1301 concentrator.
  * THEIR sensitivity figures, measured on an XRange SX1272, which is a node
    radio. This tool's presets are gateway concentrators, and the two are not
    interchangeable.

Note on sigma. The paper fits sigma = 3.57 dB for the shadowing term and then
sets it to zero, stating that otherwise "some transmissions might not be able
to reach the sink rendering our results inconclusive". That is worth reading
twice: the variability was removed because it broke the result. This study
keeps sigma at zero to reproduce their figure. `shadowing_sigma_db=3.57` turns
it back on, and what happens then is a question their paper does not answer.
"""
from loracap import Study

# Table 1, measured receiver sensitivity at 125 kHz [dBm]. SF12 is less
# sensitive than SF11 in their measurements, which is their result, not a
# transcription error.
SENSITIVITY_125KHZ_XRANGE_SX1272 = {
    7: -126.50, 8: -127.25, 9: -131.25,
    10: -132.75, 11: -134.50, 12: -133.25,
}

STUDY = Study(
    name="bor2016_sn1",
    site="Bor et al. 2016, Experiment Set 1, SN1 (most robust settings)",
    description=(
        "Companion to bor2016_sn3, differing only in coding rate. "
        "Bor, Roedig, Voigt and Alonso, MSWiM 2016, updated version."
    ),

    # --- band and spreading factors ---
    region="EU868",
    bw_khz=125,
    spreading_factors=(12,),

    # --- gateway: LoRaSim models neither a concentrator nor a channel plan ---
    sensitivity_dbm=SENSITIVITY_125KHZ_XRANGE_SX1272,
    n_channels=1,
    max_simultaneous_demodulations=None,

    # --- link budget: Prx = Ptx + GL - Lpl, with GL = 0 ---
    tx_power_dbm=14.0,
    tx_antenna_gain_db=0.0,
    rx_antenna_gain_db=0.0,
    cable_loss_db=0.0,

    # --- propagation, Section 3.2: d0 = 40 m, Lpl(d0) = 127.41 dB, gamma = 2.08 ---
    path_loss_exponent=2.08,
    path_loss_ref_db=127.41,
    path_loss_ref_distance_m=40.0,
    min_valid_distance_m=1.0,
    shadowing_sigma_db=0.0,
    path_loss_source=(
        "Bor et al. 2016, Section 3.2: empirical measurements in a built-up "
        "environment, d0 = 40 m, Lpl(d0) = 127.41 dB, gamma = 2.08, "
        "sigma = 3.57 dB set to zero by the authors"
    ),

    # --- traffic, Table 2: 20 B every 16.7 min, CR 4/8 ---
    payload_bytes=20,
    coding_rate=4,
    send_interval_s=1000.0,
    capture_threshold_db=6.0,

    # LoRaSim computes energy with the same current table, so the figure can
    # be checked rather than merely produced. That check was made on SN3,
    # where coding rate 4/5 gives 1.32 s of airtime; see the comment
    # in bor2016_sn3/study.py. It was not repeated for SN1.
    radio="SX1272",
    supply_voltage_v=3.0,

    # --- placement: nodes uniformly inside the coverage disc ---
    placement="disc",

    # --- experiment design ---
    scenarios=("SF12",),
    node_counts=(10, 20, 30, 40, 50, 55, 60, 64, 70, 80, 90, 100, 120,
                 150, 200, 250, 300),
    sim_time_s=200_000.0,      # 200 packets per node
    n_runs=15,
    base_seed=99,
    der_threshold=0.9,

    highlight_scenario="SF12",
    figure_basename="bor2016_sn1",
)
