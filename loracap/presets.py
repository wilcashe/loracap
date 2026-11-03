#!/usr/bin/env python3
"""
loracap.presets
========================

Reference data that is the same for everyone, so no study has to retype it:
regional uplink spreading-factor ranges, and receiver sensitivity tables for
gateway chips.

Two rules govern this file.

First, nothing here is invented. Every value carries its source. Where a value
has not been verified against a primary document it is simply absent, and the
study must supply it. An absent preset is not a gap to fill with a plausible
number.

Second, a preset is a convenience, never an authority. Regional parameters are
revised, and a chip may be characterised differently in a newer datasheet
revision or by a module vendor. Check the current document for your band and
hardware before publishing anything that rests on these numbers.
"""
import math


# ---------------------------------------------------------------------------
# Regional uplink spreading factors at 125 kHz
#
# Source: LoRa Alliance, LoRaWAN Regional Parameters. These are the SFs
# defined for uplink on the 125 kHz data rates of each plan. Higher-bandwidth
# uplink data rates (US915 DR4 is SF8 at 500 kHz, for example) are carried by
# DATA_RATES below, with their bandwidth.
#
# CN470 still lists SF12 because RP002 keeps DR0 defined, but declares it
# unavailable since RP002-1.0.1. Its payload ceiling of zero in
# MAX_APP_PAYLOAD_BYTES is what stops a study from using it.
#
# SF6 and SF5 at 125 kHz, optional uplink data rates since RP002-1.0.5, are
# deliberately absent. See the note above DATA_RATES.
#
# Getting this wrong is a classic reviewer catch: simulating SF11 or SF12 in a
# band whose uplink stops at SF10 inflates nothing, but simulating a band's
# full range when the deployment cannot use it misrepresents the system.
# ---------------------------------------------------------------------------
REGION_UPLINK_SF_125KHZ = {
    "US915": (7, 8, 9, 10),
    "AU915": (7, 8, 9, 10, 11, 12),
    "EU868": (7, 8, 9, 10, 11, 12),
    "AS923": (7, 8, 9, 10, 11, 12),
    "IN865": (7, 8, 9, 10, 11, 12),
    "KR920": (7, 8, 9, 10, 11, 12),
    "RU864": (7, 8, 9, 10, 11, 12),
    "CN470": (7, 8, 9, 10, 11, 12),
}

REGION_NOTES = {
    "US915": "Uplink DR0-DR3 are SF10-SF7 at 125 kHz. DR4 is SF8 at 500 kHz, "
             "not covered by the fixed-bandwidth model used here.",
    "AU915": "Mirrors the US915 channel plan but, unlike US915, its 125 kHz "
             "uplink data rates extend down to SF12.",
}

# Centre of each plan's 125 kHz uplink range [MHz], from the same Regional
# Parameters document. Nothing in the simulation depends on this: the
# collision model is frequency-independent and the propagation model carries
# its own fitted or assumed constants. It is here for one purpose, which is to
# say whether a published path-loss exponent was measured anywhere near the
# band being simulated. An exponent measured at 868 MHz transfers to 915 MHz
# without comment. The same number carried to CN470 does not.
REGION_UPLINK_MHZ = {
    "US915": 908.6,     # 902.3-914.9 (ch 0-63) and 903.0-914.2 (ch 64-71)
    "AU915": 921.5,     # 915.2-927.8
    "EU868": 868.3,     # 868.1 / 868.3 / 868.5 default channels
    "AS923": 923.3,     # AS923-1 default channels 923.2 / 923.4
    "IN865": 865.5,     # 865.0625 / 865.4025 / 865.985
    "KR920": 922.7,     # 922.1-923.3 default channels
    "RU864": 869.0,     # 868.9 / 869.1
    "CN470": 479.8,     # 470.3-489.3 uplink
}


