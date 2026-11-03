"""Shared fixtures. No test should build a SimConfig by hand: every required
field would then have to be repeated, and adding a field would break every
file at once."""
import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loracap.core import SimConfig

# Bor et al., MSWiM 2016, Table 1, measured on an XRange SX1272 at 125 kHz.
BOR_SENSITIVITY_125 = {
    7: -126.50, 8: -127.25, 9: -131.25, 10: -132.75, 11: -134.50, 12: -133.25,
}

# The Guamal deployment's fitted propagation model, for tests that want a
# realistic site rather than round numbers.
GUAMAL = dict(
    path_loss_exponent=2.159, path_loss_ref_db=130.32,
    path_loss_ref_distance_m=100.0, min_valid_distance_m=30.0,
    tx_power_dbm=22.0, net_antenna_gain_db=9.0,
)


# Study spells the link budget as separate gains, SimConfig as a net figure.
GUAMAL_STUDY_FIELDS = dict(
    path_loss_exponent=2.159, path_loss_ref_db=130.32,
    path_loss_ref_distance_m=100.0, min_valid_distance_m=30.0,
    tx_power_dbm=22.0, tx_antenna_gain_db=3.0, rx_antenna_gain_db=6.0,
)


def config(**overrides) -> SimConfig:
    """A SimConfig with every required field filled, overridable by keyword."""
    base = dict(
        payload_bytes=20, coding_rate=1,
        tx_power_dbm=14.0, net_antenna_gain_db=0.0,
        path_loss_exponent=2.08, path_loss_ref_db=127.41,
        path_loss_ref_distance_m=40.0, min_valid_distance_m=1.0,
        sensitivity_dbm=dict(BOR_SENSITIVITY_125),
        bw_khz=125, n_channels=1, max_simultaneous_demodulations=None,
        avg_send_interval_ms=1e6,
    )
    base.update(overrides)
    return SimConfig(**base)


def study(**overrides):
    """A minimal valid Study, overridable by keyword."""
    from loracap.study import Study
    base = dict(
        name="t", region="US915", bw_khz=125, chip="SX1308",
        payload_bytes=32, scenarios=("SF8",), spreading_factors=(7, 8, 9, 10),
        placement="disc", path_loss_source="test fixture",
        **GUAMAL_STUDY_FIELDS,
    )
    base.update(overrides)
    return Study(**base)

