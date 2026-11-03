"""Two refinements of the lock receiver rule (ROADMAP item 18).

`lock_survival_db` decides, per spreading factor, whether the locked packet
survives a later one past the lock window. `header_recapture` lets a later
packet stronger by the capture threshold take the receiver over when it
arrives during the locked packet's header.

Each is pinned three ways: to its source, to its boundaries, and to a closed
form that only holds if the rule is exactly as documented. The closed forms
use synthetic Poisson traffic on one channel with the preamble allowance
off, so the receiver locks on arrival and every pair is judged by the
post-lock branch alone.

At 128 kHz one SF7 symbol is exactly 1 ms, so boundaries in symbols are
exact in binary and a boundary test cannot pass by a rounding error.
"""
import copy
import math
import random
import unittest

from tests import helpers  # noqa: F401  (puts the package on sys.path)
from tests.helpers import config, study

from loracap import presets
from loracap import study as study_mod
from loracap import validation as val
from loracap.core import (_Packet, airtime_ms, header_window_ms, in_header,
                          resolve_collisions, resolve_overlap)

# Eigner, diploma thesis, TU Wien, 2021, Table 5.1, typed from the thesis.
EIGNER_TABLE_5_1 = {7: 0, 8: 0, 9: 0.4, 10: 1.3, 11: 2, 12: 2}
EIGNER = presets.lock_survival("EIGNER2021_SX1301")


def lock(**over):
    over.setdefault("capture_threshold_db", 6.0)
    return config(receiver_model="lock", **over)


class TestTheTable(unittest.TestCase):

    def test_matches_the_thesis(self):
        self.assertEqual(EIGNER, {sf: float(v) for sf, v in EIGNER_TABLE_5_1.items()})

    def test_the_source_is_recorded(self):
        src = presets.LOCK_SURVIVAL_SOURCE["EIGNER2021_SX1301"]
        self.assertIn("Table 5.1", src)
        self.assertIn("99%", src)

    def test_a_lookup_returns_a_copy(self):
        t = presets.lock_survival("eigner2021_sx1301")
        t[7] = 99.0
        self.assertEqual(presets.LOCK_SURVIVAL_DB["EIGNER2021_SX1301"][7], 0.0)

    def test_an_unknown_name_is_refused(self):
        with self.assertRaises(ValueError):
            presets.lock_survival("nonesuch")


class TestTheHeaderWindow(unittest.TestCase):
    """At 128 kHz, SF7: preamble ends at 12.25 ms, header at 20.25 ms."""

    def setUp(self):
        self.cfg = lock(bw_khz=128)

    def test_the_window_is_the_eight_symbols_after_the_preamble(self):
        self.assertEqual(header_window_ms(self.cfg, 7), (12.25, 20.25))

    def test_the_start_is_inside_and_the_end_is_not(self):
        self.assertTrue(in_header(self.cfg, 7, 12.25))
        self.assertFalse(in_header(self.cfg, 7, 12.24))
        self.assertTrue(in_header(self.cfg, 7, 20.24))
        self.assertFalse(in_header(self.cfg, 7, 20.25))


def pair(cfg, offset_ms, later_minus_earlier_db, sf=7, earlier_rssi=-110.0):
    # 64 symbols long, whatever the spreading factor, so every offset used
    # below falls inside the earlier packet.
    dur = 64.0 * 2 ** (sf - 7)
    a = _Packet(0, sf, 0, earlier_rssi, 0.0, dur)
    b = _Packet(1, sf, 0, earlier_rssi + later_minus_earlier_db, offset_ms, dur)
    return a, b


