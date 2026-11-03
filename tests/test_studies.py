"""The studies that ship with the package.

They are documentation as much as data, and a quantity quoted in a README
that no longer comes out of the code is worse than no quantity at all. These
check the cheap derived figures, not the simulated ones: capacity belongs to
`run.py run`, which takes minutes.
"""
import unittest

from loracap import geo, study as study_mod
from loracap.core import airtime_ms, max_distance_m


def load(name):
    return study_mod.load_study(name)


class TestEveryShippedStudyValidates(unittest.TestCase):

    def test_all_studies_are_valid(self):
        for name in study_mod.list_studies():
            if name == "_template":
                continue            # deliberately incomplete, see below
            with self.subTest(study=name):
                errors, _warnings, _info = study_mod.validate(load(name))
                self.assertEqual(errors, [], f"{name}: {errors}")

    def test_the_template_is_incomplete_on_purpose(self):
        """It is a starting point with the site-specific fields left blank, so
        it must NOT validate. If it ever does, someone has filled it in with
        values that would then be silently inherited by every new study."""
        errors, _w, _i = study_mod.validate(load("_template"))
        self.assertTrue(errors, "the template should not be runnable as is")


class TestWorkedExample(unittest.TestCase):
    """Guamal, Meta. The figures quoted in the README and in the published
    paper."""

    def setUp(self):
        self.study = load("iot4cows")

    def test_site_geometry(self):
        info = geo.inspect([("p", r) for r in self.study.polygons_m])
        self.assertAlmostEqual(info["total_area_ha"], 88.54, places=1)
        self.assertTrue(info["gateway_inside"])
        self.assertAlmostEqual(info["max_radius_m"], 958, delta=1.0)

    def test_reach_per_spreading_factor(self):
        """SF8 reaching about 2.37 km is what the field campaign's 2.21 km
        maximum observed link is checked against."""
        cfg = self.study.to_sim_config()
        self.assertAlmostEqual(max_distance_m(cfg, cfg.sensitivity_dbm[8]),
                               2371, delta=5)
        self.assertAlmostEqual(max_distance_m(cfg, cfg.sensitivity_dbm[7]),
                               1817, delta=5)

    def test_it_is_deterministic_by_choice_and_says_so(self):
        """It reproduces a published analysis that used no shadowing term, so
        sigma stays at zero and `check` warns about the discarded residual."""
        self.assertEqual(self.study.shadowing_sigma_db, 0.0)
        _e, warnings, _i = study_mod.validate(self.study)
        self.assertTrue(any("shadowing_sigma_db is 0" in w for w in warnings))

    def test_conservative_bound_is_a_legal_data_rate(self):
        """SF10 was the published bound and is not transmittable with a
        32-byte payload in US915, DR0 carrying eleven bytes. SF9 replaced
        it."""
        self.assertIn("SF9", self.study.scenarios)
        self.assertNotIn("SF10", self.study.scenarios)


class TestReproductionStudies(unittest.TestCase):
    """Bor et al., MSWiM 2016, Experiment Set 1."""

    def test_sn1_airtime_matches_the_published_figure(self):
        cfg = load("bor2016_sn1").to_sim_config()
        self.assertAlmostEqual(airtime_ms(cfg, 12), 1712.13, places=2)

    def test_the_pair_differs_only_in_coding_rate(self):
        """SN1 against SN3 is a control: anything that moves between them has
        to be the coding rate and nothing else."""
        sn1, sn3 = load("bor2016_sn1"), load("bor2016_sn3")
        self.assertNotEqual(sn1.coding_rate, sn3.coding_rate)
        for field in ("region", "bw_khz", "payload_bytes", "send_interval_s",
                      "tx_power_dbm", "path_loss_exponent", "path_loss_ref_db",
                      "path_loss_ref_distance_m", "n_channels", "sim_time_s",
                      "node_counts", "scenarios", "placement"):
            self.assertEqual(getattr(sn1, field), getattr(sn3, field), field)

    def test_the_three_settings_that_decide_the_experiment(self):
        """One channel, no demodulator limit, and their own measured
        sensitivity. Left at this tool's defaults each would quietly produce a
        different number for reasons unrelated to the engine."""
        for name in ("bor2016_sn1", "bor2016_sn3"):
            s = load(name)
            with self.subTest(study=name):
                self.assertEqual(s.n_channels, 1)
                self.assertIsNone(s.max_simultaneous_demodulations)
                self.assertIsNotNone(s.sensitivity_dbm)
                self.assertEqual(s.sensitivity_dbm[12], -133.25)

    def test_propagation_matches_the_paper(self):
        """Section 3.2: d0 = 40 m, Lpl(d0) = 127.41 dB, gamma = 2.08."""
        s = load("bor2016_sn3")
        self.assertEqual(s.path_loss_ref_distance_m, 40.0)
        self.assertEqual(s.path_loss_ref_db, 127.41)
        self.assertEqual(s.path_loss_exponent, 2.08)
        # the paper fits sigma = 3.57 dB and then sets it to zero
        self.assertEqual(s.shadowing_sigma_db, 0.0)

    def test_modelled_range(self):
        """About 360 m, inverting the model consistently in base 10. LoRaSim's
        own maxDist inverts in base e and returns 99 m, which is the figure
        the paper quotes as 'around 100 m'."""
        cfg = load("bor2016_sn3").to_sim_config()
        self.assertAlmostEqual(max_distance_m(cfg, cfg.sensitivity_dbm[12]),
                               360, delta=5)


if __name__ == "__main__":
    unittest.main()
