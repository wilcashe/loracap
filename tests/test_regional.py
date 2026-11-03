"""Regional data rates, payload ceilings and transmit power offsets.

Most of these exist because an extraction was once wrong in a way that
produced plausible-looking numbers. Those cases are marked.
"""
import unittest

from loracap import presets


class TestDataRateTables(unittest.TestCase):

    def test_us915_uplink_data_rates(self):
        """Checked against the published Regional Parameters, independently of
        the library the table was extracted from."""
        self.assertEqual(presets.DATA_RATES["US915"], {
            0: (10, 125), 1: (9, 125), 2: (8, 125), 3: (7, 125), 4: (8, 500),
        })
        self.assertEqual(presets.MAX_APP_PAYLOAD_BYTES["US915"][None],
                         {0: 11, 1: 53, 2: 125, 3: 222, 4: 222})

    def test_eu868_uses_the_repeater_compatible_ceilings(self):
        """REGRESSION. The first extraction returned 242 bytes for DR4 to DR6
        instead of 222, because one file in the source library spells the
        parameter `repeatedCompatible`, with a typo, and the extractor matched
        `repeaterCompatible` and so fell through to the non-repeater table.
        Nothing about the output looked wrong. Only a second source caught
        it."""
        self.assertEqual(presets.MAX_APP_PAYLOAD_BYTES["EU868"][None],
                         {0: 51, 1: 51, 2: 51, 3: 115, 4: 222, 5: 222, 6: 222})

    def test_every_plan_has_a_ceiling_for_every_data_rate(self):
        for region, drs in presets.DATA_RATES.items():
            for dwell, ceilings in presets.MAX_APP_PAYLOAD_BYTES[region].items():
                self.assertEqual(
                    set(ceilings), set(drs),
                    f"{region} dwell={dwell}: data rates and ceilings disagree")

    def test_zero_ceiling_is_a_value_not_a_gap(self):
        """CN470 DR0 carries no application payload at all, and neither does
        SF12 or SF11 under a 400 ms dwell limit. Collapsing that into
        'unknown' would let an impossible configuration through."""
        self.assertEqual(presets.MAX_APP_PAYLOAD_BYTES["CN470"][None][0], 0)
        self.assertEqual(presets.MAX_APP_PAYLOAD_BYTES["AU915"][400][0], 0)
        self.assertEqual(presets.MAX_APP_PAYLOAD_BYTES["AS923"][400][1], 0)


class TestDataRateLookup(unittest.TestCase):

    def test_bandwidth_is_part_of_the_key(self):
        """SF8 appears twice in US915, at DR2 and DR4, so the spreading factor
        alone does not identify a data rate."""
        self.assertEqual(presets.data_rate_for("US915", 8, 125), (2, 125))
        self.assertEqual(presets.data_rate_for("US915", 8, 500), (4, 222))

    def test_combination_that_is_not_a_data_rate_returns_none(self):
        self.assertIsNone(presets.data_rate_for("US915", 7, 500))
        self.assertIsNone(presets.data_rate_for("US915", 12, 125))

    def test_unknown_region_returns_none_rather_than_raising(self):
        self.assertIsNone(presets.region_data_rates("XX999"))
        self.assertIsNone(presets.data_rate_for("XX999", 8, 125))

    def test_dwell_time_plans_refuse_to_guess(self):
        """AU915 at DR2 carries 51 bytes with no dwell limit and 11 with one.
        Returning either without being told which would be wrong half the
        time, so an unstated dwell time yields no ceiling at all."""
        self.assertTrue(presets.needs_dwell_time("AU915"))
        dr, ceiling = presets.data_rate_for("AU915", 10, 125, None)
        self.assertEqual(dr, 2)
        self.assertIsNone(ceiling)
        self.assertEqual(presets.data_rate_for("AU915", 10, 125, 0), (2, 51))
        self.assertEqual(presets.data_rate_for("AU915", 10, 125, 400), (2, 11))

    def test_plans_without_dwell_dependence_ignore_the_argument(self):
        self.assertFalse(presets.needs_dwell_time("US915"))
        self.assertEqual(presets.data_rate_for("US915", 10, 125, None),
                         presets.data_rate_for("US915", 10, 125, 400))