# ---------------------------------------------------------------------------
# Receiver sensitivity [dBm], indexed by bandwidth and then spreading factor
#
# LoRaWAN is not a 125 kHz-only protocol: EU868 DR6 is SF7 at 250 kHz, US915
# DR4 and AU915 DR6 are SF8 at 500 kHz, CN470 DR6 is SF7 at 500 kHz. A table
# indexed by spreading factor alone cannot describe those data rates, and
# reusing the 125 kHz figure at 500 kHz is about 6 dB optimistic, which
# inflates range by roughly half again at a typical path-loss exponent.
#
# Only tables actually read from a source appear here. Where a bandwidth is
# missing, `sensitivity_for` DERIVES it rather than reusing the wrong figure,
# and says so. See that function for how well the derivation holds up.
# ---------------------------------------------------------------------------
SENSITIVITY_DBM = {
    # Semtech SX1301 datasheet V2.4 (June 2017), Table 12, "125 kHz Mode:
    # IF8, IF[0 to 7] Paths".
    #
    # Section 3.12 states these are typical measurements around 867 MHz using
    # an SX1257 front end WITH an external low-noise amplifier, SAW filter and
    # TRX switch, as described in that datasheet's reference design section. A
    # gateway built without the external LNA will be worse than this table, not
    # better. The datasheet also gives the means to recompute them for another
    # front end: Sensitivity(dBm) = -174 + 10*log10(BW) + SNR + NF.
    #
    # The same section states the values depend only on bandwidth and spreading
    # factor, not on carrier frequency, so they apply to other bands using the
    # same front-end design.
    "SX1301": {
        125: {7: -126.5, 8: -129.0, 9: -131.5, 10: -134.0, 11: -136.5, 12: -139.5},
        # Table 12 is headed "125 kHz Mode". The 250 and 500 kHz paths
        # (IF9) are not transcribed here, so those bandwidths are derived.
    },

    # Semtech SX1308. THESE ARE NOT SX1308 FIGURES.
    #
    # The SX1308 datasheet (V1.2, June 2017) publishes no per-spreading-factor
    # sensitivity table. Its section 3 ends at 3.11, there is no Table 12, and
    # the string "dBm" appears twice in the whole document: once in the feature
    # list ("Up to -139 dBm sensitivity with SX1257") and once about transmit
    # power. The values below are the SX1301's, reused.
    #
    # Grounds for reusing them:
    #   - both devices integrate the same LoRa concentrator IP behind an
    #     SX1255/SX1257 front end;
    #   - the two datasheets carry near-identical wording on channel structure
    #     (8 x 125 kHz uplink channels, IF0-IF7) and on the limit of 8
    #     simultaneous packet demodulations;
    #   - the SX1308's stated best case of -139 dBm is consistent with the
    #     SX1301's -139.5 dBm at SF12.
    #
    # This is a documented assumption, not a measured table. Say so wherever
    # results obtained with this preset are reported. Note also that gateway
    # vendors quote more optimistic figures still: the Dragino LPS8, an
    # SX1308 design, claims -140 dBm, 1 dB beyond the chip manufacturer.
    "SX1308": {
        125: {7: -126.5, 8: -129.0, 9: -131.5, 10: -134.0, 11: -136.5, 12: -139.5},
    },

    # Bor, Roedig, Voigt and Alonso, MSWiM 2016, Table 1: sensitivity they
    # MEASURED on an XRange SX1272, which is a node radio, not a gateway
    # concentrator. Included because it is the only fully sourced table
    # here that covers all three bandwidths, and because the reproduction
    # studies need it. Note SF12 comes out less sensitive than SF11 in
    # their measurements: that is their result, not a transcription error.
    "XRange_SX1272": {
        125: {7: -126.50, 8: -127.25, 9: -131.25,
              10: -132.75, 11: -134.50, 12: -133.25},
        250: {7: -124.25, 8: -126.75, 9: -128.25,
              10: -130.25, 11: -132.75, 12: -132.25},
        500: {7: -120.75, 8: -124.00, 9: -127.50,
              10: -128.75, 11: -128.75, 12: -132.25},
    },
}

SENSITIVITY_SOURCE = {
    "SX1301": "Semtech SX1301 datasheet V2.4 (June 2017), Table 12",
    "SX1308": ("Semtech SX1301 datasheet V2.4 (June 2017), Table 12, reused for "
               "the SX1308, whose datasheet (V1.2) publishes no per-SF table. "
               "Documented assumption, not a measured table."),
}

# Simultaneous packet demodulations, chip-wide and independent of channel.
#
# Do not confuse this with "demodulation paths". Vendors advertise the SX1308
# as having 10 programmable parallel demodulation paths, but those are IF0-IF9:
# eight 125 kHz LoRa channels, one LoRa backhaul channel and one GFSK channel.
# The number of packets demodulated at once is 8 on both chips.
#
# SX1301 datasheet section 3.6.2 and SX1308 datasheet section 3.6.2 both state
# the chip detects preambles on all of IF0-IF7 at every data rate but "cannot
# demodulate more than 8 packets simultaneously", and both add that this count
# is an arbitrary system parameter a custom circuit could set differently.
# Confirm it for your module.
MAX_SIMULTANEOUS_DEMODULATIONS = {
    "SX1301": 8,
    "SX1308": 8,
}

N_UPLINK_CHANNELS = {
    # SX1301 reference design: IF0-IF7, eight 125 kHz uplink channels.
    "SX1301": 8,
    # SX1308 datasheet: "The system uses 8 separate 125 kHz LoRa channels for
    # star connection to sensors", plus a 250 kHz backhaul channel and a GFSK
    # channel that are outside this fixed-bandwidth model.
    "SX1308": 8,
}


