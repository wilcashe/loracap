"""Rejection between spreading factors (ROADMAP item 14).

The engine treats spreading factors as orthogonal unless a study names a
rejection table. These tests pin the table to its source, the pair rule to
its boundaries, the collision pass to two results that must hold exactly,
and the whole thing to a closed-form bound for two spreading factors on one
channel.

Packets are built by hand and fed to `resolve_collisions`, which draws
nothing random, so every expectation here is exact except the bound, which
is checked in units of its own standard error.
"""
import copy
import dataclasses
import math
import random
import unittest

from tests import helpers  # noqa: F401  (puts the package on sys.path)
from tests.helpers import config, study

from loracap import presets
from loracap import study as study_mod
from loracap.core import (_Packet, airtime_ms, inter_sf_losses,
                          resolve_collisions, run_batch, run_single_sim)

# Croce, Gucciardo, Mangione, Santaromita and Tinnirello, IEEE Trans.
# Wireless Commun. 19(2):822-834, 2020, Table I, typed from the paper rather
# than copied from presets, so the two are independent sources.
CROCE_TABLE_I = {
    7: {7: 1, 8: -8, 9: -9, 10: -9, 11: -9, 12: -9},
    8: {7: -11, 8: 1, 9: -11, 10: -12, 11: -13, 12: -13},
    9: {7: -15, 8: -13, 9: 1, 10: -13, 11: -14, 12: -15},
    10: {7: -19, 8: -18, 9: -17, 10: 1, 11: -17, 12: -18},
    11: {7: -22, 8: -22, 9: -21, 10: -20, 11: 1, 12: -20},
    12: {7: -25, 8: -25, 9: -25, 10: -24, 11: -23, 12: 1},
}

CROCE = presets.inter_sf_rejection("CROCE2020_SX1272")

# Eigner, diploma thesis, TU Wien, 2021, Table 5.2, SX1301, typed from the
# thesis page rather than copied from presets.
EIGNER_TABLE_5_2 = {
    7: {8: -8.5, 9: -9, 10: -9, 11: -9.5, 12: -9.5},
    8: {7: -11, 9: -11, 10: -11.5, 11: -12, 12: -12.5},
    9: {7: -14.5, 8: -14, 10: -14, 11: -14, 12: -14.5},
    10: {7: -19, 8: -16.5, 9: -16, 11: -17, 12: -17},
    11: {7: -21.5, 8: -22, 9: -21, 10: -20.5, 12: -20},
    12: {7: -24.5, 8: -24.5, 9: -24, 10: -23, 11: -22.5},
}


def t_sym(sf, bw=125):
    return 2.0 ** sf / bw


def pkt(nid, sf, start, rssi, cfg, channel=0):
    return _Packet(nid, sf, channel, rssi, start, airtime_ms(cfg, sf))


def cfg_on(**over):
    return config(inter_sf_rejection_db=CROCE, **over)


class TestTheTableIsTheMeasuredOne(unittest.TestCase):

    def test_every_off_diagonal_entry_matches_the_paper(self):
        for ref, row in CROCE_TABLE_I.items():
            for intf, value in row.items():
                if ref == intf:
                    continue
                with self.subTest(ref=ref, intf=intf):
                    self.assertEqual(CROCE[ref][intf], value)

    def test_the_diagonal_is_left_to_the_capture_rule(self):
        for ref, row in CROCE.items():
            self.assertNotIn(ref, row)

    def test_it_covers_every_pair_from_sf7_to_sf12(self):
        for ref in range(7, 13):
            self.assertEqual(set(CROCE[ref]), set(range(7, 13)) - {ref})

    def test_the_source_is_recorded(self):
        src = presets.INTER_SF_REJECTION_SOURCE["CROCE2020_SX1272"]
        self.assertIn("10.1109/TWC.2019.2948872", src)
        self.assertIn("Table I", src)

    def test_a_lookup_returns_a_copy(self):
        t = presets.inter_sf_rejection("croce2020_sx1272")
        t[7][8] = 99.0
        self.assertEqual(presets.INTER_SF_REJECTION_DB["CROCE2020_SX1272"][7][8], -8.0)

    def test_an_unknown_name_is_refused(self):
        with self.assertRaises(ValueError):
            presets.inter_sf_rejection("nonesuch")


