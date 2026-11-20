"""The site map (design item 31).

The map claims to show the placement of one repetition of a run, exactly.
So the first thing checked is that claim: what the map draws is what the
engine simulated, node for node, at the same seed, for a fixed data rate,
MULTI and ADR, on a polygon and on a disc, with shadowing. The rest checks
how the node count is chosen, what is written, what is drawn from it, and
that the study, `reproduce` and the web form all reach it.

Pulling the placement out of the run must not move a single random draw.
tests/test_engine_golden.py guards that bit for bit, and nothing here
repeats it.
"""
import dataclasses
import io
import json
import math
import os
import random
import tempfile
import shutil
import unittest
import zipfile
from unittest import mock

from tests import helpers
from tests.test_reproduce import TempStudy, run_exp
from tests.test_webui import PAGE, TempRoot

import matplotlib.colors

from loracap import core, plotting, reproduce, sitemap
from loracap import study as study_mod
from webui import server

SQUARE = [[(-900.0, -900.0), (900.0, -900.0), (900.0, 900.0), (-900.0, 900.0)]]


def _study(**over):
    return helpers.study(**over)


def _snap(study, scenario, n):
    return sitemap.snapshot(study, scenario, n)


def _rssi_spread(cfg, data):
    """The engine's within-SF received-power spread, from the map's nodes."""
    by = {}
    for nd in data["nodes"]:
        if nd["sf"] is None:
            continue
        by.setdefault(nd["sf"], []).append(core.rssi_dbm(
            cfg, nd["distance_m"], nd["tx_power_dbm"], nd["shadowing_db"]))
    spreads = [max(v) - min(v) for v in by.values() if len(v) > 1]
    return max(spreads) if spreads else 0.0


class TestTheMapIsTheRunsFirstRepetition(unittest.TestCase):
    """Compared with `core.run_batch` itself, so the seed the map replays is
    checked against the one the grid actually uses, not against a copy."""

    CASES = (
        ("polygon, fixed", dict(placement="polygon", polygons_m=SQUARE), "SF8"),
        ("polygon, MULTI, shadowing",
         dict(placement="polygon", polygons_m=SQUARE, shadowing_sigma_db=8.0,
              scenarios=("MULTI",)), "MULTI"),
        ("polygon, ADR, shadowing",
         dict(placement="polygon", polygons_m=SQUARE, shadowing_sigma_db=8.0,
              scenarios=("ADR",)), "ADR"),
        ("disc, MULTI, shadowing",
         dict(placement="disc", shadowing_sigma_db=6.0, scenarios=("MULTI",)),
         "MULTI"),
    )

    def test_counts_and_received_powers_match_the_engine(self):
        for label, over, scen in self.CASES:
            with self.subTest(case=label):
                s = _study(base_seed=11, **over)
                cfg = s.to_sim_config()
                n = 120
                data = _snap(s, scen, n)
                row = core.run_batch(cfg, n, 60_000.0, scen, n_runs=1,
                                     base_seed=s.base_seed)
                per_sf = {int(k): v for k, v in data["counts"]["per_sf"].items()}
                self.assertEqual(per_sf, {int(k): v for k, v in
                                          row["nodes_per_sf_mean"].items()})
                self.assertEqual(data["counts"]["unreachable"], row["unreachable_mean"])
                # Positions, data rates, powers and shadowing all go into the
                # spread, so it agrees only if the placement is the same one.
                # The map rounds metres to the centimetre.
                self.assertAlmostEqual(_rssi_spread(cfg, data),
                                       row["rssi_spread_db_mean"], delta=0.01)

    def test_the_seed_is_repetition_zeros(self):
        self.assertEqual(sitemap.first_repetition_seed(_study(base_seed=11)),
                         1_100_000)

    def test_keeping_coordinates_draws_nothing(self):
        cfg = _study(placement="polygon", polygons_m=SQUARE,
                     shadowing_sigma_db=4.0).to_sim_config()
        plain = core.place_nodes(cfg, 50, "SF8", random.Random(3))
        kept = core.place_nodes(cfg, 50, "SF8", random.Random(3), xy={})
        self.assertEqual(plain, kept)