# ---------------------------------------------------------------------------
# Rejection between spreading factors
# ---------------------------------------------------------------------------
# Minimum signal-to-interference ratio [dB] a packet needs to survive an
# overlapping packet on ANOTHER spreading factor in the same channel, indexed
# [reference SF][interfering SF]. Negative values mean the interferer may be
# that much stronger before the reference packet is lost.
#
# LoRa spreading factors are quasi-orthogonal, not orthogonal. LoRaSim, and
# this engine by default, treat them as orthogonal. These tables are what a
# study names in `inter_sf_rejection` to stop doing so.
#
# Two tables, one per chip family. They agree within 1.5 dB everywhere.
#
# CROCE2020_SX1272: Croce, Gucciardo, Mangione, Santaromita and Tinnirello,
# "LoRa Technology Demystified: From Link Behavior to Cell-Level Performance",
# IEEE Trans. Wireless Commun. 19(2):822-834, 2020,
# doi:10.1109/TWC.2019.2948872, Table I. Measured on a Semtech SX1272 node
# radio receiving a reference stream of 500 packets with a 20-byte payload,
# with an interfering stream synthesised in software, summed with it at a set
# SIR from -30 to +6 dB and transmitted from a USRP B210. Each interfering
# packet was offset at random within a window guaranteeing at least one
# symbol of overlap, which is why the engine applies the table only to
# overlaps of at least one symbol of the reference packet.
#
# What the source does not state, and so what a result built on this table
# inherits as an assumption: the bandwidth and coding rate of this test (the
# paper's simulations use 500 kHz and CR 4/5), and how a gateway
# concentrator such as the SX1301 or SX1308 compares with the SX1272. The
# diagonal of Table I, 1 dB, is the same-SF capture threshold and is not here:
# same-SF collisions are the capture rule's, under `capture_threshold_db`.
# The authors note the theoretical values usually quoted for this table
# (Goursaud and Gorce, 2015) are about 10 dB less demanding than measured.
INTER_SF_REJECTION_DB = {
    "CROCE2020_SX1272": {
        7: {8: -8.0, 9: -9.0, 10: -9.0, 11: -9.0, 12: -9.0},
        8: {7: -11.0, 9: -11.0, 10: -12.0, 11: -13.0, 12: -13.0},
        9: {7: -15.0, 8: -13.0, 10: -13.0, 11: -14.0, 12: -15.0},
        10: {7: -19.0, 8: -18.0, 9: -17.0, 11: -17.0, 12: -18.0},
        11: {7: -22.0, 8: -22.0, 9: -21.0, 10: -20.0, 12: -20.0},
        12: {7: -25.0, 8: -25.0, 9: -25.0, 10: -24.0, 11: -23.0},
    },
    # EIGNER2021_SX1301: Eigner, "Interference Analysis of LoRaWAN Systems",
    # diploma thesis, TU Wien, 2021, Table 5.2. Measured on a Semtech SX1301
    # concentrator (iC880A), the gateway chip family of the shipped studies,
    # receiving two signals replayed from recordings of an RN2483 node, both
    # at 125 kHz with a 20-byte payload, the interferer starting at a random
    # delay during the first. Each value is the SIR above which more than 99%
    # of packets on the reference spreading factor were delivered. The
    # paragraph after the table calls it table 5.1, a slip: the values are
    # Table 5.2's, and the measured curves of the thesis's Figure 5.10 cross
    # 99% at the tabulated -20 dB (SF11 against SF12) and -22.5 dB (SF12
    # against SF11). The coding rate is not stated, and the random delay
    # covered the whole first packet, so overlaps shorter than one symbol
    # were part of the measurement where the engine leaves them harmless.
    "EIGNER2021_SX1301": {
        7: {8: -8.5, 9: -9.0, 10: -9.0, 11: -9.5, 12: -9.5},
        8: {7: -11.0, 9: -11.0, 10: -11.5, 11: -12.0, 12: -12.5},
        9: {7: -14.5, 8: -14.0, 10: -14.0, 11: -14.0, 12: -14.5},
        10: {7: -19.0, 8: -16.5, 9: -16.0, 11: -17.0, 12: -17.0},
        11: {7: -21.5, 8: -22.0, 9: -21.0, 10: -20.5, 12: -20.0},
        12: {7: -24.5, 8: -24.5, 9: -24.0, 10: -23.0, 11: -22.5},
    },
}

INTER_SF_REJECTION_SOURCE = {
    "CROCE2020_SX1272": (
        "Croce et al., IEEE Trans. Wireless Commun. 19(2):822-834, 2020, "
        "doi:10.1109/TWC.2019.2948872, Table I, measured on an SX1272 node "
        "radio. Bandwidth and coding rate of the test not stated."),
    "EIGNER2021_SX1301": (
        "Eigner, diploma thesis, TU Wien, 2021, Table 5.2, measured on an "
        "SX1301 concentrator at 125 kHz. Coding rate of the test not stated."),
}