class TestTransmitPowerOffsets(unittest.TestCase):

    def test_every_plan_steps_in_two_decibels(self):
        """REGRESSION. The first extraction swept the index comments on each
        line into the list, producing sequences like (0, 0, -2, 1, -4, 2) for
        AU915, AS923 and CN470. It was caught only because the step sizes
        stopped being uniform, which is what this asserts."""
        for region, offsets in presets.TX_POWER_OFFSETS_DB.items():
            self.assertEqual(offsets[0], 0, f"{region} must start at 0 dB")
            steps = {offsets[i] - offsets[i + 1] for i in range(len(offsets) - 1)}
            self.assertEqual(steps, {2}, f"{region} steps are {sorted(steps)}")

    def test_offsets_are_monotonically_decreasing(self):
        for region, offsets in presets.TX_POWER_OFFSETS_DB.items():
            self.assertEqual(list(offsets), sorted(offsets, reverse=True), region)

    def test_every_plan_with_data_rates_has_power_offsets(self):
        self.assertEqual(set(presets.DATA_RATES), set(presets.TX_POWER_OFFSETS_DB))

    def test_lookup_of_unknown_region(self):
        self.assertIsNone(presets.region_tx_power_offsets("XX999"))


def _ladder(deepest):
    return tuple(range(0, deepest - 1, -2))


class TestAgainstRP002_1_0_5(unittest.TestCase):
    """Every regional table, typed from the LoRa Alliance document itself
    (RP002-1.0.5, October 2025) rather than from the library the tables were
    first extracted from. Until this check, six of the eight plans rested on
    that library alone.

    LoRa data rates only. FSK, LR-FHSS and the OPTIONAL SF6/SF5 rates are
    outside the model, see `test_sf6_and_sf5_are_deliberately_absent`."""

    # Tables 10, 19, 39, 50, 67, 80, 91, 102: DR -> (SF, kHz)
    DATA_RATES = {
        "EU868": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125),
                  4: (8, 125), 5: (7, 125), 6: (7, 250)},
        "US915": {0: (10, 125), 1: (9, 125), 2: (8, 125), 3: (7, 125),
                  4: (8, 500)},
        "AU915": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125),
                  4: (8, 125), 5: (7, 125), 6: (8, 500)},
        "CN470": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125),
                  4: (8, 125), 5: (7, 125), 6: (7, 500)},
        "AS923": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125),
                  4: (8, 125), 5: (7, 125), 6: (7, 250)},
        "KR920": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125),
                  4: (8, 125), 5: (7, 125)},
        # DR6 was removed from IN865 in RP002-1.0.5.
        "IN865": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125),
                  4: (8, 125), 5: (7, 125)},
        "RU864": {0: (12, 125), 1: (11, 125), 2: (10, 125), 3: (9, 125),
                  4: (8, 125), 5: (7, 125), 6: (7, 250)},
    }

    # Tables 15, 24, 44, 54, 72, 85, 96, 107, repeater compatible, column N.
    # The document's N/A is a ceiling of zero here.
    CEILINGS = {
        "EU868": {None: {0: 51, 1: 51, 2: 51, 3: 115, 4: 222, 5: 222, 6: 222}},
        "US915": {None: {0: 11, 1: 53, 2: 125, 3: 222, 4: 222}},
        "AU915": {0: {0: 51, 1: 51, 2: 51, 3: 115, 4: 222, 5: 222, 6: 222},
                  400: {0: 0, 1: 0, 2: 11, 3: 53, 4: 125, 5: 222, 6: 222}},
        "CN470": {None: {0: 0, 1: 23, 2: 86, 3: 184, 4: 222, 5: 222, 6: 222}},
        "AS923": {0: {0: 51, 1: 51, 2: 115, 3: 115, 4: 222, 5: 222, 6: 222},
                  400: {0: 0, 1: 0, 2: 11, 3: 53, 4: 125, 5: 222, 6: 222}},
        "KR920": {None: {0: 51, 1: 51, 2: 51, 3: 115, 4: 222, 5: 222}},
        "IN865": {None: {0: 51, 1: 51, 2: 51, 3: 115, 4: 222, 5: 222}},
        "RU864": {None: {0: 51, 1: 51, 2: 51, 3: 115, 4: 222, 5: 222, 6: 222}},
    }

    # Tables 13, 22, 42, 50, 70, 83, 94, 105. US915 is the full 30 dBm
    # ladder, cut per node at the 2 dBm floor (see the test class below).
    OFFSETS = {
        "EU868": _ladder(-14), "US915": _ladder(-28), "AU915": _ladder(-28),
        "CN470": _ladder(-14), "AS923": _ladder(-14), "KR920": _ladder(-14),
        "IN865": _ladder(-28), "RU864": _ladder(-14),
    }

    def test_data_rates(self):
        self.assertEqual(presets.DATA_RATES, self.DATA_RATES)

    def test_repeater_compatible_ceilings(self):
        self.assertEqual(presets.MAX_APP_PAYLOAD_BYTES, self.CEILINGS)

    def test_power_offsets(self):
        self.assertEqual(presets.TX_POWER_OFFSETS_DB, self.OFFSETS)

    def test_in865_reaches_minus_28_db(self):
        """REGRESSION. The library the tables came from stopped IN865 at
        -20 dB. RP002-1.0.5 Table 94 gives 'Max EIRP - 2*TXPower' for indices
        1 to 14, so -28 dB. Only the check against the document caught it."""
        self.assertEqual(presets.region_tx_power_offsets("IN865", 14.0)[-1], -28)

    def test_sf6_and_sf5_are_deliberately_absent(self):
        """RP002-1.0.5 added SF6 and SF5 at 125 kHz as OPTIONAL uplink data
        rates. They are left out on purpose: the gateway chips tabulated here
        cannot demodulate them, so there is no sourced sensitivity. A study
        asking for them must be refused, not quietly simulated."""
        for region in presets.DATA_RATES:
            for sf in (5, 6):
                self.assertIsNone(presets.data_rate_for(region, sf, 125),
                                  f"{region} SF{sf}")


