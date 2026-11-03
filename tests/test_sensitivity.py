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


if __name__ == "__main__":
    unittest.main()