class TestSurvival(unittest.TestCase):
    """Past the lock window (3 ms at SF7, 128 kHz), table on."""

    def judge(self, sf, diff_db, **over):
        cfg = lock(bw_khz=128, lock_survival_db=dict(EIGNER), **over)
        a, b = pair(cfg, 30.0 * 2 ** (sf - 7), diff_db, sf=sf)
        return resolve_overlap(cfg, a, b)

    def test_sf7_survives_an_equal_later_packet(self):
        self.assertEqual(self.judge(7, 0.0), (False, True))

    def test_sf7_is_lost_to_a_slightly_stronger_one(self):
        self.assertEqual(self.judge(7, 0.01), (True, True))

    def test_sf12_is_lost_to_an_equal_one(self):
        self.assertEqual(self.judge(12, 0.0), (True, True))

    def test_reaching_the_threshold_exactly_is_survival(self):
        # SF12 needs 2 dB: a later packet exactly 2 dB weaker leaves it whole.
        self.assertEqual(self.judge(12, -2.0), (False, True))
        self.assertEqual(self.judge(12, -1.99), (True, True))

    def test_the_later_packet_is_always_lost_past_the_window(self):
        for diff in (-20.0, 0.0, 20.0):
            self.assertTrue(self.judge(7, diff)[1])

    def test_inside_the_window_the_capture_threshold_still_decides(self):
        cfg = lock(bw_khz=128, lock_survival_db=dict(EIGNER))
        a, b = pair(cfg, 1.0, 0.0)
        self.assertEqual(resolve_overlap(cfg, a, b), (True, True))

    def test_off_keeps_item_13s_rule(self):
        cfg = lock(bw_khz=128)
        a, b = pair(cfg, 30.0, 5.9)
        self.assertEqual(resolve_overlap(cfg, a, b), (False, True))
        a, b = pair(cfg, 30.0, 6.0)
        self.assertEqual(resolve_overlap(cfg, a, b), (True, True))

    def test_lorasim_ignores_it(self):
        cfg = config(bw_khz=128, receiver_model="lorasim", capture_threshold_db=6.0,
                     lock_survival_db=dict(EIGNER), header_recapture=True)
        base = config(bw_khz=128, receiver_model="lorasim", capture_threshold_db=6.0)
        for offset in (1.0, 15.0, 30.0):
            for diff in (-8.0, 0.0, 3.0, 8.0):
                a, b = pair(cfg, offset, diff)
                self.assertEqual(resolve_overlap(cfg, a, b),
                                 resolve_overlap(base, a, b))

    def test_a_missing_spreading_factor_says_which(self):
        cfg = lock(bw_khz=128, lock_survival_db={7: 0.0})
        a, b = pair(cfg, 30.0 * 32, 0.0, sf=12)
        with self.assertRaisesRegex(ValueError, "SF12"):
            resolve_overlap(cfg, a, b)


class TestRecapture(unittest.TestCase):
    """SF7 at 128 kHz: header from 12.25 ms to 20.25 ms. Threshold 6 dB."""

    def judge(self, offset, diff, **over):
        cfg = lock(bw_khz=128, header_recapture=True, **over)
        a, b = pair(cfg, offset, diff)
        return resolve_overlap(cfg, a, b)

    def test_a_stronger_arrival_in_the_header_takes_over(self):
        self.assertEqual(self.judge(15.0, 6.0), (True, False))

    def test_not_stronger_enough_changes_nothing(self):
        self.assertEqual(self.judge(15.0, 5.99), (False, True))

    def test_at_the_header_edges(self):
        self.assertEqual(self.judge(12.25, 10.0), (True, False))
        self.assertEqual(self.judge(20.25, 10.0), (True, True))

    def test_before_the_header_both_are_still_lost(self):
        self.assertEqual(self.judge(10.0, 10.0), (True, True))

    def test_off_no_recapture(self):
        cfg = lock(bw_khz=128)
        a, b = pair(cfg, 15.0, 10.0)
        self.assertEqual(resolve_overlap(cfg, a, b), (True, True))

    def test_it_takes_precedence_over_the_survival_table(self):
        self.assertEqual(
            self.judge(15.0, 6.0, lock_survival_db=dict(EIGNER)), (True, False))


def poisson(cfg, classes, horizon_ms, rng, sf=7):
    """Independent Poisson streams on one channel, one per (rate, rssi)."""
    packets = []
    for k, (rate, rssi) in enumerate(classes):
        t = rng.expovariate(rate)
        i = 0
        while t < horizon_ms:
            packets.append(_Packet((k, i), sf, 0, rssi, t, airtime_ms(cfg, sf)))
            i += 1
            t += rng.expovariate(rate)
    packets.sort(key=lambda p: p.start)
    return packets


def der_of(packets, lost, cls):
    sent = [p for p in packets if p.nodeid[0] == cls]
    return 1 - sum((p.nodeid, p.start) in lost for p in sent) / len(sent), len(sent)