# ---------------------------------------------------------------------------
# Survival of a locked packet, per spreading factor
# ---------------------------------------------------------------------------
# Minimum SIR [dB] the packet a receiver has locked onto needs against a
# later packet on the same channel and spreading factor, arriving past the
# lock window, to be received. Used only by the lock receiver rule, through
# `lock_survival` on a study, in place of `capture_threshold_db` for that one
# decision. See `core.resolve_overlap`.
#
# EIGNER2021_SX1301: Eigner, "Interference Analysis of LoRaWAN Systems",
# diploma thesis, TU Wien, 2021, Table 5.1. Measured on a Semtech SX1301
# concentrator (iC880A) receiving two signals replayed from recordings of an
# RN2483 node, 125 kHz, 20-byte payload, the second starting at a delay drawn
# uniformly over the length of the first. Each value is the SIR of the first
# signal above which more than 99% of first packets were delivered.
#
# What that makes it, and what it does not say: it is the 99% point, so used
# as a step it is pessimistic wherever the transition is wide. At SF12 and
# equal power the step loses every first packet, where the same thesis
# measured 68% dropped. The coding rate of the collision tests is not stated
# in that chapter. And the delay covered the whole first packet, so the
# figure averages over offsets the lock rule otherwise treats apart.
LOCK_SURVIVAL_DB = {
    "EIGNER2021_SX1301": {7: 0.0, 8: 0.0, 9: 0.4, 10: 1.3, 11: 2.0, 12: 2.0},
}

LOCK_SURVIVAL_SOURCE = {
    "EIGNER2021_SX1301": (
        "Eigner, diploma thesis, TU Wien, 2021, Table 5.1, SX1301: SIR of the "
        "first packet above which more than 99% were delivered. A step at the "
        "99% point, pessimistic at SF9 to SF12. Coding rate not stated."),
}


def lock_survival(name: str):
    """A named locked-packet survival table, as a fresh dict."""
    key = name.upper()
    if key not in LOCK_SURVIVAL_DB:
        raise ValueError(
            f"No lock survival table named {name!r}. Known: "
            f"{', '.join(sorted(LOCK_SURVIVAL_DB))}.")
    return dict(LOCK_SURVIVAL_DB[key])


def inter_sf_rejection(name: str):
    """A named rejection table, as a fresh nested dict."""
    key = name.upper()
    if key not in INTER_SF_REJECTION_DB:
        raise ValueError(
            f"No inter-SF rejection table named {name!r}. Known: "
            f"{', '.join(sorted(INTER_SF_REJECTION_DB))}.")
    return {ref: dict(row) for ref, row in INTER_SF_REJECTION_DB[key].items()}


# ---------------------------------------------------------------------------
# Measured path-loss exponents by environment
#
# Source, for every value below:
#   Gonzalez-Palacio, Tobon-Vallejo, Sepulveda-Cano, Rua and Le,
#   "A Critical Review of the Propagation Models Employed in LoRa Systems",
#   Sensors 24(12):3877, 2024, doi:10.3390/s24123877, Table 12
#   ("Parameters derived from measurements with LoRa").
#
# That review collects single-slope log-distance fits from published LoRa
# measurement campaigns. Its model is
#
#     PL(d) = alpha + 10 * beta * log10(d)
#
# so its beta is exactly `path_loss_exponent` here, and its alpha is the loss
# at 1 m. The review calls this the floating-intercept form and is explicit
# that alpha need not equal free-space loss at 1 m: it is the fitted line
# extrapolated back, not a physical measurement. That is the same reason this
# tool asks for a reference distance inside the fitted range.
#
# Read these ranges as the spread actually observed in the literature for an
# environment label, NOT as a value to adopt. Four cautions:
#
#   - The labels are the original authors'. "Rural" spans open pasture to
#     scattered woodland, and the spread within each label shows it.
#   - Values are pooled across frequency and across very different distance
#     ranges, from tens of metres to tens of kilometres.
#   - Exponents below 2 appear, which the review attributes partly to
#     waveguiding and partly to single-slope fits over ranges where a
#     multi-slope model fits better.
#   - The review's central argument is that single-slope fits are often
#     inadequate. This simulator uses a single slope, so a swept range is a
#     coarser description of reality than the best available models.
# ---------------------------------------------------------------------------
TERRAIN_EXPONENTS = {
    # label:     (lowest, highest, median, number of studies, frequencies MHz)
    "rural":     (1.87, 3.39, 2.94, 3, (868,)),
    "suburban":  (1.47, 4.67, 3.54, 10, (868, 915)),
    "urban":     (1.45, 3.24, 2.34, 7, (868,)),
    "forest":    (2.53, 5.97, 3.17, 6, (433, 868, 915, 920)),
    "campus":    (2.25, 5.30, 3.07, 4, (868, 915)),
}