class TestTheConcentratorTable(unittest.TestCase):
    """Eigner's Table 5.2, the one measured on a gateway concentrator."""

    def setUp(self):
        self.table = presets.inter_sf_rejection("EIGNER2021_SX1301")

    def test_every_entry_matches_the_thesis(self):
        for ref, row in EIGNER_TABLE_5_2.items():
            for intf, value in row.items():
                with self.subTest(ref=ref, intf=intf):
                    self.assertEqual(self.table[ref][intf], float(value))

    def test_it_covers_every_pair_and_no_diagonal(self):
        for ref in range(7, 13):
            self.assertEqual(set(self.table[ref]), set(range(7, 13)) - {ref})

    def test_the_source_is_recorded(self):
        src = presets.INTER_SF_REJECTION_SOURCE["EIGNER2021_SX1301"]
        self.assertIn("Table 5.2", src)
        self.assertIn("SX1301", src)

    def test_the_two_tables_agree_within_one_and_a_half_db(self):
        """Stated in presets and in core. Checked so the claim cannot
        outlive a change to either table."""
        worst = max(abs(self.table[r][i] - CROCE[r][i])
                    for r in CROCE for i in CROCE[r])
        self.assertEqual(worst, 1.5)

    def test_check_reports_it(self):
        _e, _w, info = study_mod.validate(
            study(inter_sf_rejection="EIGNER2021_SX1301"))
        self.assertTrue(any("Table 5.2" in i for i in info))


class TestThePairRule(unittest.TestCase):
    """A is SF7, already in the air. B is SF9, arriving 1 ms later, so the
    two overlap for the rest of A. Thresholds: SF7 against SF9 is -9 dB,
    SF9 against SF7 is -15 dB."""

    def setUp(self):
        self.cfg = cfg_on()

    def judge(self, a_rssi, b_rssi, b_start=1.0, a_sf=7, b_sf=9, cfg=None):
        cfg = cfg or self.cfg
        a = pkt(0, a_sf, 0.0, a_rssi, cfg)
        b = pkt(1, b_sf, b_start, b_rssi, cfg)
        return inter_sf_losses(cfg, a, b)

    def test_equal_power_harms_neither(self):
        self.assertEqual(self.judge(-110.0, -110.0), (False, False))

    def test_a_threshold_reached_exactly_is_survived(self):
        # B is 9 dB stronger: A's SIR is exactly -9.
        self.assertEqual(self.judge(-110.0, -101.0), (False, False))

    def test_just_past_the_threshold_is_lost(self):
        self.assertEqual(self.judge(-110.0, -100.99), (True, False))

    def test_each_packet_is_judged_on_its_own_row(self):
        # A 12 dB stronger than B. B's SIR is -12, inside SF9's -15. The same
        # gap the other way round would cost SF7, whose limit is -9.
        self.assertEqual(self.judge(-98.0, -110.0), (False, False))
        self.assertEqual(self.judge(-110.0, -98.0), (True, False))

    def test_the_weaker_side_is_lost_on_the_later_packet_too(self):
        # A 16 dB stronger: B's SIR -16 is below -15.
        self.assertEqual(self.judge(-94.0, -110.0), (False, True))

    def test_an_overlap_of_exactly_one_symbol_counts(self):
        # At 128 kHz an SF7 symbol is exactly 1 ms, so the overlap below is
        # exactly one symbol in binary too, not one symbol give or take a
        # rounding error that would decide the test by accident.
        cfg = cfg_on(bw_khz=128)
        a = _Packet(0, 7, 0, -110.0, 0.0, 64.0)
        b = _Packet(1, 9, 0, -90.0, 63.0, 64.0)
        self.assertEqual(inter_sf_losses(cfg, a, b)[0], True)

    def test_a_shorter_overlap_is_harmless(self):
        a = pkt(0, 7, 0.0, -110.0, self.cfg)
        b = pkt(1, 9, a.dur - 0.99 * t_sym(7), -90.0, self.cfg)
        self.assertEqual(inter_sf_losses(self.cfg, a, b), (False, False))

    def test_the_symbol_floor_is_the_reference_packets_own(self):
        # 2 ms of overlap is two SF7 symbols but half an SF9 one. A weak SF9
        # packet is therefore untouched while a weak SF7 one is lost.
        cfg = self.cfg
        a7 = pkt(0, 7, 0.0, -130.0, cfg)
        b9 = pkt(1, 9, a7.dur - 2.0, -100.0, cfg)
        self.assertEqual(inter_sf_losses(cfg, a7, b9), (True, False))
        a9 = pkt(0, 9, 0.0, -130.0, cfg)
        b7 = pkt(1, 7, a9.dur - 2.0, -100.0, cfg)
        self.assertEqual(inter_sf_losses(cfg, a9, b7), (False, False))

    def test_neither_the_receiver_rule_nor_the_preamble_enters(self):
        for over in ({"receiver_model": "lock"}, {"preamble_capture": False},
                     {"capture_threshold_db": math.inf}):
            with self.subTest(**{k: str(v) for k, v in over.items()}):
                cfg = cfg_on(**over)
                self.assertEqual(self.judge(-110.0, -100.0, cfg=cfg),
                                 (True, False))

    def test_a_missing_pair_says_which(self):
        cfg = config(inter_sf_rejection_db={7: {8: -8.0}})
        with self.assertRaisesRegex(ValueError, "SF7 interfered by SF9"):
            self.judge(-110.0, -100.0, cfg=cfg)


