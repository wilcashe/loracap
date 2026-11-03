"""Resolving one study under two propagation models.

Fast tests only: constructing the variants and judging the result. Actually
running both models is `run.py compare`, which takes minutes.
"""
import unittest

from loracap import compare, study as study_mod
from loracap.core import max_distance_m
from tests.helpers import study

SQUARE = [[(-500.0, -500.0), (500.0, -500.0), (500.0, 500.0), (-500.0, 500.0)]]


def sited(**over):
    over.setdefault("placement", "polygon")
    over.setdefault("polygons_m", SQUARE)
    return study(**over)


class TestSiteRadius(unittest.TestCase):

    def test_radius_of_a_square(self):
        """The farthest point of a 1 km square centred on the gateway is its
        corner, at 500*sqrt(2)."""
        self.assertAlmostEqual(compare.site_radius_m(sited()), 707.1, places=1)

    def test_disc_placement_has_no_site_radius(self):
        """A study placed over the coverage disc has no boundary, so there is
        nothing for an expected reach to be anchored to."""
        self.assertIsNone(compare.site_radius_m(study(placement="disc")))


class TestTerrainVariant(unittest.TestCase):

    def test_takes_the_published_median_exponent(self):
        _label, overrides, prov = compare.terrain_variant(sited(), "rural")
        self.assertEqual(overrides["path_loss_exponent"], prov["median"])
        self.assertEqual(prov["range_low"], 1.87)
        self.assertEqual(prov["range_high"], 3.39)

    def test_anchor_makes_the_link_reach_exactly_that_far(self):
        s = sited()
        _label, overrides, prov = compare.terrain_variant(s, "rural")
        import dataclasses
        cfg = dataclasses.replace(s.to_sim_config(), **overrides)
        reach = max_distance_m(cfg, cfg.sensitivity_dbm[prov["anchor_sf"]])
        self.assertAlmostEqual(reach, prov["anchor_range_m"], places=3)

    def test_anchor_defaults_to_the_slowest_simulated_data_rate(self):
        """REGRESSION. It once defaulted to the slowest the chip supports.
        On a study running SF7 to SF9 that anchored SF10, which no scenario
        uses, and every simulated data rate then fell short of the site for a
        reason that had nothing to do with the terrain."""
        s = sited(scenarios=("SF7", "SF8", "SF9"))
        _l, _o, prov = compare.terrain_variant(s, "rural")
        self.assertEqual(prov["anchor_sf"], 9)

    def test_explicit_range_overrides_the_site_radius(self):
        _l, _o, prov = compare.terrain_variant(sited(), "rural", range_m=2000.0)
        self.assertEqual(prov["anchor_range_m"], 2000.0)

    def test_disc_study_demands_an_explicit_range(self):
        with self.assertRaises(ValueError):
            compare.terrain_variant(study(placement="disc"), "rural")
        # but succeeds once told how far the link should reach
        _l, _o, prov = compare.terrain_variant(
            study(placement="disc"), "rural", range_m=1500.0)
        self.assertEqual(prov["anchor_range_m"], 1500.0)

    def test_unknown_terrain_raises(self):
        with self.assertRaises(KeyError):
            compare.terrain_variant(sited(), "tundra")


class TestExponentOnlyVariant(unittest.TestCase):

    def test_keeps_the_fitted_intercept(self):
        s = sited()
        _label, overrides, prov = compare.exponent_only_variant(s, "rural")
        self.assertEqual(set(overrides), {"path_loss_exponent"})
        self.assertEqual(prov["path_loss_ref_db"], s.path_loss_ref_db)
        self.assertIsNone(prov["anchor_range_m"])

    def test_moves_coverage_far_less_than_anchoring_does(self):
        """Separating the two is the point of having both: the exponent is
        worth a few per cent while coverage holds, and the anchor is worth
        everything else."""
        import dataclasses
        s = sited()
        base = s.to_sim_config()
        _l, exp_only, _p = compare.exponent_only_variant(s, "rural")
        _l, anchored, _p = compare.terrain_variant(s, "rural")
        sens = base.sensitivity_dbm[8]
        reach = lambda o: max_distance_m(dataclasses.replace(base, **o), sens)
        self.assertGreater(reach(exp_only), reach(anchored))


class TestGuards(unittest.TestCase):

    def test_only_propagation_fields_may_differ(self):
        """Anything else and the comparison stops being about propagation,
        while still presenting itself as though it were."""
        with self.assertRaises(ValueError):
            compare.compare_models(sited(), [("a", {}), ("b", {"n_runs": 3})])

    def test_a_propagation_field_is_accepted(self):
        self.assertIn("shadowing_sigma_db", compare.PROPAGATION_FIELDS)
        self.assertIn("path_loss_exponent", compare.PROPAGATION_FIELDS)


class TestVerdict(unittest.TestCase):

    def _result(self, baseline, estimate, ci):
        return {
            "study": "x", "threshold": 0.9, "n_runs": 1, "scenarios": ["SF8"],
            "site_radius_m": 700.0,
            "baseline_model": {"path_loss_exponent": 2.1,
                               "path_loss_ref_db": 130.0},
            "variants": [
                {"label": "fitted", "overrides": {},
                 "capacity": {"SF8": {"capacity": baseline,
                                      "ci_low": ci[0], "ci_high": ci[1]}},
                 "reach_m": {"SF8": 2000.0}, "covers_site": {"SF8": True},
                 "reach_ratio": {"SF8": 2.9}, "unreachable_fraction": {"SF8": 0.0}},
                {"label": "assumed", "overrides": {"path_loss_exponent": 2.9},
                 "capacity": {"SF8": {"capacity": estimate,
                                      "ci_low": None, "ci_high": None}},
                 "reach_m": {"SF8": 900.0}, "covers_site": {"SF8": True},
                 "reach_ratio": {"SF8": 1.3}, "unreachable_fraction": {"SF8": 0.0}},
            ],
        }

    def test_estimate_inside_the_measured_interval(self):
        v = compare.assess(self._result(60.0, 61.0, (59.0, 63.0)))
        self.assertTrue(v["all_inside"])
        self.assertTrue(v["comparisons"][0]["inside"])

    def test_estimate_outside_is_reported_with_its_size(self):
        v = compare.assess(self._result(60.0, 90.0, (59.0, 63.0)))
        self.assertFalse(v["all_inside"])
        self.assertAlmostEqual(v["comparisons"][0]["relative_error"], 0.5,
                               places=9)

    def test_no_crossing_is_not_counted_as_agreement(self):
        """A model that never reaches the threshold has not agreed with
        anything, so it must not quietly pass."""
        v = compare.assess(self._result(60.0, None, (59.0, 63.0)))
        self.assertIsNone(v["comparisons"][0]["inside"])
        self.assertFalse(v["all_inside"])

    def test_format_runs_without_a_crossing(self):
        text = compare.format_comparison(self._result(60.0, None, (59.0, 63.0)))
        self.assertIn("nothing to compare", text)


if __name__ == "__main__":
    unittest.main()
