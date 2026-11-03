"""Airtime, path loss and the inverses, against external oracles where they
exist. These are the numbers everything else is built on, so they are pinned
to published figures rather than to whatever the code happens to return."""
import math
import unittest

from loracap.core import (
    airtime_ms, max_distance_m, path_loss_db, ref_loss_for_range, rssi_dbm,
)
from tests.helpers import config


class TestAirtime(unittest.TestCase):

    def test_matches_published_figure(self):
        """20 B at SF12, 125 kHz, CR 4/8 is 1712.13 ms.

        Published in Voigt, Bor, Roedig and Alonso, "Mitigating Inter-network
        Interference in LoRa Networks" (2016), section 4, for configuration
        SN1. An external oracle for the whole airtime formula, including the
        low-data-rate-optimise flag, in one number."""
        cfg = config(payload_bytes=20, coding_rate=4, bw_khz=125)
        self.assertAlmostEqual(airtime_ms(cfg, 12), 1712.13, places=2)

    def test_sn3_coding_rate(self):
        """SN1 and SN3 differ only in coding rate, so this isolates it."""
        cfg = config(payload_bytes=20, coding_rate=1, bw_khz=125)
        self.assertAlmostEqual(airtime_ms(cfg, 12), 1318.91, places=2)

    def test_doubling_spreading_factor_roughly_doubles_airtime(self):
        cfg = config()
        for sf in (7, 8, 9):
            ratio = airtime_ms(cfg, sf + 1) / airtime_ms(cfg, sf)
            self.assertTrue(1.8 < ratio < 2.2, f"SF{sf}->SF{sf+1} ratio {ratio}")

    def test_low_data_rate_optimise_applies_only_at_125_khz(self):
        """The DE flag is set for SF11 and SF12 at 125 kHz and nowhere else.

        The payload matters for detecting it, which is worth knowing. At 20
        bytes the ceiling in the symbol-count formula rounds both the DE and
        the no-DE case to the same number of symbols, so the flag is
        invisible and the 125/250 ratio is exactly 2, the symbol time alone.
        At 30 bytes the two land either side of a ceiling boundary and the
        flag shows up. The published 1712.13 ms oracle above uses 20 bytes,
        so it does not pin this either, which is why the test exists
        separately."""
        wide = dict(payload_bytes=30)
        at125 = airtime_ms(config(bw_khz=125, **wide), 12)
        at250 = airtime_ms(config(bw_khz=250, **wide), 12)
        self.assertAlmostEqual(at125 / at250, 2.2210, places=3)
        # SF10 never gets the flag, so there the ratio is the symbol time only
        self.assertAlmostEqual(
            airtime_ms(config(bw_khz=125, **wide), 10)
            / airtime_ms(config(bw_khz=250, **wide), 10), 2.0, places=9)

    def test_airtime_grows_with_payload(self):
        cfg_small, cfg_big = config(payload_bytes=1), config(payload_bytes=200)
        self.assertLess(airtime_ms(cfg_small, 7), airtime_ms(cfg_big, 7))


class TestPathLoss(unittest.TestCase):

    def test_reference_distance_gives_reference_loss(self):
        cfg = config()
        self.assertAlmostEqual(
            path_loss_db(cfg, cfg.path_loss_ref_distance_m),
            cfg.path_loss_ref_db, places=9)

    def test_decade_of_distance_costs_ten_gamma(self):
        cfg = config()
        d = cfg.path_loss_ref_distance_m
        self.assertAlmostEqual(
            path_loss_db(cfg, 10 * d) - path_loss_db(cfg, d),
            10 * cfg.path_loss_exponent, places=9)

    def test_clamps_at_validity_floor_not_at_d0(self):
        """The floor is a property of the data the model was fitted to. The
        reference distance is a parameterisation choice. Clamping at d0 would
        silently flatten every node inside it, which at d0 = 100 m would be
        most of a small site."""
        cfg = config(min_valid_distance_m=30.0, path_loss_ref_distance_m=100.0)
        self.assertEqual(path_loss_db(cfg, 5.0), path_loss_db(cfg, 30.0))
        self.assertLess(path_loss_db(cfg, 50.0), path_loss_db(cfg, 100.0))

    def test_max_distance_inverts_path_loss_in_base_ten(self):
        """LoRaSim's own maxDist inverts in base e while computing the loss in
        base 10, which at its default parameters returns 99 m where the model
        gives 360 m. This asserts the consistent inverse."""
        cfg = config()
        for sens in (-120.0, -130.0, -137.0):
            d = max_distance_m(cfg, sens)
            self.assertAlmostEqual(rssi_dbm(cfg, d), sens, places=6)

    def test_ref_loss_for_range_is_the_inverse_of_max_distance(self):
        for exponent in (2.0, 2.159, 3.4):
            loss = ref_loss_for_range(22.0, 9.0, -134.0, exponent, 958.0, 100.0)
            cfg = config(tx_power_dbm=22.0, net_antenna_gain_db=9.0,
                         path_loss_exponent=exponent, path_loss_ref_db=loss,
                         path_loss_ref_distance_m=100.0)
            self.assertAlmostEqual(max_distance_m(cfg, -134.0), 958.0, places=6)

    def test_ref_loss_rejects_impossible_inputs(self):
        with self.assertRaises(ValueError):
            ref_loss_for_range(14, 0, -137, 2.0, 0.0)
        with self.assertRaises(ValueError):
            ref_loss_for_range(14, 0, -137, 0.0, 100.0)


class TestReceivedPower(unittest.TestCase):

    def test_transmit_power_moves_rssi_one_for_one(self):
        cfg = config()
        self.assertAlmostEqual(
            rssi_dbm(cfg, 200.0, tx_power_dbm=cfg.tx_power_dbm - 6) + 6,
            rssi_dbm(cfg, 200.0), places=9)

    def test_shadowing_offset_is_additive(self):
        cfg = config()
        self.assertAlmostEqual(
            rssi_dbm(cfg, 200.0, shadowing_db=-7.0) + 7.0,
            rssi_dbm(cfg, 200.0), places=9)

    def test_rssi_is_deterministic_without_sigma(self):
        """Two calls at the same distance must agree exactly. The random draws
        belong to the caller that owns their lifetime, never to this
        function, so that a node's shadowing cannot be redrawn by accident."""
        cfg = config()
        self.assertEqual(rssi_dbm(cfg, 137.0), rssi_dbm(cfg, 137.0))


if __name__ == "__main__":
    unittest.main()
