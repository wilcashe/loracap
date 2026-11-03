"""The simulation loop: accounting that must balance, reproducibility, and
the degeneracy onto the analytical bound.

These run real simulations, so they are the slowest tests here. They are kept
small enough to stay under a few seconds in total: the full degeneracy ladder
belongs to `run.py validate`, not to a unit test.
"""
import dataclasses
import math
import random
import unittest

from loracap.core import airtime_ms, run_batch, run_single_sim
from loracap.validation import aloha_der, offered_load
from tests.helpers import config

GUAMAL_SENSI = {7: -126.5, 8: -129.0, 9: -131.5, 10: -134.0}


def site(**over):
    """A small, fast site with eight channels, like a real gateway."""
    base = dict(
        sensitivity_dbm=dict(GUAMAL_SENSI), n_channels=8,
        max_simultaneous_demodulations=8, payload_bytes=32,
        avg_send_interval_ms=15000.0, tx_power_dbm=22.0,
        net_antenna_gain_db=9.0, path_loss_exponent=2.159,
        path_loss_ref_db=130.32, path_loss_ref_distance_m=100.0,
        min_valid_distance_m=30.0)
    base.update(over)
    return config(**base)


# A 1 km square centred on the gateway: a real deployment occupies a bounded
# area well inside the coverage the link budget allows, rather than filling it.
SQUARE_1KM = [[(-500.0, -500.0), (500.0, -500.0), (500.0, 500.0), (-500.0, 500.0)]]


def bounded_site(**over):
    over.setdefault("placement", "polygon")
    over.setdefault("placement_polygons_m", SQUARE_1KM)
    return site(**over)


class TestAccounting(unittest.TestCase):

    def test_losses_and_receipts_add_up_to_transmissions(self):
        """Every packet has exactly one fate. A packet counted twice, or not
        at all, would move DER without any physical cause."""
        for scen in ("SF8", "MULTI", "ADR"):
            r = run_single_sim(site(), 60, 600_000.0, scen, random.Random(3))
            self.assertEqual(
                r["received"] + r["lost_signal"] + r["lost_capacity"]
                + r["collided"], r["transmitted"], scen)

    def test_der_is_a_proportion(self):
        for scen in ("SF8", "MULTI", "ADR"):
            r = run_single_sim(site(), 80, 600_000.0, scen, random.Random(4))
            for key in ("der", "der_classic", "der_fleet"):
                self.assertTrue(0.0 <= r[key] <= 1.0, f"{scen} {key}={r[key]}")

    def test_classic_der_ignores_only_the_demodulator_limit(self):
        """`der_classic` is the literature's definition, counting weak-signal
        and collision losses but not receiver capacity. It can therefore never
        be below `der`."""
        r = run_single_sim(site(), 200, 600_000.0, "SF8", random.Random(5))
        self.assertGreaterEqual(r["der_classic"], r["der"])

    def test_fleet_der_counts_nodes_that_never_transmit(self):
        """REGRESSION. A node with no usable data rate never transmits, so it
        cannot lower the DER of the nodes that did. Before `der_fleet`
        existed, a scenario could post a rising capacity under shadowing
        purely by excluding part of the deployment."""
        cfg = site(shadowing_sigma_db=12.0)
        r = run_single_sim(cfg, 120, 600_000.0, "ADR", random.Random(6))
        self.assertGreater(r["unreachable_nodes"], 0,
                           "fixture no longer excludes anyone; raise sigma")
        self.assertLess(r["der_fleet"], r["der"])

    def test_fleet_and_plain_der_agree_when_nobody_is_excluded(self):
        r = run_single_sim(site(), 60, 600_000.0, "SF8", random.Random(7))
        self.assertEqual(r["unreachable_nodes"], 0)
        self.assertAlmostEqual(r["der_fleet"], r["der"], places=12)

    def test_more_nodes_never_raises_der(self):
        cfg = site()
        ders = [run_batch(cfg, n, 600_000.0, "SF8", 4, 11)["der_mean"]
                for n in (20, 60, 150, 300)]
        for a, b in zip(ders, ders[1:]):
            self.assertLessEqual(b, a + 0.01, f"DER rose: {ders}")


class TestReproducibility(unittest.TestCase):

    def test_same_seed_gives_identical_results(self):
        """Without this a result file cannot be checked against its own
        configuration, which is the whole premise of keeping them together."""
        a = run_single_sim(site(), 50, 600_000.0, "SF8", random.Random(42))
        b = run_single_sim(site(), 50, 600_000.0, "SF8", random.Random(42))
        self.assertEqual(a, b)

    def test_different_seeds_give_different_results(self):
        a = run_single_sim(site(), 50, 600_000.0, "SF8", random.Random(1))
        b = run_single_sim(site(), 50, 600_000.0, "SF8", random.Random(2))
        self.assertNotEqual(a["der"], b["der"])

    def test_batches_are_reproducible(self):
        cfg = site()
        self.assertEqual(run_batch(cfg, 40, 600_000.0, "SF8", 3, 77),
                         run_batch(cfg, 40, 600_000.0, "SF8", 3, 77))