class TestUS915AbsolutePowerFloor(unittest.TestCase):
    """RP002-1.0.5 Table 22 lists absolute conducted levels for US915, 30 dBm
    down to 2 dBm. Read as absolute, the ladder a node can use depends on its
    own power, so a fixed table would be right at one power only."""

    def test_the_ladder_stops_at_two_dbm(self):
        for power, deepest in ((30.0, -28), (22.0, -20), (14.0, -12),
                               (21.0, -18)):
            with self.subTest(power=power):
                offsets = presets.region_tx_power_offsets("US915", power)
                self.assertEqual(offsets, _ladder(deepest))
                self.assertGreaterEqual(power + offsets[-1], 2.0)

    def test_the_worked_example_is_unchanged(self):
        """The IoT4Cows collar transmits at 22 dBm, where the absolute reading
        gives exactly the -20 dB the table held before this check, so no
        quoted ADR result moves."""
        from loracap import study as study_mod
        s = study_mod.load_study("iot4cows")
        self.assertEqual(s.resolved_tx_power_offsets(), _ladder(-20))

    def test_relative_plans_ignore_the_node_power(self):
        self.assertEqual(presets.region_tx_power_offsets("AU915", 14.0),
                         _ladder(-28))


class TestFrequencies(unittest.TestCase):

    def test_every_plan_has_an_uplink_frequency(self):
        self.assertEqual(set(presets.REGION_UPLINK_MHZ), set(presets.DATA_RATES))

    def test_frequencies_are_in_their_named_bands(self):
        """The plan names carry the band, so a transposed digit shows up."""
        for region, mhz in presets.REGION_UPLINK_MHZ.items():
            expected = int(region[-3:])          # US915 -> 915, CN470 -> 470
            self.assertLess(abs(mhz - expected), 15,
                            f"{region} at {mhz} MHz is far from {expected}")


if __name__ == "__main__":
    unittest.main()
