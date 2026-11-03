"""Figures that compare configurations, and reference marks on a figure
(design item 20).

A figure is held to the same rule as a table: every number on it comes from
a file an experiment wrote. These tests pin the three ways a figure can
quietly break that rule. A capacity printed on a panel that the plotting code
recomputed instead of reading, so the figure and the table could disagree. A
reference mark outside the axis drawn at the edge, where it reads as a value
it is not. And a panel whose title does not say which receiver rule and
threshold produced it, when every capacity on it is conditional on both.
"""
import os
import unittest

from tests import helpers  # noqa: F401  (puts the package on sys.path)

from loracap import plotting, reproduce, study as study_mod
from loracap.reproduce import ManifestError, Variant
from tests.test_reproduce import TempStudy, run_exp

import matplotlib.pyplot as plt


def _rows(scenario, points):
    """Rows as `results.json` holds them, from (n, der) pairs."""
    return [{"scenario": scenario, "n_nodes": n, "der_mean": d,
             "der_std": 0.01} for n, d in points]


CURVE = [(5, 0.99), (20, 0.97), (80, 0.88), (320, 0.70)]


class TestPanelsAndMarksAreChecked(unittest.TestCase):
    """A bad figure declaration is a manifest error, found before the run."""

    PAIR = (Variant("a", "rule a"), Variant("b", "rule b"))

    def assertRejected(self, exp):
        with self.assertRaises(ManifestError):
            reproduce.check_manifest([exp])

    def test_panels_and_marks_pass_when_well_formed(self):
        reproduce.check_manifest([run_exp(
            figure=True, variants=self.PAIR, figure_panels=("a", "b"),
            figure_marks=((52.3, "other simulator"),))])

    def test_several_variants_still_need_panels(self):
        self.assertRejected(run_exp(figure=True, variants=self.PAIR))

    def test_a_panel_must_be_a_variant(self):
        self.assertRejected(run_exp(figure=True, variants=self.PAIR,
                                    figure_panels=("a", "c")))

    def test_a_panel_appears_once(self):
        self.assertRejected(run_exp(figure=True, variants=self.PAIR,
                                    figure_panels=("a", "a")))

    def test_panels_need_figure(self):
        self.assertRejected(run_exp(variants=self.PAIR,
                                    figure_panels=("a", "b")))

    def test_marks_need_figure(self):
        self.assertRejected(run_exp(figure_marks=((10.0, "x"),)))

    def test_a_mark_is_a_positive_count_and_a_label(self):
        for bad in ((0.0, "x"), (-5.0, "x"), (10.0, ""), (10.0, "  "),
                    ("10", "x"), (10.0,), [10.0, "x"]):
            with self.subTest(mark=bad):
                self.assertRejected(run_exp(figure=True, figure_marks=(bad,)))

    def test_panels_only_on_a_run(self):
        exp = reproduce.Experiment(
            name="v", kind="validate", description="test", n_runs=3,
            sim_time_s=300.0, base_seed=7, node_counts=(5, 20),
            options={"scenario": "SF8"}, figure=True, figure_panels=("",))
        self.assertRejected(exp)


class TestMarks(unittest.TestCase):

    def setUp(self):
        self.fig, self.ax = plt.subplots()

    def tearDown(self):
        plt.close(self.fig)

    def test_a_mark_outside_the_axis_is_left_out(self):
        drawn = plotting._draw_marks(
            self.ax, ((52.3, "inside"), (120.0, "outside")), (20, 100),
            (0.75, 1.0))
        self.assertEqual(drawn, [(52.3, "inside")])
        texts = [t.get_text() for t in self.ax.texts]
        self.assertEqual(texts, ["inside (52.3)"])
        self.assertEqual(len(self.ax.lines), 1)

    def test_the_label_carries_the_value(self):
        """A mark read off a log axis is not precise enough to quote, so the
        number is printed with it."""
        plotting._draw_marks(self.ax, ((64.0, "paper"),), (10, 300), (0, 1))
        self.assertIn("(64)", self.ax.texts[0].get_text())