TERRAIN_SOURCE = (
    "Gonzalez-Palacio et al., 'A Critical Review of the Propagation Models "
    "Employed in LoRa Systems', Sensors 24(12):3877, 2024, "
    "doi:10.3390/s24123877, Table 12"
)


def terrain_range(label: str):
    """(low, high, median, n_studies, frequencies) for an environment label."""
    key = label.lower()
    if key not in TERRAIN_EXPONENTS:
        raise KeyError(
            f"Unknown terrain {label!r}. Known: {sorted(TERRAIN_EXPONENTS)}. "
            f"These are labels used by the source review, not a classification "
            f"of your site. If none fits, give the exponent range explicitly."
        )
    return TERRAIN_EXPONENTS[key]


# Measured against Bor et al.'s Table 1, the only fully sourced table here
# covering all three bandwidths. Deriving their 250 and 500 kHz columns from
# their own 125 kHz column gives:
#
#   250 kHz   mean error -1.18 dB, worst -2.51 dB
#   500 kHz   mean error -2.10 dB, worst -5.02 dB
#
# Every error has the same sign: the measured receiver is BETTER than the
# derivation says. So a derived figure understates sensitivity, which
# understates range, which is the safe direction to be wrong in for a
# coverage claim. The worst case, 5 dB at SF12, is not negligible: at a
# path-loss exponent of 2.16 that is about 70% of range. Derive to get a
# conservative answer, not a precise one, and say which values were derived.
SENSITIVITY_BW_SCALING_NOTE = (
    "Sensitivity scales as -174 + 10*log10(BW) + NF + SNR, and NF and SNR do "
    "not depend on bandwidth, so doubling the bandwidth costs 3.01 dB. Stated "
    "both in the SX1301 datasheet section 3.12 and in Bor et al. 2016 "
    "section 3.2."
)


def sensitivity_for(chip: str, spreading_factors, bw_khz: int = 125):
    """Sensitivity for `chip` at `bw_khz`, restricted to `spreading_factors`.

    Returns (table, derived_from) where `derived_from` is None when the
    bandwidth was tabulated and the bandwidth actually used otherwise.

    Raises rather than guessing when the chip is unknown or the spreading
    factor is outside its table. A missing BANDWIDTH is different: the
    relation between bandwidths is physics the datasheets state outright, so
    it is derived and reported rather than refused. See the note above for
    how far that derivation sits from measurement.
    """
    if chip not in SENSITIVITY_DBM:
        raise KeyError(
            f"No verified sensitivity table for {chip!r}. Known chips: "
            f"{sorted(SENSITIVITY_DBM)}. Read the datasheet for your gateway "
            f"and pass sensitivity_dbm explicitly in your study instead."
        )
    by_bw = SENSITIVITY_DBM[chip]
    if bw_khz in by_bw:
        base, derived_from = by_bw[bw_khz], None
    else:
        # nearest tabulated bandwidth, by ratio, so the correction is smallest
        derived_from = min(by_bw, key=lambda b: abs(math.log(bw_khz / b)))
        base = by_bw[derived_from]
    missing = [sf for sf in spreading_factors if sf not in base]
    if missing:
        raise KeyError(
            f"{chip} sensitivity table has no entry for SF{missing} at "
            f"{derived_from or bw_khz} kHz."
        )
    shift = 0.0 if derived_from is None else 10 * math.log10(bw_khz / derived_from)
    return ({sf: base[sf] + shift for sf in spreading_factors}, derived_from)


def sensitivity_derivation_error(chip: str = "XRange_SX1272", base_bw: int = 125):
    """How far the bandwidth derivation sits from measurement.

    For each other bandwidth the chip has MEASURED, derive it from `base_bw`
    by `10*log10(BW2/BW1)` and subtract. Negative means the receiver is better
    than the derivation says. Returns [(bw_khz, mean_error_db, worst_error_db)].

    A function rather than a quoted figure, because the README quotes these
    numbers and they must follow the table if it is ever corrected.
    """
    by_bw = SENSITIVITY_DBM[chip]
    out = []
    for bw in sorted(b for b in by_bw if b != base_bw):
        shift = 10 * math.log10(bw / base_bw)
        errs = [by_bw[bw][sf] - (by_bw[base_bw][sf] + shift)
                for sf in by_bw[base_bw] if sf in by_bw[bw]]
        out.append((bw, sum(errs) / len(errs), min(errs, key=lambda e: -abs(e))))
    return out


