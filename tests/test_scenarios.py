"""Scenario behaviour: fixed data rate, ideal assignment and steady-state ADR.

The ADR tests here are mostly guards against a modelling error that treated
the link margin as an admission test. It went unnoticed until shadowing was
added, and it made ADR look better the worse propagation got.
"""
import dataclasses
import unittest

from loracap.core import (
    choose_adr, choose_sf_adaptive, parse_scenario, scenario_is_adr,
)
from tests.helpers import GUAMAL, config

SFS = (7, 8, 9, 10)
GUAMAL_SENSI = {7: -126.5, 8: -129.0, 9: -131.5, 10: -134.0}


def guamal(**over):
    return config(sensitivity_dbm=dict(GUAMAL_SENSI), n_channels=8,
                  avg_send_interval_ms=15000.0, payload_bytes=32,
                  **{**GUAMAL, **over})


class TestScenarioParsing(unittest.TestCase):

    def test_fixed_spreading_factor(self):
        self.assertEqual(parse_scenario("SF9", guamal()), (9, (9,)))

    def test_adaptive_scenarios_share_a_shape(self):
        """MULTI and ADR both assign per node, so callers that only want the
        spreading factors in play need not distinguish them."""
        for name in ("MULTI", "ADR"):
            fixed, opts = parse_scenario(name, guamal())
            self.assertIsNone(fixed)
            self.assertEqual(opts, SFS)

    def test_only_adr_is_adr(self):
        self.assertTrue(scenario_is_adr("ADR"))
        self.assertFalse(scenario_is_adr("MULTI"))
        self.assertFalse(scenario_is_adr("SF8"))

    def test_unknown_scenario_raises(self):
        with self.assertRaises(ValueError):
            parse_scenario("FASTEST", guamal())

    def test_scenario_needing_an_absent_sensitivity_raises(self):
        with self.assertRaises(ValueError):
            parse_scenario("SF12", guamal())


class TestIdealAssignment(unittest.TestCase):

    def test_picks_the_shortest_airtime_that_reaches(self):
        cfg = guamal()
        self.assertEqual(choose_sf_adaptive(cfg, 100.0, SFS)[0], 7)

    def test_sits_on_the_sensitivity_threshold(self):
        """MULTI keeps no margin, which is what makes it a bound rather than a
        network."""
        cfg = guamal()
        from loracap.core import max_distance_m
        reach7 = max_distance_m(cfg, GUAMAL_SENSI[7])
        self.assertEqual(choose_sf_adaptive(cfg, reach7 * 0.999, SFS)[0], 7)
        self.assertNotEqual(choose_sf_adaptive(cfg, reach7 * 1.001, SFS)[0], 7)

    def test_returns_none_when_nothing_reaches(self):
        self.assertIsNone(choose_sf_adaptive(guamal(), 1e6, SFS))

    def test_shadowing_changes_the_assignment(self):
        """A node's fixed shadowing is part of its link, so the choice is made
        against the link it actually has."""
        cfg = guamal()
        clear = choose_sf_adaptive(cfg, 900.0, SFS)[0]
        # -10 dB still reaches, on a slower data rate. Deeper than about
        # -14 dB nothing reaches at this distance and the answer is None,
        # which a different test covers.
        shadowed = choose_sf_adaptive(cfg, 900.0, SFS, shadowing_db=-10.0)[0]
        self.assertGreater(shadowed, clear)
        self.assertIsNone(choose_sf_adaptive(cfg, 900.0, SFS, shadowing_db=-20.0))


class TestSteadyStateADR(unittest.TestCase):

    def test_keeps_a_margin_so_it_is_slower_than_ideal(self):
        cfg = guamal(adr_margin_db=10.0)
        at_edge = 900.0
        self.assertLessEqual(choose_sf_adaptive(cfg, at_edge, SFS)[0],
                             choose_adr(cfg, at_edge, SFS)[0])

    def test_reduces_power_for_a_close_node(self):
        cfg = guamal(adr_margin_db=10.0, tx_power_offsets_db=tuple(
            range(0, -21, -2)))
        _sf, power = choose_adr(cfg, 50.0, SFS)
        self.assertLess(power, cfg.tx_power_dbm)

    def test_leaves_power_alone_without_an_offset_table(self):
        cfg = guamal(adr_margin_db=10.0, tx_power_offsets_db=())
        _sf, power = choose_adr(cfg, 50.0, SFS)
        self.assertEqual(power, cfg.tx_power_dbm)

    def test_power_is_quantised_to_the_plan_steps(self):
        cfg = guamal(adr_margin_db=10.0,
                     tx_power_offsets_db=tuple(range(0, -21, -2)))
        for d in (50.0, 120.0, 300.0, 600.0):
            _sf, power = choose_adr(cfg, d, SFS)
            offset = power - cfg.tx_power_dbm
            self.assertAlmostEqual(offset % 2, 0.0, places=9,
                                   msg=f"{offset} dB is not a 2 dB step")

    def test_margin_is_not_an_admission_test(self):
        """REGRESSION. ADR is an optimisation on top of a working link, not a
        gate. A node that reaches but cannot afford the margin must stay on
        the slowest data rate it can use, at full power, and simply never
        speed up. Excluding it instead hid struggling nodes from DER and made
        ADR look better the worse propagation got: capacity appeared to rise
        from 147 to 174 under shadowing purely by dropping a fifth of the
        fleet."""
        cfg = guamal(adr_margin_db=10.0)
        # a shadowing depth that leaves the link usable but with no margin
        choice = choose_adr(cfg, 900.0, SFS, shadowing_db=-8.0)
        self.assertIsNotNone(choice, "a reachable node was excluded")
        sf, power = choice
        self.assertIn(sf, SFS)
        self.assertEqual(power, cfg.tx_power_dbm,
                         "a node with no margin must stay at full power")

    def test_still_returns_none_when_genuinely_out_of_range(self):
        """The fallback must not become a way of serving unreachable nodes."""
        self.assertIsNone(choose_adr(guamal(), 1e6, SFS, shadowing_db=-40.0))

    def test_a_bigger_margin_never_speeds_a_node_up(self):
        cfg_small = guamal(adr_margin_db=0.0)
        cfg_big = guamal(adr_margin_db=15.0)
        for d in (200.0, 500.0, 900.0):
            self.assertLessEqual(choose_adr(cfg_small, d, SFS)[0],
                                 choose_adr(cfg_big, d, SFS)[0])


if __name__ == "__main__":
    unittest.main()