class TestWhereTheNodesAre(unittest.TestCase):

    def test_polygon_nodes_are_inside_and_at_their_distance(self):
        ring = [(-200.0, -800.0), (600.0, -800.0), (600.0, 300.0), (-200.0, 300.0)]
        data = _snap(_study(placement="polygon", polygons_m=[ring]), "SF8", 80)
        self.assertFalse(data["angles_for_display_only"])
        self.assertEqual(data["polygons_m"], [[list(p) for p in ring]])
        for nd in data["nodes"]:
            self.assertTrue(core.point_in_ring(nd["x_m"], nd["y_m"], ring))
            self.assertAlmostEqual(math.hypot(nd["x_m"], nd["y_m"]),
                                   nd["distance_m"], delta=0.02)

    def test_disc_angles_are_for_display_and_repeatable(self):
        s = _study(placement="disc")
        a, b = _snap(s, "SF8", 60), _snap(s, "SF8", 60)
        self.assertTrue(a["angles_for_display_only"])
        self.assertIsNone(a["polygons_m"])
        self.assertEqual(a, b)
        for nd in a["nodes"]:
            self.assertAlmostEqual(math.hypot(nd["x_m"], nd["y_m"]),
                                   nd["distance_m"], delta=0.02)
            self.assertLessEqual(nd["distance_m"], a["disc_radius_m"] + 0.1)
        # spread round the gateway, not lined up on one bearing
        angles = {round(math.atan2(nd["y_m"], nd["x_m"]), 1) for nd in a["nodes"]}
        self.assertGreater(len(angles), 30)


class TestReachAndLinks(unittest.TestCase):

    def test_reach_only_for_the_scenarios_data_rates(self):
        """US915 defines SF10, which these scenarios never use, and at a
        32-byte payload SF10 is not even legal there."""
        s = _study(scenarios=("SF7", "SF8", "SF9"))
        data = _snap(s, "SF8", 10)
        cfg = s.to_sim_config()
        self.assertEqual(sorted(data["reach_m"]), ["7", "8", "9"])
        for sf in (7, 8, 9):
            self.assertAlmostEqual(data["reach_m"][str(sf)],
                                   core.max_distance_m(cfg, cfg.sensitivity_dbm[sf]),
                                   delta=0.1)

    def test_a_fixed_rate_node_past_its_reach_is_below_sensitivity(self):
        s = _study(placement="polygon", tx_power_dbm=2.0,
                   polygons_m=[[(-3000.0, -3000.0), (3000.0, -3000.0),
                                (3000.0, 3000.0), (-3000.0, 3000.0)]])
        data = _snap(s, "SF8", 150)
        reach = data["reach_m"]["8"]
        far = sum(1 for nd in data["nodes"] if nd["distance_m"] > reach)
        self.assertGreater(far, 0)
        self.assertEqual(data["counts"]["below_sensitivity"], far)
        self.assertEqual({nd["link"] for nd in data["nodes"]
                          if nd["distance_m"] > reach}, {"below_sensitivity"})
        self.assertEqual(data["counts"]["unreachable"], 0)

    def test_an_adaptive_node_no_rate_reaches_is_unreachable(self):
        s = _study(placement="polygon", tx_power_dbm=2.0, scenarios=("MULTI",),
                   polygons_m=[[(-6000.0, -6000.0), (6000.0, -6000.0),
                                (6000.0, 6000.0), (-6000.0, 6000.0)]])
        data = _snap(s, "MULTI", 150)
        silent = [nd for nd in data["nodes"] if nd["link"] == "unreachable"]
        self.assertTrue(silent)
        self.assertEqual(data["counts"]["unreachable"], len(silent))
        for nd in silent:
            self.assertIsNone(nd["sf"])
            self.assertIsNone(nd["tx_power_dbm"])