# ---------------------------------------------------------------------------
# Uplink data rates per regional plan
#
# Each entry is DR index -> (spreading factor, bandwidth [kHz], maximum
# application payload [bytes]). The payload figure is N, the application
# payload with no MAC options, from the repeater-compatible table.
#
# This is the table `REGION_UPLINK_SF_125KHZ` above is derived from, and it
# carries the two things that derivation throws away: the bandwidth each DR
# runs at, and the payload ceiling. The ceiling binds hard at the slow data
# rates. US915 DR0 allows ELEVEN bytes of application payload, so a 32-byte
# reading cannot be sent at SF10 in that plan at all, and a simulation that
# pairs the two is measuring a configuration the band would refuse.
#
# ONLY REGIONS WHOSE TABLE HAS ACTUALLY BEEN READ APPEAR HERE, and a payload
# figure of None means that region's DR-to-SF mapping was verified but its
# payload ceiling was not. The check degrades to silence rather than guessing:
# a wrong ceiling is worse than a missing one, because it would reject valid
# configurations or wave through invalid ones with equal confidence.
#
# A region absent from this table still validates against
# REGION_UPLINK_SF_125KHZ, it simply gets no bandwidth or payload check.
#
# LoRa data rates only. FSK and LR-FHSS data rates are not modelled. Neither
# are the OPTIONAL SF6 and SF5 data rates at 125 kHz that RP002-1.0.5 added
# to every plan except CN470 (EU868 DR12-DR13, US915 DR7-DR8, AU915 DR9-DR10,
# and so on). Leaving them out was decided, not overlooked: the gateway chips
# tabulated here (SX1301, SX1308) cannot demodulate them, so there is no
# sourced gateway sensitivity, the airtime of SF5 and SF6 has not been checked
# against a reference, and the capture model has never been exercised at
# those spreading factors. A study naming them is rejected as an undefined
# data rate, which is the safe failure.
# ---------------------------------------------------------------------------
DATA_RATES = {
    "EU868": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125), 4: (8, 125), 5: (7, 125), 6: (7, 250)},
    "US915": {0: (10, 125), 1: (9, 125), 2: (8, 125), 3: (7, 125), 4: (8, 500)},
    "AU915": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125), 4: (8, 125), 5: (7, 125), 6: (8, 500)},
    "AS923": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125), 4: (8, 125), 5: (7, 125), 6: (7, 250)},
    "IN865": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125), 4: (8, 125), 5: (7, 125)},
    "KR920": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125), 4: (8, 125), 5: (7, 125)},
    "RU864": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125), 4: (8, 125), 5: (7, 125), 6: (7, 250)},
    "CN470": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125), 4: (8, 125), 5: (7, 125), 6: (7, 500)},
}

MAX_APP_PAYLOAD_BYTES = {
    "EU868": {
        None: {0: 51, 1: 51, 2: 51, 3: 115, 4: 222, 5: 222, 6: 222},
    },
    "US915": {
        None: {0: 11, 1: 53, 2: 125, 3: 222, 4: 222},
    },
    "AU915": {
        0: {0: 51, 1: 51, 2: 51, 3: 115, 4: 222, 5: 222, 6: 222},
        400: {0: 0, 1: 0, 2: 11, 3: 53, 4: 125, 5: 222, 6: 222},
    },
    "AS923": {
        0: {0: 51, 1: 51, 2: 115, 3: 115, 4: 222, 5: 222, 6: 222},
        400: {0: 0, 1: 0, 2: 11, 3: 53, 4: 125, 5: 222, 6: 222},
    },
    "IN865": {
        None: {0: 51, 1: 51, 2: 51, 3: 115, 4: 222, 5: 222},
    },
    "KR920": {
        None: {0: 51, 1: 51, 2: 51, 3: 115, 4: 222, 5: 222},
    },
    "RU864": {
        None: {0: 51, 1: 51, 2: 51, 3: 115, 4: 222, 5: 222, 6: 222},
    },
    "CN470": {
        None: {0: 0, 1: 23, 2: 86, 3: 184, 4: 222, 5: 222, 6: 222},
    },
}

DATA_RATE_SOURCE = (
    "LoRa Alliance, LoRaWAN Regional Parameters RP002-1.0.5 (October 2025), "
    "repeater-compatible maximum payload tables. First extracted from the "
    "ChirpStack lorawan library, github.com/brocaar/lorawan, package `band` "
    "(RP002-1.0.2 / RP002-1.0.3), by parsing the package with Go's own AST, "
    "then checked against RP002-1.0.5 for all eight plans."
)

DATA_RATE_CHECKED_AGAINST = (
    "US915 and EU868 were checked line by line against the LoRaWAN Regional "
    "Parameters tables published at thethingsnetwork.org/docs/lorawan/"
    "regional-parameters/ and agree exactly. That check earned its keep: the "
    "first extraction had EU868 DR4-DR6 at 242 bytes instead of 222, because "
    "that one file in the library spells the parameter `repeatedCompatible` "
    "and the extractor was matching `repeaterCompatible`, so it silently read "
    "the non-repeater table. All eight plans were then checked line by line "
    "against RP002-1.0.5 itself: data rates in Tables 10, 19, 39, 50, 67, 80, "
    "91 and 102, payload ceilings in Tables 15, 24, 44, 54, 72, 85, 96 and "
    "107, transmit power in Tables 13, 22, 42, 50, 70, 83, 94 and 105. Every "
    "LoRa data rate and every payload ceiling agreed. The IN865 power offsets "
    "did not: the library stopped at -20 dB, RP002-1.0.5 goes to -28."
)

