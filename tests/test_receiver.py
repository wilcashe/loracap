"""The two receiver rules, case by case, and the analytical bound of the second.

Each case in `TestOverlapCases` is a situation that was measured on a real
chip, and its docstring says where. A is the packet already in the air, B the
one that arrives after it, both on one channel and one spreading factor. The
LoRaSim column is pinned as well as the lock column: it is the default, and
the cases where the two differ are the point of having two.

SF12 at 125 kHz throughout, so one symbol is 32.768 ms and the lock window,
`preamble_critical_ms`, is three symbols.
"""
import dataclasses
import math
import random
import statistics as stats
import unittest

from loracap.core import (_Packet, airtime_ms, preamble_critical_ms,
                          resolve_overlap, run_batch)
from loracap.validation import offered_load
from tests.helpers import config, study

SF = 12
T_SYM = 2.0 ** SF / 125.0


def cfg_for(model, **over):
    over.setdefault("capture_threshold_db", 6.0)
    return config(receiver_model=model, **over)


def pair(cfg, b_offset_symbols, b_minus_a_db, a_rssi=-110.0):
    """A starts at 0. B starts `b_offset_symbols` later, `b_minus_a_db`
    stronger. Returns (A, B)."""
    dur = airtime_ms(cfg, SF)
    a = _Packet(0, SF, 0, a_rssi, 0.0, dur)
    b = _Packet(1, SF, 0, a_rssi + b_minus_a_db, b_offset_symbols * T_SYM, dur)
    return a, b


def outcome(model, offset, db, **over):
    cfg = cfg_for(model, **over)
    a, b = pair(cfg, offset, db)
    return resolve_overlap(cfg, a, b)


BOTH_LOST = (True, True)
A_LOST = (True, False)
B_LOST = (False, True)
NONE_LOST = (False, False)


class TestOverlapCases(unittest.TestCase):

    def test_window_is_three_symbols(self):
        self.assertAlmostEqual(preamble_critical_ms(cfg_for("lock"), SF),
                               3 * T_SYM)

    def test_e1_stronger_packet_inside_the_lock_window_wins(self):
        """Bor et al. 2016, Figure 3: a strong transmission is decoded when it
        arrives up to at most 3 symbols late, suppressing the weak one."""
        for model in ("lorasim", "lock"):
            self.assertEqual(outcome(model, 2.0, +10.0), A_LOST, model)

    def test_e2_stronger_packet_after_the_lock_destroys_both(self):
        """Bor et al. 2016, Figure 3: past 3 symbols "no transmission gets
        through". Haxhibeqiri et al. 2017, Tables 4 and 5: 12 dB stronger
        and after the header, the first has a bad CRC and the second is lost.
        LoRaSim's rule lets the stronger one through, which is the case its
        own measurement contradicts."""
        self.assertEqual(outcome("lock", 10.0, +10.0), BOTH_LOST)
        self.assertEqual(outcome("lorasim", 10.0, +10.0), A_LOST)

    def test_e3_equal_power_after_the_lock_keeps_the_first(self):
        """Haxhibeqiri et al. 2017, Tables 2 and 3: at equal received power
        the first packet is received and the second lost. LoRaSim loses both."""
        self.assertEqual(outcome("lock", 10.0, +0.5), B_LOST)
        self.assertEqual(outcome("lorasim", 10.0, +0.5), BOTH_LOST)

    def test_e4_weaker_packet_after_the_lock_is_the_one_lost(self):
        for model in ("lorasim", "lock"):
            self.assertEqual(outcome(model, 10.0, -10.0), B_LOST, model)

    def test_e5_earlier_packet_ending_in_the_allowance_harms_neither(self):
        """Bor et al. 2016, eq. 10, and Haxhibeqiri et al. 2017, Table 2 at
        1500 and 1600 ms: a packet that loses only the start of its preamble
        to the tail of another is still received, and so is the other."""
        cfg = cfg_for("lock")
        dur_symbols = airtime_ms(cfg, SF) / T_SYM
        for model in ("lorasim", "lock"):
            for db in (-10.0, 0.0, +10.0):
                self.assertEqual(outcome(model, dur_symbols - 1.0, db),
                                 NONE_LOST, (model, db))

    def test_e6_equal_power_inside_the_window_loses_both(self):
        for model in ("lorasim", "lock"):
            self.assertEqual(outcome(model, 1.0, +0.5), BOTH_LOST, model)

    def test_weaker_packet_inside_the_window_is_the_one_lost(self):
        for model in ("lorasim", "lock"):
            self.assertEqual(outcome(model, 1.0, -10.0), B_LOST, model)


