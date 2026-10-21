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

# ---------------------------------------------------------------------------
# Regional uplink spreading factors at 125 kHz
#
# Source: LoRa Alliance, LoRaWAN Regional Parameters. These are the SFs
# available for uplink on the 125 kHz data rates of each plan. Some plans also
# define a higher-bandwidth uplink data rate (US915 DR4 is SF8 at 500 kHz, for
# example) which is outside the fixed-bandwidth model used here.
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


# ---------------------------------------------------------------------------
# Gateway receiver sensitivity at 125 kHz [dBm]
#
# Only chips whose table has actually been read from the manufacturer's
# datasheet appear here. For anything else, read the datasheet and put the
# values in your study.
# ---------------------------------------------------------------------------
SENSITIVITY_125KHZ = {
    # Semtech SX1301 datasheet V2.4 (June 2017), Table 12, "125 kHz Mode:
    # IF8, IF[0 to 7] Paths". Typical measurements around 867 MHz with an
    # SX1257 front-end per the reference design. The datasheet states these
    # depend only on bandwidth and spreading factor, not on carrier frequency,
    # so they also apply to other bands using the same front-end design.
    "SX1301": {7: -126.5, 8: -129.0, 9: -131.5, 10: -134.0, 11: -136.5, 12: -139.5},
}

SENSITIVITY_SOURCE = {
    "SX1301": "Semtech SX1301 datasheet V2.4 (June 2017), Table 12",
}

# Simultaneous demodulation paths, chip-wide and independent of channel.
# SX1301: datasheet section 3.6.2 states the chip detects preambles on all of
# IF0-IF7 at every data rate but cannot demodulate more than 8 packets at once.
# The same section notes this count is a system parameter that a custom design
# could set differently, so confirm it for your module.
MAX_SIMULTANEOUS_DEMODULATIONS = {
    "SX1301": 8,
}

N_UPLINK_CHANNELS = {
    # SX1301 reference design: IF0-IF7, eight 125 kHz uplink channels.
    "SX1301": 8,
}


def sensitivity_for(chip: str, spreading_factors) -> dict:
    """Sensitivity table for `chip`, restricted to `spreading_factors`.

    Raises rather than guessing, both when the chip is unknown and when the
    requested SF is outside the chip's table.
    """
    if chip not in SENSITIVITY_125KHZ:
        raise KeyError(
            f"No verified sensitivity table for {chip!r}. Known chips: "
            f"{sorted(SENSITIVITY_125KHZ)}. Read the datasheet for your gateway "
            f"and pass sensitivity_dbm explicitly in your study instead."
        )
    table = SENSITIVITY_125KHZ[chip]
    missing = [sf for sf in spreading_factors if sf not in table]
    if missing:
        raise KeyError(f"{chip} sensitivity table has no entry for SF{missing}.")
    return {sf: table[sf] for sf in spreading_factors}


def region_sfs(region: str):
    """125 kHz uplink spreading factors for a region."""
    key = region.upper()
    if key not in REGION_UPLINK_SF_125KHZ:
        raise KeyError(
            f"Unknown region {region!r}. Known: {sorted(REGION_UPLINK_SF_125KHZ)}. "
            f"If your band is not listed, pass the spreading factors explicitly."
        )
    return REGION_UPLINK_SF_125KHZ[key]
