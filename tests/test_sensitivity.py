"""Receiver sensitivity: what is tabulated, what is derived, and how far the
derivation sits from measurement."""
import math
import unittest

from loracap import presets


class TestTables(unittest.TestCase):

    def test_tables_are_indexed_by_bandwidth(self):
        """LoRaWAN is not 125 kHz only, so a table keyed by spreading factor
        alone cannot describe EU868 DR6 or US915 DR4."""
        for chip, by_bw in presets.SENSITIVITY_DBM.items():
            self.assertTrue(by_bw, f"{chip} has no bandwidths")
            for bw, table in by_bw.items():
                self.assertIn(bw, (125, 250, 500), f"{chip} at {bw} kHz")
                self.assertTrue(table, f"{chip} at {bw} kHz is empty")

    def test_gateway_chips_improve_with_spreading_factor(self):
        """A higher spreading factor should be more sensitive. Bor et al.'s
        measured node radio breaks this at SF12, which is their result and is
        why only the gateway tables are checked here."""
        for chip in ("SX1301", "SX1308"):
            table = presets.SENSITIVITY_DBM[chip][125]
            ordered = sorted(table)
            for a, b in zip(ordered, ordered[1:]):
                self.assertLess(table[b], table[a], f"{chip} SF{a} vs SF{b}")

    def test_bor_table_covers_three_bandwidths(self):
        by_bw = presets.SENSITIVITY_DBM["XRange_SX1272"]
        self.assertEqual(sorted(by_bw), [125, 250, 500])
        self.assertEqual(by_bw[125][7], -126.50)
        self.assertEqual(by_bw[500][7], -120.75)


class TestLookup(unittest.TestCase):

    def test_tabulated_bandwidth_is_returned_unchanged(self):
        table, derived = presets.sensitivity_for("SX1308", (7, 8), 125)
        self.assertIsNone(derived)
        self.assertEqual(table, {7: -126.5, 8: -129.0})

    def test_missing_bandwidth_is_derived_and_declared(self):
        table, derived = presets.sensitivity_for("SX1308", (8,), 500)
        self.assertEqual(derived, 125)
        self.assertAlmostEqual(table[8], -129.0 + 10 * math.log10(500 / 125),
                               places=9)

    def test_derivation_uses_the_nearest_tabulated_bandwidth(self):
        """XRange has all three, so a request at 500 is tabulated rather than
        derived from 125."""
        _table, derived = presets.sensitivity_for("XRange_SX1272", (7,), 500)
        self.assertIsNone(derived)

    def test_unknown_chip_raises_rather_than_guessing(self):
        with self.assertRaises(KeyError):
            presets.sensitivity_for("SX9999", (7,), 125)

    def test_missing_spreading_factor_raises(self):
        with self.assertRaises(KeyError):
            presets.sensitivity_for("SX1308", (6,), 125)


class TestDerivationAgainstMeasurement(unittest.TestCase):
    """The derivation is `10*log10(BW2/BW1)`, which both the SX1301 datasheet
    and Bor et al. state. Bor et al. also publish all three bandwidths
    measured, so the derivation can be checked rather than trusted."""

    def _errors(self, bw):
        by_bw = presets.SENSITIVITY_DBM["XRange_SX1272"]
        shift = 10 * math.log10(bw / 125)
        return [by_bw[bw][sf] - (by_bw[125][sf] + shift) for sf in by_bw[125]]

    def test_derivation_never_overstates_sensitivity(self):
        """Every measured value is better than the derivation says. That makes
        a derived figure understate range, which is the safe direction to be
        wrong in for a coverage claim."""
        for bw in (250, 500):
            for err in self._errors(bw):
                self.assertLessEqual(err, 0.0, f"{bw} kHz error {err:+.2f} dB")

    def test_derivation_error_stays_within_the_documented_bound(self):
        """Documented as up to 5 dB. If a table changes and this breaks, the
        documented bound has to change with it."""
        self.assertLess(max(abs(e) for e in self._errors(250)), 3.0)
        self.assertLess(max(abs(e) for e in self._errors(500)), 5.1)


# Semtech SX1301 datasheet V2.4 (June 2017), page 29, typed from the rendered
# page rather than copied from presets, so the two sources stay independent.
SX1301_TABLE_13_250KHZ = {7: -123.5, 8: -126.0, 9: -128.5, 10: -131.0, 11: -133.5, 12: -136.5}
SX1301_TABLE_14_500KHZ = {7: -120.5, 8: -123.0, 9: -125.5, 10: -128.0, 11: -130.5, 12: -133.5}