def _rows(points, scenario="SF8"):
    # As much of a results row as the node count and the DER figure read.
    return [{"scenario": scenario, "n_nodes": n, "der_mean": d, "der_std": 0.01}
            for n, d in points]


class TestHowManyNodes(unittest.TestCase):

    def test_capacity_rounded_halves_up(self):
        s = _study()
        # crossing at 62.5: Python's round() would give 62
        n, how, cap = sitemap.map_node_count(s, _rows([(62, 0.905), (63, 0.895)]))
        self.assertEqual((n, how), (63, "capacity"))
        self.assertAlmostEqual(cap, 62.5)
        n, _how, _cap = sitemap.map_node_count(s, _rows([(60, 0.95), (70, 0.85)]))
        self.assertEqual(n, 65)

    def test_the_highlighted_scenario_decides(self):
        s = _study(scenarios=("SF7", "SF8"), highlight_scenario="SF8")
        rows = _rows([(10, 0.95), (20, 0.85)], "SF7") + _rows([(30, 0.95), (50, 0.85)])
        self.assertEqual(sitemap.map_node_count(s, rows)[0], 40)
        self.assertEqual(sitemap.map_scenario(s), "SF8")
        self.assertEqual(sitemap.map_scenario(_study(scenarios=("SF7", "SF8"))), "SF7")

    def test_a_chosen_count_wins(self):
        s = _study(site_map_nodes=17)
        self.assertEqual(sitemap.map_node_count(s, _rows([(60, 0.95), (70, 0.85)]))[:2],
                         (17, "site_map_nodes"))

    def test_no_crossing_no_count(self):
        self.assertEqual(sitemap.map_node_count(_study(), _rows([(10, 0.99), (20, 0.97)])),
                         (None, None, None))


class TempDir(unittest.TestCase):

    def setUp(self):
        self.out = tempfile.mkdtemp(prefix="loracap-map-")
        self.addCleanup(shutil.rmtree, self.out, True)


class TestWhatIsWritten(TempDir):

    ROWS = _rows([(60, 0.95), (70, 0.85)])

    def test_written_only_when_asked(self):
        self.assertEqual(sitemap.write_site_map(_study(), self.ROWS, out_dir=self.out),
                         (None, None))
        self.assertEqual(os.listdir(self.out), [])

    def test_written_with_its_record(self):
        s = _study(extra_figures=("site_map",))
        path, note = sitemap.write_site_map(s, self.ROWS, out_dir=self.out,
                                            provenance={"source": "test"})
        self.assertIsNone(note)
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        self.assertEqual(payload["provenance"], {"source": "test"})
        self.assertEqual(payload["study"], "t")
        data = payload["site_map"]
        self.assertEqual((data["scenario"], data["n_nodes"], data["nodes_from"]),
                         ("SF8", 65, "capacity"))
        self.assertEqual(len(data["nodes"]), 65)
        self.assertEqual(data["seed"], sitemap.first_repetition_seed(s))
        self.assertEqual(sitemap.load_site_map(self.out), data)

    def test_no_capacity_writes_nothing_and_says_what_to_do(self):
        s = _study(extra_figures=("site_map",))
        path, note = sitemap.write_site_map(s, _rows([(10, 0.99), (20, 0.97)]),
                                            out_dir=self.out)
        self.assertIsNone(path)
        self.assertIn("never crosses 0.9", note)
        self.assertIn("site_map_nodes", note)
        self.assertEqual(os.listdir(self.out), [])


    def test_a_map_from_an_earlier_run_does_not_survive(self):
        """`run` and the page write every run into the same outputs/."""
        asked = _study(extra_figures=("site_map",))
        for later in (_study(),                                   # no longer asked
                      asked):                                     # asked, no capacity
            sitemap.write_site_map(asked, self.ROWS, out_dir=self.out)
            self.assertTrue(os.path.isfile(os.path.join(self.out, sitemap.SITE_MAP_JSON)))
            sitemap.write_site_map(later, _rows([(10, 0.99), (20, 0.97)]), out_dir=self.out)
            self.assertEqual(os.listdir(self.out), [])


