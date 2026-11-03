"""Transmit energy, energy per extracted message, and service life.

Energy is the one figure here that depends on the node's radio rather than
the gateway's, so most of these are about refusing to produce a number that
has no basis.
"""
import random
import unittest

from loracap import analysis, presets, study as study_mod
from loracap.core import airtime_ms, run_single_sim
from tests.helpers import config, study

SX1272_TABLE = presets.TX_CURRENT_MA["SX1272"]


def powered(**over):
    over.setdefault("tx_current_ma", dict(SX1272_TABLE))
    over.setdefault("supply_voltage_v", 3.0)
    over.setdefault("sensitivity_dbm",
                    {7: -126.5, 8: -129.0, 9: -131.5, 10: -134.0})
    over.setdefault("n_channels", 8)
    over.setdefault("avg_send_interval_ms", 15000.0)
    over.setdefault("tx_power_dbm", 14.0)
    return config(**over)


class TestCurrentTable(unittest.TestCase):

    def test_power_amplifier_step_is_present(self):
        """The jump from 14 to 15 dBm nearly doubles the draw, which is why
        values outside the table cannot be interpolated from those inside."""
        self.assertEqual(SX1272_TABLE[14], 44)
        self.assertEqual(SX1272_TABLE[15], 82)

    def test_lookup_rounds_to_the_nearest_decibel(self):
        self.assertEqual(presets.tx_current_ma("SX1272", 13.6), 44.0)

    def test_lookup_refuses_outside_the_table(self):
        with self.assertRaises(KeyError):
            presets.tx_current_ma("SX1272", 30.0)
        with self.assertRaises(KeyError):
            presets.tx_current_ma("SX1272", -10.0)

    def test_unknown_radio_raises(self):
        with self.assertRaises(KeyError):
            presets.tx_current_ma("STM32WL", 14.0)

    def test_every_table_has_a_source(self):
        self.assertEqual(set(presets.TX_CURRENT_MA),
                         set(presets.TX_CURRENT_SOURCE))


class TestEnergyIsOptional(unittest.TestCase):

    def test_no_table_means_no_number(self):
        """A guessed current produces a battery figure that reads as
        authoritative and is fiction, so the default is silence."""
        r = run_single_sim(config(), 20, 600_000.0, "SF8", random.Random(1))
        self.assertIsNone(r["tx_energy_j"])
        self.assertIsNone(r["nec_j_per_message"])

    def test_a_table_produces_one(self):
        r = run_single_sim(powered(), 20, 600_000.0, "SF8", random.Random(1))
        self.assertGreater(r["tx_energy_j"], 0.0)
        self.assertGreater(r["nec_j_per_message"], 0.0)


class TestEnergyArithmetic(unittest.TestCase):

    def test_energy_equals_airtime_times_current_times_voltage(self):
        """Checked against the closed form rather than against itself: the
        packets are all at one spreading factor and one power, so the total
        is exactly computable."""
        cfg = powered()
        r = run_single_sim(cfg, 15, 600_000.0, "SF8", random.Random(2))
        expected = (r["transmitted"] * airtime_ms(cfg, 8)
                    * SX1272_TABLE[14] * 3.0 / 1e6)
        self.assertAlmostEqual(r["tx_energy_j"], expected, places=9)

    def test_collided_packets_are_still_paid_for(self):
        """A node spends the same whether its packet survives, so energy per
        EXTRACTED message is the figure worth reporting."""
        cfg = powered()
        light = run_single_sim(cfg, 10, 600_000.0, "SF8", random.Random(3))
        heavy = run_single_sim(cfg, 300, 600_000.0, "SF8", random.Random(3))
        self.assertLess(light["der"], 1.01)
        self.assertGreater(light["der"], heavy["der"])
        # per transmission the cost is identical, per extracted message it is not
        self.assertGreater(heavy["nec_j_per_message"],
                           light["nec_j_per_message"])

    def test_voltage_scales_energy_linearly(self):
        a = run_single_sim(powered(supply_voltage_v=3.0), 20, 600_000.0,
                           "SF8", random.Random(4))
        b = run_single_sim(powered(supply_voltage_v=6.0), 20, 600_000.0,
                           "SF8", random.Random(4))
        self.assertAlmostEqual(b["tx_energy_j"], 2 * a["tx_energy_j"], places=9)

    def test_a_slower_data_rate_costs_more(self):
        cfg = powered()
        fast = run_single_sim(cfg, 20, 600_000.0, "SF7", random.Random(5))
        slow = run_single_sim(cfg, 20, 600_000.0, "SF10", random.Random(5))
        self.assertGreater(slow["nec_j_per_message"], fast["nec_j_per_message"])