class TestShadowing(unittest.TestCase):

    def test_a_node_keeps_its_shadowing_for_the_whole_run(self):
        """Per-node shadowing is obstruction belonging to where the node is,
        so a node's received power is the same for every packet it sends.

        The assertion is exact rather than statistical, and that is the point.
        An adaptive scenario assigns each node a data rate whose sensitivity
        its own shadowed link already meets, so if the shadowing never
        changes, NO packet can be lost to weak signal. One drawn per packet
        instead would break that immediately.

        An earlier version of this test compared the reported RSSI spread
        instead, and a mutation that moved the draw into the packet loop
        passed it, because the spread is computed from the per-node figure
        and never noticed."""
        for scen in ("MULTI", "ADR"):
            r = run_single_sim(site(shadowing_sigma_db=12.0), 120,
                               1_200_000.0, scen, random.Random(9))
            self.assertEqual(r["lost_signal"], 0,
                             f"{scen}: shadowing is not fixed per node")

    def test_fading_does_cost_packets(self):
        """The counterpart: per-packet variation moves the link between
        transmissions, so an assignment that was safe on average is not safe
        every time. Without this the test above could be satisfied by not
        drawing anything at all."""
        r = run_single_sim(site(shadowing_sigma_db=12.0, fading_sigma_db=6.0),
                           120, 1_200_000.0, "MULTI", random.Random(9))
        self.assertGreater(r["lost_signal"], 0)

    def test_shadowing_widens_the_received_power_spread(self):
        clear = run_single_sim(site(), 100, 600_000.0, "SF8", random.Random(9))
        shadowed = run_single_sim(site(shadowing_sigma_db=8.0), 100,
                                  600_000.0, "SF8", random.Random(9))
        self.assertGreater(shadowed["rssi_spread_db"], clear["rssi_spread_db"])

    def test_fading_does_not_change_the_standing_spread(self):
        """Per-packet fading is reported separately from the deployment's own
        spread, so the spread stays a property of the site."""
        base = run_single_sim(site(), 100, 600_000.0, "SF8", random.Random(10))
        faded = run_single_sim(site(fading_sigma_db=8.0), 100, 600_000.0,
                               "SF8", random.Random(10))
        self.assertAlmostEqual(base["rssi_spread_db"], faded["rssi_spread_db"],
                               places=9)

    def test_zero_sigma_is_exactly_deterministic(self):
        a = run_single_sim(site(shadowing_sigma_db=0.0), 40, 600_000.0,
                           "SF8", random.Random(11))
        b = run_single_sim(site(), 40, 600_000.0, "SF8", random.Random(11))
        self.assertEqual(a["der"], b["der"])


class TestPowerControl(unittest.TestCase):

    def test_adr_collapses_the_received_power_spread(self):
        """The capture effect feeds on the spread of received powers, and
        power control exists to remove it. This is the mechanism by which ADR
        can cost capacity rather than gain it.

        A bounded site is used, not the coverage disc, because the effect
        needs nodes that sit well inside range. Spread over the whole disc,
        most nodes are near its edge with no headroom to give up, so the mean
        power barely moves and the test would prove nothing. A real
        deployment is the bounded case."""
        cfg = bounded_site(adr_margin_db=10.0,
                           tx_power_offsets_db=tuple(range(0, -21, -2)))
        multi = run_single_sim(cfg, 150, 600_000.0, "MULTI", random.Random(12))
        adr = run_single_sim(cfg, 150, 600_000.0, "ADR", random.Random(12))
        self.assertGreater(multi["rssi_spread_db"], 15.0)
        # down to the quantisation step, which is as far as it can collapse
        self.assertLess(adr["rssi_spread_db"], 3.0)
        self.assertLess(adr["mean_tx_power_dbm"], cfg.tx_power_dbm - 3.0)

    def test_multi_leaves_power_at_maximum(self):
        cfg = site()
        r = run_single_sim(cfg, 100, 600_000.0, "MULTI", random.Random(13))
        self.assertEqual(r["mean_tx_power_dbm"], cfg.tx_power_dbm)


class TestDegeneracyOntoTheBound(unittest.TestCase):
    """Pure ALOHA is a lower bound, not a target. What validates the engine is
    that it walks down onto the bound when the mechanisms the theory lacks are
    switched off, one at a time. `run.py validate` does this properly across a
    grid; this is the fast guard."""

    def _degenerate(self, cfg):
        return dataclasses.replace(
            cfg, n_channels=1, max_simultaneous_demodulations=None,
            capture_threshold_db=math.inf, preamble_capture=False)

    def test_degenerate_engine_matches_the_analytical_bound(self):
        cfg = site()
        for n in (30, 100):
            got = run_batch(self._degenerate(cfg), n, 1_800_000.0, "SF8",
                            12, 99)["der_mean"]
            want = aloha_der(cfg, n, 8, n_channels=1)
            self.assertAlmostEqual(
                got, want, delta=0.03,
                msg=f"N={n}: degenerate {got:.4f} against ALOHA {want:.4f}")

    def test_each_mechanism_only_helps(self):
        """Capture and the preamble allowance both save packets, so switching
        either on cannot lower DER."""
        cfg = site(n_channels=1, max_simultaneous_demodulations=None)
        bare = dataclasses.replace(cfg, capture_threshold_db=math.inf,
                                   preamble_capture=False)
        with_preamble = dataclasses.replace(bare, preamble_capture=True)
        with_both = dataclasses.replace(with_preamble, capture_threshold_db=6.0)
        a, b, c = (run_batch(x, 100, 1_800_000.0, "SF8", 10, 5)["der_mean"]
                   for x in (bare, with_preamble, with_both))
        self.assertLessEqual(a, b + 0.005)
        self.assertLessEqual(b, c + 0.005)

    def test_offered_load_divides_across_channels(self):
        cfg = site()
        self.assertAlmostEqual(
            offered_load(cfg, 80, 8, n_channels=1),
            80 * airtime_ms(cfg, 8) / cfg.avg_send_interval_ms, places=12)
        self.assertAlmostEqual(offered_load(cfg, 80, 8, n_channels=8) * 8,
                               offered_load(cfg, 80, 8, n_channels=1),
                               places=12)


if __name__ == "__main__":
    unittest.main()