class TestTheFigure(TempDir):

    def _write(self, **over):
        s = _study(extra_figures=("site_map",), figure_formats=("png",), **over)
        path, note = sitemap.write_site_map(
            s, _rows([(60, 0.95), (70, 0.85)], sitemap.map_scenario(s)), out_dir=self.out)
        self.assertIsNotNone(path, note)
        return s

    def test_drawn_from_the_file_without_simulating(self):
        s = self._write(placement="polygon", polygons_m=SQUARE)
        with mock.patch.object(core, "place_nodes", side_effect=AssertionError("simulated")), \
                mock.patch.object(core, "run_single_sim", side_effect=AssertionError("simulated")):
            written = plotting.plot_study(s, _rows([(60, 0.95), (70, 0.85)]),
                                          out_dir=self.out)
        self.assertIn(os.path.join(self.out, "capacity_site_map.png"), written)

    def test_no_file_no_map(self):
        s = _study(extra_figures=("site_map",), figure_formats=("png",))
        written = plotting.plot_study(s, _rows([(60, 0.95), (70, 0.85)]),
                                      out_dir=self.out)
        self.assertEqual([os.path.basename(p) for p in written], ["capacity.png"])

    def _labels(self, s):
        fig = plotting.site_map_figure(s, sitemap.load_site_map(self.out))
        labels = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
        return fig, labels

    def test_the_legend_counts_what_is_drawn(self):
        s = self._write(placement="polygon", polygons_m=SQUARE)
        _fig, labels = self._labels(s)
        self.assertIn("SF8, 65 nodes", labels)
        self.assertIn("gateway", labels)
        self.assertIn("site boundary", labels)

    def test_a_reach_outside_the_frame_is_named(self):
        small = [[(-100.0, -100.0), (100.0, -100.0), (100.0, 100.0), (-100.0, 100.0)]]
        s = self._write(placement="polygon", polygons_m=small)
        _fig, labels = self._labels(s)
        reach = sitemap.load_site_map(self.out)["reach_m"]["8"]
        self.assertGreater(reach, 300)
        self.assertTrue(any(l.startswith("SF8 median reach") and
                            l.endswith("beyond the frame") for l in labels), labels)

    def test_disc_says_its_angles_are_for_display(self):
        s = self._write(placement="disc")
        fig, _labels = self._labels(s)
        self.assertIn("angles are drawn for display", fig.axes[0].get_title(loc="left"))

    def test_greyscale_has_no_colour(self):
        s = self._write(placement="polygon", polygons_m=SQUARE, scenarios=("MULTI",),
                        shadowing_sigma_db=6.0, figure_greyscale=True)
        fig, _labels = self._labels(s)
        ax = fig.axes[0]
        colours = [c for coll in ax.collections
                   for c in list(coll.get_facecolors()) + list(coll.get_edgecolors())]
        colours += [c for p in ax.patches for c in (p.get_facecolor(), p.get_edgecolor())]
        colours += [line.get_color() for line in ax.get_xgridlines()]
        self.assertTrue(ax.collections and ax.patches)
        for c in colours:
            r, g, b, a = matplotlib.colors.to_rgba(c)
            if a == 0:
                continue        # an unfilled circle's face, never drawn
            self.assertAlmostEqual(r, g, places=6, msg=c)
            self.assertAlmostEqual(g, b, places=6, msg=c)


class TestTheStudyField(unittest.TestCase):

    def errors(self, **over):
        return [e for e in study_mod.validate(_study(**over))[0]
                if "site_map_nodes" in e]

    def test_bad_counts_are_refused(self):
        for bad in (0, -3, 2.5, True, "10"):
            with self.subTest(value=bad):
                self.assertEqual(len(self.errors(site_map_nodes=bad)), 1)

    def test_good_counts_pass(self):
        for good in (None, 1, 40):
            self.assertEqual(self.errors(site_map_nodes=good,
                                         extra_figures=("site_map",)), [])

    def test_written_to_study_py(self):
        order = [f for f, _ in study_mod.STUDY_FIELD_ORDER]
        self.assertLess(order.index("extra_figures"), order.index("site_map_nodes"))


