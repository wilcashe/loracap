"""What `check` catches.

A simulator with a bad parameter does not fail, it returns a wrong answer
quietly, so these are the tests that matter most to someone using the tool
rather than reading it.
"""
import unittest

from loracap.study import validate
from tests.helpers import study

NODE_SENSI = {7: -126.5, 8: -129.0, 9: -131.5, 10: -134.0,
              11: -136.5, 12: -139.5}


def errors(**over):
    return validate(study(**over))[0]


def warnings(**over):
    return validate(study(**over))[1]


def infos(**over):
    return validate(study(**over))[2]


def says(messages, *fragments):
    return any(all(f in m for f in fragments) for m in messages)


class TestPayloadCeilings(unittest.TestCase):

    def test_payload_over_the_data_rate_ceiling_is_an_error(self):
        """REGRESSION, and it was found in this repository's own published
        worked example after publication. US915 DR0 is SF10 at 125 kHz and
        carries eleven bytes. Pairing it with a 32-byte reading describes a
        transmission the band would refuse."""
        self.assertTrue(says(errors(scenarios=("SF10",), payload_bytes=32),
                             "payload_bytes = 32", "DR0", "11 bytes"))

    def test_payload_within_the_ceiling_is_fine(self):
        self.assertEqual(errors(scenarios=("SF8",), payload_bytes=32), [])

    def test_data_rate_carrying_no_payload_at_all_is_an_error(self):
        """CN470 DR0 has a ceiling of zero, which is a value rather than a
        gap. A transmission at that data rate cannot exist."""
        self.assertTrue(says(
            errors(region="CN470", scenarios=("SF12",),
                   spreading_factors=(12,), chip=None,
                   sensitivity_dbm=NODE_SENSI, n_channels=8,
                   max_simultaneous_demodulations=8),
            "no application payload at all"))


class TestBandwidthAndDataRates(unittest.TestCase):

    def test_spreading_factor_absent_from_the_plan_at_that_bandwidth(self):
        self.assertTrue(says(
            errors(bw_khz=500, scenarios=("SF7",), spreading_factors=(7,)),
            "SF7 at 500 kHz is not an uplink data rate"))

    def test_the_same_spreading_factor_at_a_legal_bandwidth_passes(self):
        """SF8 is DR2 at 125 kHz and DR4 at 500 kHz, so bandwidth is part of
        the question, not a detail."""
        self.assertEqual(
            errors(bw_khz=500, scenarios=("SF8",), spreading_factors=(8,)), [])

    def test_derived_sensitivity_is_declared(self):
        self.assertTrue(says(
            warnings(bw_khz=500, scenarios=("SF8",), spreading_factors=(8,)),
            "derived from its 125 kHz column", "+6.02 dB"))

    def test_tabulated_sensitivity_is_not_flagged(self):
        self.assertFalse(says(warnings(), "derived from"))


class TestDwellTime(unittest.TestCase):

    def test_plan_that_needs_a_dwell_time_demands_one(self):
        self.assertTrue(says(
            errors(region="AU915", scenarios=("SF10",),
                   spreading_factors=(10,), chip=None,
                   sensitivity_dbm=NODE_SENSI, n_channels=8,
                   max_simultaneous_demodulations=8),
            "uplink_dwell_time_ms"))

    def test_an_undefined_dwell_setting_is_rejected(self):
        self.assertTrue(says(
            errors(region="AU915", uplink_dwell_time_ms=200,
                   scenarios=("SF10",), spreading_factors=(10,), chip=None,
                   sensitivity_dbm=NODE_SENSI, n_channels=8,
                   max_simultaneous_demodulations=8),
            "not a setting AU915 defines"))

    def test_the_dwell_setting_changes_the_ceiling(self):
        common = dict(region="AU915", scenarios=("SF10",),
                      spreading_factors=(10,), chip=None,
                      sensitivity_dbm=NODE_SENSI, n_channels=8,
                      max_simultaneous_demodulations=8, payload_bytes=32)
        self.assertEqual(errors(uplink_dwell_time_ms=0, **common), [])
        self.assertTrue(says(errors(uplink_dwell_time_ms=400, **common),
                             "11 bytes"))


class TestAdaptiveScenarios(unittest.TestCase):

    def test_data_rates_the_payload_cannot_use_are_dropped(self):
        """A network server does not hand a node a data rate that cannot carry
        its payload, so neither does this."""
        s = study(scenarios=("MULTI",), payload_bytes=32)
        self.assertEqual(s.resolved_adaptive_sf_options(), (7, 8, 9))
        self.assertTrue(says(infos(scenarios=("MULTI",)),
                             "will not use SF10"))

    def test_a_smaller_payload_keeps_them(self):
        self.assertEqual(
            study(scenarios=("MULTI",), payload_bytes=11)
            .resolved_adaptive_sf_options(), (7, 8, 9, 10))

    def test_adr_reports_its_margin_and_power_range(self):
        self.assertTrue(says(infos(scenarios=("ADR",)),
                             "margin 10 dB", "down to"))

    def test_a_negative_margin_is_an_error(self):
        self.assertTrue(says(errors(scenarios=("ADR",), adr_margin_db=-1),
                             "cannot be negative"))


class TestPropagation(unittest.TestCase):

    def test_negative_sigma_is_an_error(self):
        self.assertTrue(says(errors(shadowing_sigma_db=-1.0),
                             "cannot be negative"))

    def test_discarding_a_large_residual_is_flagged(self):
        """A fit that explains two thirds of the spread, with shadowing left
        at zero, is throwing the rest away rather than modelling it."""
        self.assertTrue(says(warnings(path_loss_r_squared=0.634,
                                      shadowing_sigma_db=0.0),
                             "shadowing_sigma_db is 0"))

    def test_setting_sigma_clears_the_flag(self):
        self.assertFalse(says(warnings(path_loss_r_squared=0.634,
                                       shadowing_sigma_db=7.41),
                              "shadowing_sigma_db is 0"))

    def test_an_implausible_sigma_is_flagged(self):
        self.assertTrue(says(warnings(shadowing_sigma_db=30.0),
                             "between 2 and 12 dB"))


class TestConfigurationCompleteness(unittest.TestCase):

    def test_no_sensitivity_and_no_chip_is_an_error(self):
        self.assertTrue(errors(chip=None, sensitivity_dbm=None))

    def test_polygon_placement_without_a_polygon_is_an_error(self):
        self.assertTrue(says(errors(placement="polygon"), "polygons_m"))

    def test_a_complete_study_is_valid(self):
        self.assertEqual(errors(), [])


if __name__ == "__main__":
    unittest.main()