class TestTheConfiguration(unittest.TestCase):

    def test_off_by_default(self):
        self.assertIsNone(config().inter_sf_rejection_db)

    def test_a_same_sf_entry_is_refused(self):
        with self.assertRaisesRegex(ValueError, "against itself"):
            config(inter_sf_rejection_db={7: {7: 1.0, 8: -8.0}})


class TestTheCollisionPass(unittest.TestCase):

    def run_pass(self, cfg, packets):
        return resolve_collisions(cfg, copy.deepcopy(packets))

    def test_different_channels_never_meet(self):
        cfg = cfg_on()
        a = pkt(0, 7, 0.0, -120.0, cfg, channel=0)
        b = pkt(1, 9, 1.0, -90.0, cfg, channel=1)
        out = self.run_pass(cfg, [a, b])
        self.assertEqual(out["collided_ids"], set())

    def test_a_loss_is_reported_and_attributed(self):
        cfg = cfg_on()
        a = pkt(0, 7, 0.0, -120.0, cfg)
        b = pkt(1, 9, 1.0, -90.0, cfg)
        out = self.run_pass(cfg, [a, b])
        self.assertEqual(out["collided_ids"], {(0, 0.0)})
        self.assertEqual(out["inter_sf_ids"], {(0, 0.0)})

    def test_off_reports_no_attribution(self):
        cfg = config()
        a = pkt(0, 7, 0.0, -120.0, cfg)
        b = pkt(1, 9, 1.0, -90.0, cfg)
        out = self.run_pass(cfg, [a, b])
        self.assertEqual(out["collided_ids"], set())
        self.assertNotIn("inter_sf_ids", out)

    def test_a_finished_packet_is_not_judged(self):
        cfg = cfg_on()
        a = pkt(0, 7, 0.0, -120.0, cfg)
        b = pkt(1, 9, a.dur + 0.1, -90.0, cfg)
        self.assertEqual(self.run_pass(cfg, [a, b])["collided_ids"], set())

    def test_a_packet_dropped_for_capacity_is_counted_once(self):
        """One demodulator. P1 holds it, so P2 and P3 are dropped for
        capacity. P3, 30 dB stronger on SF8, then takes P2 on SF9 as well.
        P2 must stay a capacity loss and never also become a collision."""
        cfg = cfg_on(max_simultaneous_demodulations=1)
        p1 = pkt(1, 7, 0.0, -100.0, cfg)
        p2 = pkt(2, 9, 1.0, -130.0, cfg)
        p3 = pkt(3, 8, 2.0, -100.0, cfg)
        out = self.run_pass(cfg, [p1, p2, p3])
        self.assertEqual(out["lost_capacity"], 2)
        self.assertEqual(out["collided_ids"], set())
        self.assertEqual(out["inter_sf_ids"], set())

    def test_a_same_sf_collision_still_follows_the_receiver_rule(self):
        cfg = cfg_on()
        a = pkt(0, 9, 0.0, -110.0, cfg)
        b = pkt(1, 9, 1.0, -110.0, cfg)
        out = self.run_pass(cfg, [a, b])
        self.assertEqual(out["collided_ids"], {(0, 0.0), (1, 1.0)})
        self.assertEqual(out["inter_sf_ids"], set())