class TestBoundaries(unittest.TestCase):

    def test_arrival_exactly_at_the_window_edge_is_inside(self):
        """"Up to at most 3 symbols late" includes the third."""
        self.assertEqual(outcome("lock", 3.0, +10.0), A_LOST)

    def test_arrival_just_past_the_edge_is_locked_out(self):
        self.assertEqual(outcome("lock", 3.0 + 1e-6, +10.0), BOTH_LOST)

    def test_exactly_the_threshold_counts_as_stronger(self):
        """Same boundary as the power rule, where a difference equal to the
        threshold is resolved rather than lost both ways."""
        self.assertEqual(outcome("lock", 10.0, +6.0), BOTH_LOST)
        self.assertEqual(outcome("lorasim", 1.0, +6.0), A_LOST)

    def test_just_below_the_threshold_counts_as_equal(self):
        self.assertEqual(outcome("lock", 10.0, +5.999), B_LOST)
        self.assertEqual(outcome("lorasim", 1.0, +5.999), BOTH_LOST)

    def test_without_preamble_allowance_the_lock_is_immediate(self):
        """No window at all: a packet arriving one symbol late is already
        locked out, where with the allowance it would be inside the window."""
        self.assertEqual(outcome("lock", 1.0, +0.5, preamble_capture=False),
                         B_LOST)
        self.assertEqual(outcome("lock", 1.0, +0.5), BOTH_LOST)

    def test_an_infinite_threshold_never_lets_the_later_packet_win(self):
        self.assertEqual(
            outcome("lock", 10.0, +60.0, capture_threshold_db=math.inf), B_LOST)


class TestConfiguration(unittest.TestCase):

    def test_lorasim_is_the_default(self):
        self.assertEqual(config().receiver_model, "lorasim")
        self.assertEqual(study().to_sim_config().receiver_model, "lorasim")

    def test_the_study_passes_its_rule_to_the_engine(self):
        s = study(receiver_model="lock")
        self.assertEqual(s.to_sim_config().receiver_model, "lock")

    def test_an_unknown_rule_is_a_study_error(self):
        from loracap.study import validate
        errors, _, _ = validate(study(receiver_model="locked"))
        self.assertTrue(any("receiver_model" in e for e in errors), errors)

    def test_an_unknown_rule_cannot_reach_the_engine_by_replace(self):
        with self.assertRaises(ValueError):
            dataclasses.replace(config(), receiver_model="Lock")


class TestFirstComeBound(unittest.TestCase):
    """With the lock rule, one channel, no capture and no preamble allowance,
    a packet survives exactly when no other packet is already in the air as
    it starts. Later arrivals cannot harm it. With Poisson arrivals at total
    rate N/interval and a fixed airtime T that probability is exp(-G),
    G = N T / interval.

    It is the lock rule's counterpart of pure ALOHA's exp(-2G): half the
    vulnerable period, because only the packet that arrives second is lost."""

    def _bare(self, model):
        return config(receiver_model=model, n_channels=1,
                      capture_threshold_db=math.inf, preamble_capture=False,
                      avg_send_interval_ms=100_000.0, placement="disc")

    def _der(self, cfg, n):
        r = run_batch(cfg, n, 3_000_000.0, "SF7", 12, 7)
        sem = r["der_std"] / math.sqrt(len(r["der_runs"]))
        return r["der_mean"], sem

    def test_lock_degenerates_onto_exp_minus_g(self):
        for n in (100, 300):
            cfg = self._bare("lock")
            got, sem = self._der(cfg, n)
            want = math.exp(-offered_load(cfg, n, 7, n_channels=1))
            self.assertLess(abs(got - want), 3 * sem + 0.002,
                            f"N={n}: {got:.4f} against exp(-G) {want:.4f}")

    def test_and_not_onto_the_aloha_bound(self):
        """The two bounds differ by a factor exp(G). Landing on exp(-G) and
        not on exp(-2G) is what shows the later packet is the only casualty."""
        cfg = self._bare("lock")
        n = 300
        got, sem = self._der(cfg, n)
        g = offered_load(cfg, n, 7, n_channels=1)
        self.assertGreater(got - math.exp(-2 * g), 10 * sem)


if __name__ == "__main__":
    unittest.main()