class TestClosedForms(unittest.TestCase):
    """One channel, no preamble allowance, so every later packet is judged
    past the lock window. Within four standard errors of the closed form."""

    def check(self, der, n, bound):
        se = math.sqrt(bound * (1 - bound) / n)
        self.assertLess(abs(der - bound), 4 * se, (der, bound))

    def test_survival_at_equal_power_is_first_come_at_sf7(self):
        """SF7 needs 0 dB, so an equal later packet never harms the locked
        one: the first-come receiver, exp(-G)."""
        cfg = lock(preamble_capture=False, lock_survival_db=dict(EIGNER))
        rate = 1 / 600.0
        packets = poisson(cfg, [(rate, -110.0)], 4e7, random.Random(5), sf=7)
        lost = resolve_collisions(cfg, packets)["collided_ids"]
        der, n = der_of(packets, lost, 0)
        self.check(der, n, math.exp(-rate * airtime_ms(cfg, 7)))

    def test_survival_at_equal_power_is_aloha_at_sf12(self):
        """SF12 needs 2 dB, so an equal later packet always takes the locked
        one with it: pure ALOHA, exp(-2G)."""
        cfg = lock(preamble_capture=False, lock_survival_db=dict(EIGNER))
        rate = 1 / 20000.0
        packets = poisson(cfg, [(rate, -110.0)], 4e8, random.Random(6), sf=12)
        lost = resolve_collisions(cfg, packets)["collided_ids"]
        der, n = der_of(packets, lost, 0)
        self.check(der, n, math.exp(-2 * rate * airtime_ms(cfg, 12)))

    def test_recapture_with_two_power_classes(self):
        """Strong packets are 10 dB above weak ones, threshold 6 dB. A weak
        packet is lost to anything before it and to a strong packet after
        it. A strong packet is lost to a strong one before it, and to a weak
        one before it unless it arrived in that packet's header, H long:

            DER_weak   = exp(-(lambda + lambda_s) T), lambda = lambda_w + lambda_s
            DER_strong = exp(-lambda_s T - lambda_w (T - H))
        """
        cfg = lock(preamble_capture=False, header_recapture=True)
        lw, ls = 1 / 500.0, 1 / 800.0
        packets = poisson(cfg, [(lw, -110.0), (ls, -100.0)], 3e7, random.Random(7))
        lost = resolve_collisions(cfg, packets)["collided_ids"]
        T = airtime_ms(cfg, 7)
        start, end = header_window_ms(cfg, 7)
        H = end - start
        der_w, n_w = der_of(packets, lost, 0)
        der_s, n_s = der_of(packets, lost, 1)
        lam = lw + ls
        self.check(der_w, n_w, math.exp(-(lam + ls) * T))
        self.check(der_s, n_s, math.exp(-ls * T - lw * (T - H)))

    def test_without_recapture_the_strong_class_is_first_come(self):
        cfg = lock(preamble_capture=False)
        lw, ls = 1 / 500.0, 1 / 800.0
        packets = poisson(cfg, [(lw, -110.0), (ls, -100.0)], 3e7, random.Random(7))
        lost = resolve_collisions(cfg, packets)["collided_ids"]
        der_s, n_s = der_of(packets, lost, 1)
        self.check(der_s, n_s, math.exp(-(lw + ls) * airtime_ms(cfg, 7)))


class TestEqualPowerChangesNothingWithRecapture(unittest.TestCase):

    def test_exactly(self):
        """Recapture needs a stronger newcomer, so with every packet at one
        power it must change nothing at all."""
        base = lock()
        on = lock(header_recapture=True)
        packets = poisson(base, [(1 / 300.0, -110.0)], 2e6, random.Random(9))
        a = resolve_collisions(base, copy.deepcopy(packets))
        b = resolve_collisions(on, copy.deepcopy(packets))
        self.assertGreater(len(a["collided_ids"]), 100)
        self.assertEqual(a, b)


class TestTheFirstComeBound(unittest.TestCase):

    def test_switches_the_refinements_off(self):
        cfg = lock(lock_survival_db=dict(EIGNER), header_recapture=True)
        bare = val.lock_bound_config(cfg)
        self.assertIsNone(bare.lock_survival_db)
        self.assertFalse(bare.header_recapture)
        self.assertIsNone(bare.inter_sf_rejection_db)


class TestTheStudyFields(unittest.TestCase):

    def test_a_named_table_reaches_the_engine(self):
        s = study(receiver_model="lock", lock_survival="EIGNER2021_SX1301",
                  header_recapture=True)
        cfg = s.to_sim_config()
        self.assertEqual(cfg.lock_survival_db, EIGNER)
        self.assertTrue(cfg.header_recapture)

    def test_off_by_default(self):
        cfg = study().to_sim_config()
        self.assertIsNone(cfg.lock_survival_db)
        self.assertFalse(cfg.header_recapture)

    def test_check_refuses_them_without_the_lock_rule(self):
        for over in ({"lock_survival": "EIGNER2021_SX1301"},
                     {"header_recapture": True}):
            errors, _w, _i = study_mod.validate(study(**over))
            self.assertTrue(any("receiver_model" in e for e in errors), over)

    def test_check_refuses_a_table_missing_a_spreading_factor(self):
        errors, _w, _i = study_mod.validate(
            study(receiver_model="lock", lock_survival={7: 0.0, 8: 0.0}))
        self.assertTrue(any("SF9" in e for e in errors), errors)

    def test_check_reports_them(self):
        _e, _w, info = study_mod.validate(
            study(receiver_model="lock", lock_survival="EIGNER2021_SX1301",
                  header_recapture=True))
        self.assertTrue(any("Table 5.1" in i for i in info))
        self.assertTrue(any("Header recapture: on" in i for i in info))


if __name__ == "__main__":
    unittest.main()