def poisson_two_sf(cfg, rate7, rate9, horizon_ms, rng, rssi7=-110.0,
                   rssi9=-110.0):
    """Two independent Poisson streams on one channel, SF7 and SF9."""
    packets = []
    for sf, rate, rssi in ((7, rate7, rssi7), (9, rate9, rssi9)):
        t = rng.expovariate(rate)
        i = 0
        while t < horizon_ms:
            packets.append(pkt((sf, i), sf, t, rssi, cfg))
            i += 1
            t += rng.expovariate(rate)
    packets.sort(key=lambda p: p.start)
    return packets


class TestExactResults(unittest.TestCase):

    def test_equal_power_gives_the_orthogonal_answer_exactly(self):
        """Every measured threshold is negative, so two packets received at
        the same power never harm each other across spreading factors. With
        every packet at one power the table must change nothing at all,
        while same-SF collisions are plentiful."""
        rng = random.Random(11)
        base = config(capture_threshold_db=6.0)
        packets = poisson_two_sf(base, 1 / 400.0, 1 / 1500.0, 2e6, rng)
        off = resolve_collisions(base, copy.deepcopy(packets))
        on = resolve_collisions(
            dataclasses.replace(base, inter_sf_rejection_db=CROCE),
            copy.deepcopy(packets))
        self.assertGreater(len(off["collided_ids"]), 100)
        self.assertEqual(on["collided_ids"], off["collided_ids"])
        self.assertEqual(on["inter_sf_ids"], set())

    def test_a_single_spreading_factor_is_untouched(self):
        cfg = study(scenarios=("SF8",)).to_sim_config()
        on = dataclasses.replace(cfg, inter_sf_rejection_db=CROCE)
        a = run_single_sim(cfg, 120, 600_000.0, "SF8", random.Random(5))
        b = run_single_sim(on, 120, 600_000.0, "SF8", random.Random(5))
        self.assertEqual(b.pop("lost_inter_sf"), 0)
        self.assertEqual(a, b)

    def test_two_spreading_factors_land_on_their_aloha_bound(self):
        """One channel, no capture, no preamble allowance, and a table that
        makes every overlap of at least one symbol destructive. A packet on
        SF i then survives only if no same-SF packet starts within its
        airtime either side, and no packet on SF k starts within the window
        that gives at least one SF i symbol of overlap, which is
        T_i + T_k - 2 t_sym(i) long. For independent Poisson streams:

            DER_i = exp(-2 lambda_i T_i) * exp(-lambda_k (T_i + T_k - 2 t_i))
        """
        always = {7: {9: math.inf}, 9: {7: math.inf}}
        cfg = config(capture_threshold_db=math.inf, preamble_capture=False,
                     inter_sf_rejection_db=always)
        rate = {7: 1 / 900.0, 9: 1 / 2500.0}
        packets = poisson_two_sf(cfg, rate[7], rate[9], 3e7, random.Random(3))
        out = resolve_collisions(cfg, packets)
        lost = out["collided_ids"]
        T = {sf: airtime_ms(cfg, sf) for sf in (7, 9)}
        for i, k in ((7, 9), (9, 7)):
            sent = [p for p in packets if p.sf == i]
            der = 1 - sum((p.nodeid, p.start) in lost for p in sent) / len(sent)
            bound = (math.exp(-2 * rate[i] * T[i])
                     * math.exp(-rate[k] * (T[i] + T[k] - 2 * t_sym(i))))
            se = math.sqrt(bound * (1 - bound) / len(sent))
            with self.subTest(sf=i, der=der, bound=bound):
                self.assertLess(abs(der - bound), 4 * se)