class TestLadderForTheLockRule(unittest.TestCase):
    """A lock study's ladder is the LoRaSim ladder with one rung on top that
    swaps the rule back, plus the lock rule's own bound beside it."""

    def test_a_lorasim_study_keeps_the_ladder_it_always_had(self):
        from loracap import validation as val
        self.assertEqual(val.ladder_for(config()), val.LADDER)

    def test_a_lock_study_gains_one_unsigned_rung_first(self):
        from loracap import validation as val
        rungs = val.ladder_for(config(receiver_model="lock"))
        self.assertEqual(rungs[0], val.LADDER[0])
        self.assertEqual(rungs[1], ("lorasim rule",
                                    {"receiver_model": "lorasim"}, "either"))
        self.assertEqual(rungs[2:], val.LADDER[1:])

    def _ladder(self, swap_delta, demod_delta=0.0, lock_gap=0.0):
        """A synthetic two-row ladder. `swap_delta` is how DER moves on the
        unsigned rung, `demod_delta` on the rung that must go up, `lock_gap`
        how far the first-come run sits from exp(-G)."""
        labels = ["full model", "lorasim rule", "no demod limit"]
        rows = []
        for n in (10, 20):
            full = 0.8
            rungs = {
                "full model": full,
                "lorasim rule": full + swap_delta,
                "no demod limit": full + swap_delta + demod_delta,
            }
            rows.append({
                "n_nodes": n, "offered_load": 0.1, "aloha_der": rungs["no demod limit"],
                "rungs": {k: {"der_mean": v, "der_sem": 0.001} for k, v in rungs.items()},
                "lock_bound": {"der_mean": 0.5 + lock_gap, "der_sem": 0.001,
                               "bound": 0.5},
            })
        return {"rung_labels": labels,
                "rung_directions": [None, "either", "up"], "rows": rows}

    def test_the_first_come_configuration_switches_everything_off(self):
        """The statistical test cannot see a small leftover mechanism: at the
        loads a fast test can afford, the preamble allowance moves DER by less
        than the noise. So the configuration is pinned exactly instead."""
        from loracap import validation as val
        cfg = config(n_channels=8, max_simultaneous_demodulations=8)
        bare = val.lock_bound_config(cfg)
        self.assertEqual(bare.receiver_model, "lock")
        self.assertEqual(bare.n_channels, 1)
        self.assertIsNone(bare.max_simultaneous_demodulations)
        self.assertEqual(bare.capture_threshold_db, math.inf)
        self.assertFalse(bare.preamble_capture)

    def test_the_unsigned_rung_may_move_either_way(self):
        from loracap.validation import assess
        for delta in (+0.1, -0.1):
            v = assess(self._ladder(delta))
            self.assertTrue(v["directions_hold"], delta)
            self.assertTrue(v["passes"], delta)

    def test_the_other_rungs_are_still_checked(self):
        from loracap.validation import assess
        v = assess(self._ladder(+0.1, demod_delta=-0.1))
        self.assertFalse(v["directions_hold"])

    def test_missing_the_first_come_bound_fails_the_verdict(self):
        from loracap.validation import assess
        v = assess(self._ladder(0.0, lock_gap=0.05))
        self.assertTrue(v["directions_hold"])
        self.assertEqual(v["n_lock_agree"], 0)
        self.assertFalse(v["passes"])

    def test_a_lorasim_verdict_has_no_lock_keys(self):
        """Its saved validation.json must not change shape."""
        from loracap.validation import assess
        lad = self._ladder(0.0)
        for row in lad["rows"]:
            del row["lock_bound"]
        self.assertNotIn("lock_agreement", assess(lad))

    def test_run_ladder_lands_on_both_bounds(self):
        """End to end on a small configuration: the descent reaches exp(-2G)
        through the LoRaSim rungs, and the first-come run reaches exp(-G)."""
        from loracap import validation as val
        cfg = config(receiver_model="lock", n_channels=3,
                     avg_send_interval_ms=100_000.0, placement="disc")
        lad = val.run_ladder(cfg, "SF7", [300], sim_time_s=6000.0,
                             n_runs=8, base_seed=3)
        self.assertEqual(lad["rung_labels"][1], "lorasim rule")
        self.assertTrue(all("lock_bound" in r for r in lad["rows"]))
        v = val.assess(lad)
        self.assertTrue(v["passes"], val.format_ladder(lad, v))
        for row in lad["rows"]:
            self.assertAlmostEqual(row["lock_bound"]["bound"],
                                   val.lock_bound_der(cfg, row["n_nodes"], 7))


class TestTheValidationTableShowsTheLockBound(unittest.TestCase):

    def test_table(self):
        import os, shutil
        from loracap import reproduce
        from loracap.reproduce import Experiment
        from tests.test_reproduce import TempStudy
        holder = TempStudy("setUp")
        holder.setUp()
        try:
            exp = Experiment(
                name="val", kind="validate", description="", n_runs=3,
                sim_time_s=300.0, base_seed=7, node_counts=(20, 80),
                overrides={"receiver_model": "lock"},
                options=dict(scenario="SF8"))
            reproduce.run_experiment("tiny", exp, root=holder.root, plot=False,
                                     log=lambda *_: None)
            text = reproduce.render_tables("tiny", exp, root=holder.root)
            self.assertIn("lorasim rule", text)
            self.assertIn("receiver lock", text)
            self.assertIn("exp(-G)", text)
            self.assertIn("first-come points", text)
        finally:
            holder.tearDown()
