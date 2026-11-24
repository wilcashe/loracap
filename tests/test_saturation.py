"""Where the gateway stops delivering more traffic (design item 26).

The saturation experiment adds no physics. What it adds is a number per
scenario that a document can quote: the most messages delivered per hour
and where on the grid it happens. These tests pin how that number is read
off the saved results, that it is never claimed where the grid ends before
the traffic turns, and that the experiment itself stays what the README
says it is.
"""
import json
import os
import shutil
import tempfile
import unittest

from tests.helpers import require_matplotlib
require_matplotlib()

from loracap import analysis, plotting, reproduce
from loracap.reproduce import Experiment

import matplotlib.pyplot as plt

from tests import helpers

SIM = 1800.0       # half an hour simulated, so a rate per hour is twice a count


def _row(scen, n, sent, der, collided=0.0, demod=0.0):
    return {"scenario": scen, "n_nodes": n, "n_runs": 3,
            "transmitted_mean": sent, "der_mean": der, "der_std": 0.01,
            "der_runs": [der] * 3, "der_fleet_mean": der,
            "collided_mean": collided, "lost_signal_mean": 0.0,
            "lost_capacity_mean": demod}


# Delivered per half hour: 90, 160, 210 (the peak), 150, 80.
RISE_AND_FALL = [_row("SF8", 10, 100, 0.9), _row("SF8", 20, 200, 0.8),
                 _row("SF8", 40, 420, 0.5, collided=150, demod=60),
                 _row("SF8", 80, 750, 0.2, collided=300, demod=300),
                 _row("SF8", 160, 1600, 0.05, collided=320, demod=1200)]
# Still rising at the last node count.
STILL_RISING = [_row("ADR", 10, 100, 0.95), _row("ADR", 20, 200, 0.93),
                _row("ADR", 40, 400, 0.91)]


class TestDelivered(unittest.TestCase):

    def test_sent_times_der_per_hour(self):
        self.assertAlmostEqual(
            analysis.delivered_per_hour(RISE_AND_FALL[2], SIM), 420 * 0.5 * 2)

    def test_the_peak_and_its_neighbours(self):
        p = analysis.delivered_peak(RISE_AND_FALL, SIM)
        self.assertEqual((p["n_nodes"], p["below"], p["above"]), (40, 20, 80))
        self.assertAlmostEqual(p["per_hour"], 420.0)
        self.assertTrue(p["in_range"])

    def test_order_of_the_rows_does_not_matter(self):
        p = analysis.delivered_peak(list(reversed(RISE_AND_FALL)), SIM)
        self.assertEqual((p["n_nodes"], p["below"], p["above"]), (40, 20, 80))

    def test_the_edge_of_the_grid_is_not_a_peak(self):
        p = analysis.delivered_peak(STILL_RISING, SIM)
        self.assertEqual(p["n_nodes"], 40)
        self.assertFalse(p["in_range"])
        self.assertIsNone(p["above"])

    def test_nor_is_the_first_node_count(self):
        falling = [_row("SF8", 10, 100, 0.9), _row("SF8", 20, 120, 0.3)]
        self.assertFalse(analysis.delivered_peak(falling, SIM)["in_range"])

    def test_the_figure_uses_the_same_definition(self):
        s = helpers.study(scenarios=("SF8",), sim_time_s=SIM, send_interval_s=60.0)
        ax = plotting.delivered_figure(s, RISE_AND_FALL).axes[0]
        line = next(l for l in ax.get_lines() if l.get_label() == "SF8")
        self.assertEqual(list(line.get_ydata()),
                         [analysis.delivered_per_hour(r, SIM) for r in RISE_AND_FALL])
        plt.close("all")

    def test_the_figure_is_scaled_to_what_is_delivered(self):
        # The offered traffic at 160 nodes is 9600 an hour, the most
        # delivered 420. Scaled to the offered line the curve would sit
        # flat on the axis.
        s = helpers.study(scenarios=("SF8",), sim_time_s=SIM, send_interval_s=60.0)
        ax = plotting.delivered_figure(s, RISE_AND_FALL).axes[0]
        self.assertAlmostEqual(ax.get_ylim()[1], 1.15 * 420.0)
        plt.close("all")