# Dwell-time-limited sub-bands change the ceilings drastically, and in AU915
# and AS923 the plan defines both cases. Under a 400 ms limit SF12 and SF11
# cannot complete a transmission at all, which is why their ceiling is zero
# rather than missing. A study in one of these plans has to say which case it
# is in: at DR2 the answer is 115 bytes or 11 bytes, and guessing is not a
# rounding error.
DWELL_TIME_REGIONS = tuple(
    r for r, t in MAX_APP_PAYLOAD_BYTES.items() if None not in t
)

# ---------------------------------------------------------------------------
# Transmit power offsets per regional plan [dB below the plan's maximum]
#
# LoRaWAN does not let a node pick an arbitrary power. It selects an index
# into this table, and the plan fixes what each index means. Every plan uses
# 2 dB steps and they differ only in how far down they reach, from 14 dB of
# range in EU868 to 28 dB in AU915.
#
# This matters for capacity through a route that is easy to miss. The capture
# effect resolves a collision only when the two signals differ by more than
# the capture threshold, so what feeds it is the SPREAD of received powers.
# Power control exists to remove exactly that spread, bringing every node
# down to roughly the same level at the gateway. The step size is what stops
# the spread collapsing to zero.
#
# Same sources as the data-rate tables above, checked against RP002-1.0.5.
#
# US915 needs a rule, not just a table. RP002-1.0.5 Table 22 gives ABSOLUTE
# conducted levels, "30 dBm - 2*TXPower" from index 0 to 14, so 30 dBm down
# to 2 dBm, while the text above it calls them relative to the device's
# maximum. The two readings agree only for a 30 dBm device. Read as absolute,
# which is the decision taken here, a node can reduce power in 2 dB steps
# from its own level down to the 2 dBm floor and no further: a 22 dBm node
# reaches -20 dB, a 14 dBm node -12 dB. The table below is therefore the full
# 30 dBm ladder, and `region_tx_power_offsets` cuts it at the floor for the
# node's actual power. Every other plan states its levels relative to the
# maximum EIRP and needs no floor.
# ---------------------------------------------------------------------------
TX_POWER_OFFSETS_DB = {
    "EU868": (0, -2, -4, -6, -8, -10, -12, -14),
    "US915": (0, -2, -4, -6, -8, -10, -12, -14, -16, -18, -20, -22, -24, -26, -28),
    "AU915": (0, -2, -4, -6, -8, -10, -12, -14, -16, -18, -20, -22, -24, -26, -28),
    "AS923": (0, -2, -4, -6, -8, -10, -12, -14),
    "IN865": (0, -2, -4, -6, -8, -10, -12, -14, -16, -18, -20, -22, -24, -26, -28),
    "KR920": (0, -2, -4, -6, -8, -10, -12, -14),
    "RU864": (0, -2, -4, -6, -8, -10, -12, -14),
    "CN470": (0, -2, -4, -6, -8, -10, -12, -14),
}


# ---------------------------------------------------------------------------
# Transmit current draw [mA], indexed by transmit power [dBm]
#
# Energy is the one figure here that depends on the NODE's radio rather than
# the gateway's, and node radios differ by more than a factor of two at the
# same output power. There is no default: a study that wants an energy figure
# names a radio or supplies its own table, because a guessed current produces
# a battery-life number that looks authoritative and is fiction.
#
# This also only covers TRANSMISSION. A node that sends for two seconds a
# minute spends most of its life asleep, and sleep draw can dominate the
# budget entirely. See `Study.sleep_current_ua`.
# ---------------------------------------------------------------------------
TX_CURRENT_MA = {
    # From LoRaSim's loraDir.py, which gives it as "Transmit consumption in mA
    # from -2 to +17 dBm", split by power amplifier: RFO/PA0 below 2 dBm,
    # PA_BOOST/PA1 to 17, PA1+PA2 above. Consistent with the SX1272/76
    # datasheet's typical figures. The entries above 17 dBm are in LoRaSim's
    # list but outside the range its own comment claims, so treat them as less
    # certain than the rest.
    "SX1272": {
        -2: 22, -1: 22, 0: 22, 1: 23,
        2: 24, 3: 24, 4: 24, 5: 25, 6: 25, 7: 25, 8: 25, 9: 26,
        10: 31, 11: 32, 12: 34, 13: 35, 14: 44,
        15: 82, 16: 85, 17: 90,
        18: 105, 19: 115, 20: 125,
    },
}