class TestValidation(unittest.TestCase):

    def test_transmit_power_outside_the_table_is_an_error(self):
        """The worked example transmits at 22 dBm, beyond the SX1272 table,
        and its node is a different radio entirely."""
        errors, _w, _i = study_mod.validate(
            study(radio="SX1272", tx_power_dbm=22.0))
        self.assertTrue(any("cannot be interpolated" in e for e in errors))

    def test_a_power_inside_the_table_passes(self):
        errors, _w, _i = study_mod.validate(
            study(radio="SX1272", tx_power_dbm=14.0, tx_antenna_gain_db=0.0,
                  rx_antenna_gain_db=0.0))
        self.assertEqual(errors, [])

    def test_unknown_radio_is_an_error(self):
        errors, _w, _i = study_mod.validate(study(radio="STM32WL"))
        self.assertTrue(any("No transmit current table" in e for e in errors))

    def test_sleep_current_without_a_radio_is_useless_and_says_so(self):
        _e, warnings, _i = study_mod.validate(
            study(sleep_current_ua=2.0, battery_capacity_mah=2400.0))
        self.assertTrue(any("no energy figure can be produced" in w
                            for w in warnings))

    def test_missing_sleep_current_declines_to_give_a_life(self):
        _e, _w, info = study_mod.validate(
            study(radio="SX1272", tx_power_dbm=14.0, tx_antenna_gain_db=0.0,
                  rx_antenna_gain_db=0.0))
        self.assertTrue(any("battery life is not" in i for i in info))



class TestServiceLife(unittest.TestCase):

    def _row(self, energy_j, n_nodes=50):
        return {"n_nodes": n_nodes, "tx_energy_j_mean": energy_j}

    def test_returns_none_without_the_inputs(self):
        s = study(radio="SX1272", tx_power_dbm=14.0, tx_antenna_gain_db=0.0,
                  rx_antenna_gain_db=0.0)
        self.assertIsNone(analysis.service_life(self._row(100.0), s))
        self.assertIsNone(analysis.service_life(self._row(None), s))

    def test_sums_transmit_and_sleep_current(self):
        s = study(radio="SX1272", tx_power_dbm=14.0, tx_antenna_gain_db=0.0,
                  rx_antenna_gain_db=0.0, sleep_current_ua=2.0,
                  battery_capacity_mah=2400.0, sim_time_s=1000.0)
        life = analysis.service_life(self._row(30.0, n_nodes=10), s)
        # 3 J per node over 1000 s at 3 V is 1 mA of transmit current
        self.assertAlmostEqual(life["tx_current_ma"], 1.0, places=9)
        self.assertAlmostEqual(life["sleep_current_ma"], 0.002, places=9)
        self.assertAlmostEqual(life["average_current_ma"], 1.002, places=9)
        self.assertAlmostEqual(life["service_life_days"],
                               2400.0 / 1.002 / 24.0, places=6)

    def test_reports_which_term_dominates_rather_than_assuming(self):
        """Not the same for every deployment: at a short reporting interval
        transmitting is nearly all of it, at an interval of hours the sleep
        draw overtakes it."""
        s = study(radio="SX1272", tx_power_dbm=14.0, tx_antenna_gain_db=0.0,
                  rx_antenna_gain_db=0.0, sleep_current_ua=2.0,
                  battery_capacity_mah=2400.0, sim_time_s=1000.0)
        busy = analysis.service_life(self._row(30.0, n_nodes=10), s)
        idle = analysis.service_life(self._row(0.003, n_nodes=10), s)
        self.assertGreater(busy["transmit_share"], 0.99)
        self.assertLess(idle["transmit_share"], 0.1)


if __name__ == "__main__":
    unittest.main()