class TestTicks(unittest.TestCase):

    def test_the_published_range_keeps_its_ticks(self):
        self.assertEqual(plotting._nice_log_ticks(3, 300),
                         [3, 5, 7, 10, 15, 20, 30, 50, 70, 100, 150, 200, 300])

    def test_a_wide_range_gets_one_tick_per_half_decade(self):
        self.assertEqual(plotting._nice_log_ticks(3, 3000),
                         [3, 10, 30, 100, 300, 1000, 3000])


class TestTheTable(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="loracap-sat-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.exp = Experiment(name="saturation", kind="run", description="test",
                              n_runs=3, sim_time_s=SIM, base_seed=1,
                              node_counts=(10, 20, 40, 80, 160),
                              scenarios=("SF8", "ADR"), tables=("saturation",))
        out = reproduce.experiment_dir("tiny", self.exp, None, self.root)
        os.makedirs(out)
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as f:
            json.dump({"results": RISE_AND_FALL + STILL_RISING}, f)
        with open(os.path.join(out, "capacity.json"), "w", encoding="utf-8") as f:
            json.dump({"der_threshold": 0.9, "capacity": {
                "SF8": {"capacity": 12.5, "ci_low": 11.0, "ci_high": 14.0},
                "ADR": {"capacity": None, "ci_low": None, "ci_high": None}}}, f)
        self.text = reproduce.render_tables("tiny", self.exp, root=self.root)

    def row(self, scen):
        return next(l for l in self.text.splitlines() if l.startswith(f"| {scen} |"))

    def test_peak_with_its_neighbours_and_losses_there(self):
        cells = [c.strip() for c in self.row("SF8").strip("|").split("|")]
        self.assertEqual(cells, ["SF8", "12.5", "[11.0, 14.0]", "420", "40 (20 to 80)",
                                 "35.7%", "14.3%", "75.0% (N = 160)"])

    def test_no_peak_claimed_at_the_edge(self):
        self.assertIn("40, edge of the grid: no peak in range", self.row("ADR"))
        self.assertIn("no crossing", self.row("ADR"))

    def test_says_how_the_peak_is_read_and_where_from(self):
        for needed in ("between the neighbouring node counts", "no interval",
                       "experiment `saturation`", "--only saturation"):
            self.assertIn(needed, self.text)


class TestTheExperiment(unittest.TestCase):
    """The experiment the README quotes, as the README describes it."""

    def setUp(self):
        exps = reproduce.load_manifest("iot4cows")
        self.exp = next(e for e in exps if e.name == "saturation")
        self.headline = next(e for e in exps if e.name == "headline")

    def test_it_carries_the_canonical_grid_on_to_3000(self):
        grid = list(self.headline.node_counts)
        counts = list(self.exp.node_counts)
        self.assertEqual(counts[:len(grid)], grid)
        self.assertEqual(counts[-1], 3000)
        tail = [grid[-1]] + counts[len(grid):]
        ratios = [b / a for a, b in zip(tail, tail[1:])]
        self.assertTrue(all(abs(r - 1.18) < 0.01 for r in ratios), ratios)

    def test_under_the_studys_own_rule_and_settings(self):
        self.assertEqual(self.exp.scenarios, ("SF8", "MULTI", "ADR"))
        self.assertEqual(set(self.exp.overrides), {"extra_figures"})
        self.assertEqual(len(self.exp.variants), 1)
        self.assertFalse(self.exp.variants[0].overrides)
        for k in ("n_runs", "sim_time_s", "base_seed", "n_bootstrap"):
            self.assertEqual(getattr(self.exp, k), getattr(self.headline, k), k)

    def test_its_table_and_figures(self):
        self.assertEqual(self.exp.tables, ("saturation",))
        self.assertTrue(self.exp.figure)
        self.assertEqual(tuple(self.exp.overrides["extra_figures"]),
                         ("delivered", "losses"))


if __name__ == "__main__":
    unittest.main()
