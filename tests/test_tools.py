"""Geometry, the propagation fit and the capacity analysis: everything that
turns field data into a study, or results into a number.
"""
import math
import unittest

from loracap import analysis, geo, pathloss, study as study_mod

# A square kilometre, drawn clockwise, with the first vertex repeated as KML
# does. Both the winding and the repeat are things a real export does and a
# naive area calculation gets wrong.
KML_SQUARE = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
  <Placemark><name>Field</name><Polygon><outerBoundaryIs><LinearRing>
    <coordinates>
      -73.825,3.9195,0 -73.825,3.9240,0 -73.820,3.9240,0
      -73.820,3.9195,0 -73.825,3.9195,0
    </coordinates>
  </LinearRing></outerBoundaryIs></Polygon></Placemark>
</Document></kml>
"""


class TestGeometry(unittest.TestCase):

    def test_shoelace_area_of_a_known_square(self):
        ring = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
        self.assertAlmostEqual(geo.shoelace_area_m2(ring), 10_000.0, places=6)

    def test_area_is_independent_of_winding_direction(self):
        ring = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
        self.assertAlmostEqual(geo.shoelace_area_m2(ring),
                               geo.shoelace_area_m2(list(reversed(ring))),
                               places=6)

    def test_point_in_polygon(self):
        ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        self.assertTrue(geo.point_in_ring(5.0, 5.0, ring))
        self.assertFalse(geo.point_in_ring(15.0, 5.0, ring))
        self.assertFalse(geo.point_in_ring(-1.0, -1.0, ring))

    def test_kml_round_trip(self):
        placemarks = geo.parse_kml(KML_SQUARE, is_text=True)
        self.assertEqual(len(placemarks), 1)
        self.assertEqual(placemarks[0][0], "Field")
        rings = geo.project_rings(placemarks, 3.92175, -73.8225)
        info = geo.inspect(rings)
        # about 0.005 degrees of longitude by 0.0045 of latitude, near the
        # equator: roughly 555 m by 498 m
        self.assertTrue(26 < info["total_area_ha"] < 29,
                        f"{info['total_area_ha']:.2f} ha")
        self.assertTrue(info["gateway_inside"])
        self.assertTrue(300 < info["max_radius_m"] < 450)

    def test_gateway_outside_the_boundary_is_reported(self):
        """Usually the sign of a transposed coordinate, which otherwise
        produces a perfectly plausible-looking study."""
        rings = geo.project_rings(geo.parse_kml(KML_SQUARE, is_text=True),
                                  3.95, -73.90)
        self.assertFalse(geo.inspect(rings)["gateway_inside"])


class TestPropagationFit(unittest.TestCase):

    def test_recovers_a_known_line(self):
        xs = [math.log10(d) for d in (50, 100, 200, 400, 800, 1600)]
        ys = [-60.0 - 21.59 * x for x in xs]      # exponent 2.159, no noise
        a, b, r2, sigma = pathloss.linear_fit(xs, ys)
        self.assertAlmostEqual(a, -60.0, places=6)
        self.assertAlmostEqual(-b / 10.0, 2.159, places=6)
        self.assertAlmostEqual(r2, 1.0, places=9)
        self.assertAlmostEqual(sigma, 0.0, places=6)

    def test_residual_sigma_recovers_injected_scatter(self):
        """The residual is the log-normal shadowing term, not a
        goodness-of-fit statistic, so it has to come out in decibels."""
        import random
        rng = random.Random(4)
        xs, ys = [], []
        for _ in range(4000):
            x = math.log10(rng.uniform(50, 2000))
            xs.append(x)
            ys.append(-60.0 - 21.59 * x + rng.gauss(0.0, 6.0))
        _a, _b, _r2, sigma = pathloss.linear_fit(xs, ys)
        self.assertAlmostEqual(sigma, 6.0, delta=0.3)

    def test_a_fit_needs_more_than_one_distance(self):
        with self.assertRaises(ValueError):
            pathloss.linear_fit([2.0, 2.0, 2.0], [-100.0, -101.0, -99.0])

    def test_study_snippet_carries_the_sigma(self):
        fit = {"path_loss_exponent": 2.159, "path_loss_ref_db": 130.32,
               "path_loss_ref_distance_m": 100.0, "min_distance_m": 30.0,
               "max_distance_m": 2208.0, "r_squared": 0.634,
               "shadowing_sigma_db": 7.41, "label": "unbinned",
               "n_points": 1229}
        snippet = pathloss.study_snippet(fit)
        self.assertIn("shadowing_sigma_db=7.41", snippet)
        self.assertIn("path_loss_exponent=2.159", snippet)


class TestCapacityAnalysis(unittest.TestCase):

    def test_crossing_interpolates_between_bracketing_points(self):
        self.assertAlmostEqual(
            analysis.crossing([10, 20], [0.95, 0.85], 0.9), 15.0, places=6)

    def test_no_crossing_returns_none(self):
        self.assertIsNone(analysis.crossing([10, 20], [0.95, 0.93], 0.9))

    def test_confidence_interval_brackets_the_point_estimate(self):
        rows = [{"scenario": "SF8", "n_nodes": n,
                 "der_mean": d, "der_runs": [d - 0.004, d, d + 0.004]}
                for n, d in ((10, 0.98), (50, 0.93), (100, 0.88), (200, 0.80))]
        cap = analysis.capacity_with_ci(rows, threshold=0.9, n_boot=400)["SF8"]
        self.assertIsNotNone(cap["capacity"])
        self.assertLessEqual(cap["ci_low"], cap["capacity"])
        self.assertLessEqual(cap["capacity"], cap["ci_high"])


class TestStudyRendering(unittest.TestCase):

    def test_values_survive_a_round_trip_through_the_generated_module(self):
        text = study_mod.render_study_module(
            {"name": "x", "site": "A place", "region": "EU868",
             "payload_bytes": 20, "scenarios": ["SF7", "ADR"]},
            use_site_polygon=False)
        self.assertIn("name='x'", text)
        self.assertIn("region='EU868'", text)
        self.assertIn("payload_bytes=20", text)

    def test_quotes_and_newlines_cannot_break_out_of_the_literal(self):
        """The web interface writes this file from form input, so a quote in
        a site name must not become executable code."""
        text = study_mod.render_study_module(
            {"name": "x", "site": 'He said "hi"\nand left'},
            use_site_polygon=False)
        compile(text, "<generated>", "exec")       # raises if it is malformed
        self.assertNotIn('site="He said "hi""', text)


if __name__ == "__main__":
    unittest.main()