class TestReproduceWritesIt(TempStudy):

    def test_a_run_experiment_writes_the_map_with_its_provenance(self):
        exp = run_exp(name="mapped", overrides={"extra_figures": ("site_map",),
                                                "figure_formats": ("png",)},
                      figure=True)
        summary = reproduce.run_experiment("tiny", exp, root=self.root,
                                           log=lambda *_: None)
        d = os.path.join(self.root, "tiny", "outputs", "mapped")
        self.assertIn(os.path.join(d, sitemap.SITE_MAP_JSON), summary["written"])
        self.assertTrue(os.path.isfile(os.path.join(d, "capacity_site_map.png")))
        with open(os.path.join(d, sitemap.SITE_MAP_JSON), encoding="utf-8") as f:
            payload = json.load(f)
        self.assertEqual(payload["provenance"]["experiment"], "mapped")
        # the seed of the study that ran, the experiment's, not the base one
        self.assertEqual(payload["site_map"]["seed"], exp.base_seed * 100_000)


    def test_an_experiment_without_a_figure_writes_no_map(self):
        exp = run_exp(name="plain", overrides={"extra_figures": ("site_map",)})
        reproduce.run_experiment("tiny", exp, root=self.root, log=lambda *_: None)
        d = os.path.join(self.root, "tiny", "outputs", "plain")
        self.assertTrue(os.path.isfile(os.path.join(d, "results.json")))
        self.assertFalse(os.path.exists(os.path.join(d, sitemap.SITE_MAP_JSON)))


class TestTheWebForm(TempRoot):

    def test_the_count_reaches_study_py_and_comes_back(self):
        out = self.create(extra_figures=["site_map"], site_map_nodes=12)
        self.assertEqual(out["errors"], [])
        self.assertIn("site_map_nodes=12", out["study_py"])
        s = study_mod.load_study("formtest")
        self.assertEqual((tuple(s.extra_figures), s.site_map_nodes), (("site_map",), 12))

    def test_the_page_receives_its_default(self):
        """The Output tab fills the field from the study's own default, so
        the page opens without a count of its own invention."""
        defaults = server.api_bootstrap(None)["output_defaults"]
        self.assertIn("site_map_nodes", defaults)
        self.assertIsNone(defaults["site_map_nodes"])

    def test_untouched_it_is_not_written(self):
        self.assertNotIn("site_map_nodes=", self.create()["study_py"])

    def test_a_run_from_the_page_writes_the_map_into_the_zip(self):
        self.create(extra_figures=["site_map"], figure_formats=["png"],
                    node_counts=[3, 5, 10, 20], n_runs=2, sim_time_s=60.0,
                    site_map_nodes=8)
        server._run_worker("formtest", 50)
        self.assertEqual(server._job["state"], "done", server._job.get("error"))
        names = zipfile.ZipFile(io.BytesIO(server.study_zip("formtest"))).namelist()
        self.assertIn("formtest/outputs/site_map.json", names)
        self.assertIn("formtest/outputs/capacity_site_map.png", names)


class TestThePage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(PAGE, encoding="utf-8") as f:
            cls.html = f.read()

    def test_the_count_is_sent_only_with_the_map(self):
        self.assertIn("if($('o_site_map').checked && $('o_mapn').value!=='') "
                      "v.site_map_nodes=num('o_mapn',null);", self.html)

    def test_the_count_is_closed_without_the_map(self):
        self.assertIn("const mapOn=()=>{ $('o_mapn').disabled=!$('o_site_map').checked; };",
                      self.html)

    def test_the_file_is_listed(self):
        self.assertIn("if(v.extra_figures.includes('site_map')) f.push('site_map.json');",
                      self.html)


if __name__ == "__main__":
    unittest.main()