class TestSX1301WideBandwidths(unittest.TestCase):
    """Design item 28: the SX1301's own 250 and 500 kHz tables."""

    def test_tables_13_and_14_as_printed(self):
        by_bw = presets.SENSITIVITY_DBM["SX1301"]
        self.assertEqual(by_bw[250], SX1301_TABLE_13_250KHZ)
        self.assertEqual(by_bw[500], SX1301_TABLE_14_500KHZ)

    def test_tabulated_rather_than_derived(self):
        for bw, printed in ((250, SX1301_TABLE_13_250KHZ), (500, SX1301_TABLE_14_500KHZ)):
            table, derived = presets.sensitivity_for("SX1301", tuple(printed), bw)
            self.assertIsNone(derived, f"{bw} kHz")
            self.assertEqual(table, printed)

    def test_they_agree_with_the_derivation(self):
        """The code says the two columns equal the 125 kHz one plus
        10*log10(BW/125) to the datasheet's half decibel, so they confirm the
        derivation for this chip rather than test it. Pinned so the statement
        cannot outlive a change to either table."""
        by_bw = presets.SENSITIVITY_DBM["SX1301"]
        for bw in (250, 500):
            shift = 10 * math.log10(bw / 125)
            for sf, value in by_bw[bw].items():
                self.assertAlmostEqual(value, by_bw[125][sf] + shift, delta=0.03,
                                       msg=f"SF{sf} at {bw} kHz")

    def test_table_12_kept_at_sf7(self):
        """Table 11 gives -126 dBm at SF7 on IF0 to 7, Table 12 -126.5. Table
        12 was kept on 2026-11-19, since the other moves published results."""
        self.assertEqual(presets.SENSITIVITY_DBM["SX1301"][125][7], -126.5)

    def test_the_sx1308_is_not_given_them(self):
        """The SX1308 reuses the SX1301's 125 kHz column as a documented
        assumption. Nothing extended that assumption to the wide columns."""
        _table, derived = presets.sensitivity_for("SX1308", (8,), 500)
        self.assertEqual(derived, 125)


class TestTheWideChannel(unittest.TestCase):
    """Above 125 kHz a concentrator receives on IF8 only: one channel, one
    configured data rate (SX1301 datasheet V2.4, section 3.6.2)."""

    def _study(self, **kw):
        from tests import helpers
        return helpers.study(**kw)

    def _check(self, **kw):
        from loracap.study import validate
        return validate(self._study(**kw))[0]

    def test_one_channel_by_default(self):
        for chip in ("SX1301", "SX1308"):
            for bw in (250, 500):
                s = self._study(chip=chip, bw_khz=bw)
                self.assertEqual(s.resolved_n_channels(), 1, (chip, bw))
                self.assertEqual(s.to_sim_config().n_channels, 1, (chip, bw))

    def test_eight_channels_at_125_khz(self):
        for chip in ("SX1301", "SX1308"):
            self.assertEqual(self._study(chip=chip, bw_khz=125).resolved_n_channels(), 8)

    def test_a_fixed_scenario_on_the_wide_channel_is_valid(self):
        self.assertEqual(self._check(chip="SX1301", bw_khz=500, scenarios=("SF8",)), [])
        self.assertEqual(self._check(chip="SX1301", bw_khz=500, scenarios=("SF8",),
                                     n_channels=1), [])

    def test_more_channels_are_refused(self):
        errors = self._check(chip="SX1301", bw_khz=500, scenarios=("SF8",), n_channels=8)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("n_channels = 8", errors[0])
        self.assertIn("only on IF8", errors[0])

    def test_adaptive_scenarios_are_refused(self):
        errors = self._check(chip="SX1301", bw_khz=500, scenarios=("SF8", "MULTI", "ADR"))
        self.assertEqual(len(errors), 2, errors)
        for scen, err in zip(("MULTI", "ADR"), errors):
            self.assertIn(f"Scenario {scen} ", err)
            self.assertIn("only on IF8", err)

    def test_nothing_changes_at_125_khz(self):
        self.assertEqual(self._check(chip="SX1301", bw_khz=125, n_channels=8,
                                     scenarios=("SF8", "MULTI", "ADR")), [])

    def test_a_node_radio_is_not_held_to_it(self):
        """The rule belongs to the concentrators. Bor et al.'s node radio,
        used as a receiver in the reproductions, keeps the channels it is
        given."""
        s = self._study(chip="XRange_SX1272", bw_khz=500, n_channels=8,
                        scenarios=("SF8", "MULTI"))
        from loracap.study import validate
        self.assertEqual(s.resolved_n_channels(), 8)
        self.assertFalse([e for e in validate(s)[0] if "IF8" in e])


if __name__ == "__main__":
    unittest.main()