class TestPanelsFigure(unittest.TestCase):

    def _study(self, **kw):
        return study_mod.Study(
            name="p", region="US915", bw_khz=125, chip="SX1308",
            payload_bytes=32, scenarios=("SF8", "MULTI"),
            spreading_factors=(7, 8, 9, 10), placement="disc",
            path_loss_source="test", path_loss_exponent=2.16,
            path_loss_ref_db=130.3, path_loss_ref_distance_m=100.0,
            min_valid_distance_m=30.0, node_counts=(5, 20, 80, 320),
            highlight_scenario="SF8", **kw)

    def _panels(self):
        # The capacity in each panel's file is deliberately NOT where its
        # curve crosses 0.9 (about 70 nodes), so a label recomputed from the
        # curve is told apart from one read from the file.
        return [
            {"study": self._study(), "label": "rule a",
             "rows": _rows("SF8", CURVE) + _rows("MULTI", CURVE),
             "capacity": {"SF8": {"capacity": 42.0, "ci_low": 40.0,
                                  "ci_high": 44.0},
                          "MULTI": {"capacity": None, "ci_low": None,
                                    "ci_high": None}}},
            {"study": self._study(capture_threshold_db=1.0,
                                  receiver_model="lock"),
             "label": "rule b",
             "rows": _rows("SF8", [(n, d - 0.1) for n, d in CURVE]),
             "capacity": {"SF8": {"capacity": 17.0, "ci_low": 15.0,
                                  "ci_high": 19.0}}},
        ]

    def setUp(self):
        self.fig = plotting.panels_figure(self._panels())
        self.axes = self.fig.axes

    def tearDown(self):
        plt.close(self.fig)

    def labels(self, ax):
        return [t.get_text() for t in ax.texts]

    def test_capacity_labels_come_from_the_file(self):
        self.assertEqual(self.labels(self.axes[0]), ["42"])
        self.assertEqual(self.labels(self.axes[1]), ["17"])

    def test_a_curve_that_never_crosses_gets_no_label(self):
        """MULTI's file has no capacity. Printing a number for it would be
        inventing one."""
        self.assertNotIn("70", self.labels(self.axes[0]))
        self.assertEqual(len(self.labels(self.axes[0])), 1)

    def test_titles_state_the_rule_and_threshold(self):
        self.assertEqual(self.axes[0].get_title(loc="left"),
                         "rule a, 6 dB capture threshold")
        self.assertEqual(self.axes[1].get_title(loc="left"),
                         "rule b, 1 dB capture threshold")

    def test_panels_share_one_der_axis(self):
        """Equal heights must mean equal DER, or the eye compares panels
        wrongly."""
        self.assertEqual(self.axes[0].get_ylim(), self.axes[1].get_ylim())
        lo, hi = self.axes[0].get_ylim()
        self.assertEqual(hi, 1.0)
        # The lowest band, 0.70 - 0.1 - 0.01, must be inside the axis.
        self.assertLessEqual(lo, 0.59)

    def test_a_lossless_grid_still_gets_an_axis_with_height(self):
        panel = {"rows": [dict(r, der_mean=1.0, der_std=0.0)
                          for r in _rows("SF8", CURVE)]}
        self.assertEqual(plotting._panel_ylim([panel], (5, 320)), (0.95, 1.0))

    def test_the_interval_is_drawn_along_the_threshold(self):
        bars = [l for l in self.axes[0].lines
                if list(l.get_xdata()) == [40.0, 44.0]]
        self.assertEqual(len(bars), 1)
        self.assertEqual(list(bars[0].get_ydata()), [0.9, 0.9])


class TestPanelFigureFromAnExperiment(TempStudy):
    """End to end: the run writes one figure for the experiment, the replot
    redraws it from the saved files, and no variant writes its own."""

    def test_run_and_replot_write_one_panel_figure(self):
        exp = run_exp(name="pair", figure=True, n_runs=2,
                      variants=(Variant("a", "rule a"),
                                Variant("b", "rule b",
                                        {"receiver_model": "lock"})),
                      figure_panels=("a", "b"))
        quiet = dict(root=self.root, log=lambda *_: None)
        summary = reproduce.run_experiment("tiny", exp, **quiet)
        out = os.path.join(self.root, "tiny", "outputs", "pair")
        figs = sorted(p for p in summary["written"]
                      if p.endswith((".png", ".svg", ".pdf")))
        self.assertEqual([os.path.dirname(p) for p in figs], [out] * 3)
        for v in ("a", "b"):
            self.assertFalse(any(f.endswith((".png", ".svg", ".pdf"))
                                 for f in os.listdir(os.path.join(out, v))))
        for p in figs:
            os.remove(p)

        with open(os.path.join(self.root, "tiny", "experiments.py"), "w") as f:
            f.write("from loracap.reproduce import Experiment, Variant\n"
                    f"EXPERIMENTS = [{exp!r}]\n")
        redrawn = reproduce.replot("tiny", root=self.root, log=lambda *_: None)
        self.assertEqual(sorted(redrawn), figs)
        self.assertTrue(all(os.path.exists(p) for p in figs))

    def test_panel_data_reads_the_saved_capacity(self):
        exp = run_exp(name="pair", figure=True, n_runs=2,
                      variants=(Variant("a", "rule a"),
                                Variant("b", "rule b",
                                        {"receiver_model": "lock"})),
                      figure_panels=("b", "a"))
        reproduce.run_experiment("tiny", exp, root=self.root, plot=False,
                                 log=lambda *_: None)
        base = study_mod.load_study("tiny", self.root)
        panels = reproduce.panel_data("tiny", base, exp, root=self.root)
        # In the order the manifest names them, not the variants' order.
        self.assertEqual([p["label"] for p in panels], ["rule b", "rule a"])
        self.assertEqual(panels[0]["study"].receiver_model, "lock")
        for p, v in zip(panels, ("b", "a")):
            saved = reproduce._load_json(os.path.join(
                self.root, "tiny", "outputs", "pair", v, "capacity.json"))
            self.assertEqual(p["capacity"], saved["capacity"])


if __name__ == "__main__":
    unittest.main()