class TestEndToEnd(unittest.TestCase):

    def test_a_spread_of_powers_costs_the_far_nodes(self):
        """MULTI over a disc puts near nodes on fast data rates and far ones
        on slow ones, at full power: the near-far case Croce et al. warn
        about. The rule must find losses there and DER must not rise."""
        cfg = study(scenarios=("MULTI",), send_interval_s=15.0).to_sim_config()
        on = dataclasses.replace(cfg, inter_sf_rejection_db=CROCE)
        off_r = run_batch(cfg, 300, 600_000.0, "MULTI", 4, 7)
        on_r = run_batch(on, 300, 600_000.0, "MULTI", 4, 7)
        self.assertNotIn("lost_inter_sf_mean", off_r)
        self.assertGreater(on_r["lost_inter_sf_mean"], 0)
        self.assertLess(on_r["der_mean"], off_r["der_mean"])


class TestTheStudyField(unittest.TestCase):

    def test_a_named_table_reaches_the_engine(self):
        s = study(inter_sf_rejection="CROCE2020_SX1272")
        self.assertEqual(s.to_sim_config().inter_sf_rejection_db, CROCE)

    def test_unset_reaches_the_engine_as_orthogonal(self):
        self.assertIsNone(study().to_sim_config().inter_sf_rejection_db)

    def test_a_table_of_ones_own_is_taken_with_integer_keys(self):
        table = {str(a): {str(b): -10 for b in (7, 8, 9, 10) if b != a}
                 for a in (7, 8, 9, 10)}
        cfg = study(inter_sf_rejection=table).to_sim_config()
        self.assertEqual(cfg.inter_sf_rejection_db[7][8], -10.0)

    def test_check_reports_the_choice(self):
        _e, _w, info = study_mod.validate(study())
        self.assertTrue(any("treated as orthogonal" in i for i in info))
        _e, _w, info = study_mod.validate(
            study(inter_sf_rejection="CROCE2020_SX1272"))
        self.assertTrue(any("10.1109/TWC.2019.2948872" in i for i in info))

    def test_check_refuses_a_table_missing_a_pair(self):
        table = {a: {b: -10.0 for b in (7, 8, 9) if b != a} for a in (7, 8, 9)}
        errors, _w, _i = study_mod.validate(study(inter_sf_rejection=table))
        self.assertTrue(any("SF7 by SF10" in e for e in errors), errors)

    def test_check_refuses_an_unknown_name(self):
        errors, _w, _i = study_mod.validate(study(inter_sf_rejection="nope"))
        self.assertTrue(any("nope" in e for e in errors), errors)


class TestTheLossesTable(unittest.TestCase):
    """The column exists only when some variant ran with the rule, so every
    table written before item 14 regenerates unchanged."""

    def setUp(self):
        from tests.test_reproduce import TempStudy
        self.tmp = TempStudy()
        self.tmp.setUp()

    def tearDown(self):
        self.tmp.tearDown()

    def render(self, variants):
        from loracap import reproduce
        from tests.test_reproduce import run_exp
        exp = run_exp(name="isf", scenarios=("MULTI",), variants=variants,
                      tables=("losses",))
        reproduce.run_experiment("tiny", exp, root=self.tmp.root, plot=False,
                                 log=lambda *_: None)
        return reproduce.render_tables("tiny", exp, root=self.tmp.root)

    def test_the_column_appears_with_the_rule(self):
        from loracap.reproduce import Variant
        text = self.render((
            Variant("off", "orthogonal"),
            Variant("on", "rejection",
                    {"inter_sf_rejection": "CROCE2020_SX1272"})))
        self.assertIn("of which another SF", text)
        # The orthogonal row says so rather than showing a zero.
        self.assertIn("| off |", text)

    def test_and_not_without_it(self):
        from loracap.reproduce import Variant
        text = self.render((Variant("off", "orthogonal"),))
        self.assertNotIn("another SF", text)


if __name__ == "__main__":
    unittest.main()