TX_CURRENT_SOURCE = {
    "SX1272": (
        "LoRaSim (github.com/mcbor/lorasim), loraDir.py, the TX array. "
        "Describes the SX1272/76 family. A different node radio needs its own "
        "table: an STM32WL or an SX1262 draws materially different current at "
        "the same output power."
    ),
}

# LoRaSim pairs its current table with `V = 3.0  # voltage XXX`, the comment
# being the author's own marker that the figure is assumed rather than looked
# up. It is carried here as the default for that radio, with the same caveat:
# a node on two alkaline cells, a lithium primary and a regulated 3.3 V rail
# are three different numbers, and energy scales linearly with the choice.
DEFAULT_SUPPLY_VOLTAGE_V = 3.0


def tx_current_ma(radio: str, tx_power_dbm: float) -> float:
    """Current draw at a transmit power, for a known radio.

    Raises rather than extrapolating off the end of the table. Power amplifier
    stages switch at specific powers and the current jumps, so a value outside
    the measured range cannot be inferred from the ones inside it: in this
    table the step from 14 to 15 dBm nearly doubles the draw."""
    key = radio.upper()
    if key not in TX_CURRENT_MA:
        raise KeyError(
            f"No transmit current table for {radio!r}. Known: "
            f"{sorted(TX_CURRENT_MA)}. Supply tx_current_ma in your study."
        )
    table = TX_CURRENT_MA[key]
    rounded = int(round(tx_power_dbm))
    if rounded not in table:
        raise KeyError(
            f"{radio} has no current figure for {tx_power_dbm:g} dBm. The "
            f"table covers {min(table)} to {max(table)} dBm, and the power "
            f"amplifier stages switch inside that range, so a figure outside "
            f"it cannot be interpolated."
        )
    return float(table[rounded])


# Plans whose power table is absolute, with the lowest conducted level [dBm].
TX_POWER_ABSOLUTE_FLOOR_DBM = {
    "US915": 2.0,
}


def region_tx_power_offsets(region: str, tx_power_dbm=None):
    """Power offsets a plan allows a node at `tx_power_dbm`, or None when the
    plan has not been transcribed.

    For a plan with an absolute floor the ladder stops where the node would
    go below it, which depends on the node's own power. Without that power
    the full table is returned, so callers that know it must pass it."""
    key = region.upper()
    offsets = TX_POWER_OFFSETS_DB.get(key)
    floor = TX_POWER_ABSOLUTE_FLOOR_DBM.get(key)
    if offsets is None or floor is None or tx_power_dbm is None:
        return offsets
    return tuple(o for o in offsets if tx_power_dbm + o >= floor - 1e-9)


def region_data_rates(region: str):
    """DR table for a region, or None when it has not been transcribed."""
    return DATA_RATES.get(region.upper())


def needs_dwell_time(region: str) -> bool:
    """True when this plan's payload ceilings depend on the uplink dwell time,
    so a study in it must say which case applies."""
    return region.upper() in DWELL_TIME_REGIONS


def data_rate_for(region: str, sf: int, bw_khz: int, dwell_time_ms=None):
    """(DR index, maximum application payload) for a spreading factor at a
    bandwidth, or None when the plan defines no such uplink data rate.

    Three different answers have to stay distinguishable here. None means the
    combination is not an uplink data rate in this plan at all. A ceiling of
    None means the mapping is known and the ceiling is not. A ceiling of ZERO
    is a real value: that data rate carries no application payload, which is
    the case for CN470 DR0, and for SF12 and SF11 anywhere a 400 ms dwell
    limit applies, since neither can complete a transmission inside it."""
    table = region_data_rates(region)
    if table is None:
        return None
    key = region.upper()
    for dr, (dr_sf, dr_bw) in sorted(table.items()):
        if dr_sf != sf or dr_bw != bw_khz:
            continue
        ceilings = MAX_APP_PAYLOAD_BYTES.get(key, {})
        if needs_dwell_time(key):
            # No silent default: the two cases differ by more than tenfold at
            # the slow data rates, so an unstated dwell time is a missing
            # input rather than a value to assume.
            table_for_dwell = (None if dwell_time_ms is None
                               else ceilings.get(int(dwell_time_ms)))
        else:
            table_for_dwell = ceilings.get(None)
        max_n = None if table_for_dwell is None else table_for_dwell.get(dr)
        return dr, max_n
    return None


def region_sfs(region: str):
    """125 kHz uplink spreading factors for a region."""
    key = region.upper()
    if key not in REGION_UPLINK_SF_125KHZ:
        raise KeyError(
            f"Unknown region {region!r}. Known: {sorted(REGION_UPLINK_SF_125KHZ)}. "
            f"If your band is not listed, pass the spreading factors explicitly."
        )
    return REGION_UPLINK_SF_125KHZ[key]
