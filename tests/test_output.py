"""What a study asks to be drawn and written (design item 25).

The output options change no number, so what these tests pin is the three
ways they could still mislead. A default that quietly changes a figure or a
file a study already produced. A figure that turns counts into a rate with
the wrong time, or a share with the wrong total, so it disagrees with the
results it is drawn from. And a capacity table that leaves out the
conditions its numbers depend on.

They also pin the web side of the same options: the page starts from
Study's own defaults, the download holds the study and its run and nothing
else, and the form's required marks, terms and output fields stay in step
with the code they describe.
"""
import dataclasses
import io
import json
import os
import re
import shutil
import struct
import tempfile
import unittest
import zipfile
from unittest import mock

from tests import helpers
from tests.test_webui import TempRoot, form_values

from loracap import analysis, experiment, plotting, presets, study as study_mod
from loracap.study import DATA_FILES, FIGURE_FORMATS, FIGURE_KINDS
from webui import server

import matplotlib.pyplot as plt

PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
    helpers.__file__))), "webui", "index.html")


def _rows():
    """Two scenarios on four node counts, with every count a figure reads."""
    rows = []
    for scen, ders in (("SF8", (0.99, 0.95, 0.85, 0.60)),
                       ("ADR", (0.99, 0.97, 0.93, 0.80))):
        for n, d in zip((5, 20, 80, 320), ders):
            sent = n * 60.0           # one report a minute for an hour
            lost = sent * (1 - d)
            rows.append({
                "scenario": scen, "n_nodes": n, "n_runs": 3,
                "der_mean": d, "der_std": 0.01, "der_runs": [d, d, d],
                "der_fleet_mean": d, "der_fleet_runs": [d, d, d],
                "transmitted_mean": sent, "collided_mean": 0.6 * lost,
                "lost_signal_mean": 0.3 * lost, "lost_capacity_mean": 0.1 * lost,
                "nec_j_per_message_mean": 0.05 + 0.0001 * n,
            })
    return rows


def _study(**over):
    base = dict(scenarios=("SF8", "ADR"), node_counts=(5, 20, 80, 320),
                sim_time_s=3600.0, send_interval_s=60.0)
    base.update(over)
    return helpers.study(**base)


def _png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


class TempOut(unittest.TestCase):

    def setUp(self):
        self.out = tempfile.mkdtemp(prefix="loracap-out-")
        self.addCleanup(shutil.rmtree, self.out, True)

    def plot(self, study, rows=None):
        return [os.path.basename(p) for p in
                plotting.plot_study(study, rows or _rows(), out_dir=self.out)]


class TestTheDefaultsChangeNothing(TempOut):
    """A study written before these options existed draws and writes what it
    did then."""

    def test_only_the_der_figure_in_three_formats(self):
        self.assertEqual(sorted(self.plot(_study())),
                         ["capacity.pdf", "capacity.png", "capacity.svg"])

    def test_png_at_200_dpi_and_the_old_size(self):
        self.plot(_study())
        w, h = _png_size(os.path.join(self.out, "capacity.png"))
        fig = plotting.study_figure(_study(), _rows())
        self.assertEqual(tuple(fig.get_size_inches()), plotting.DEFAULT_SIZE_IN)
        plt.close(fig)
        # bbox_inches="tight" trims the margins, so the width sits a little
        # under 11 in times 200 dpi rather than on it.
        self.assertTrue(1800 < w <= 2200, w)

    def test_results_csv_and_no_tables(self):
        csv_path, json_path = experiment.write_results(_study(), _rows(),
                                                       out_dir=self.out)
        self.assertTrue(csv_path and os.path.isfile(csv_path))
        self.assertEqual(analysis.write_capacity_tables(
            _study(), {"SF8": {"capacity": 50.0, "ci_low": 45.0, "ci_high": 55.0}},
            out_dir=self.out), [])

    def test_the_study_defaults_are_the_ones_named_here(self):
        s = helpers.study()
        self.assertEqual(tuple(s.extra_figures), ())
        self.assertEqual(tuple(s.figure_formats), FIGURE_FORMATS)
        self.assertEqual(s.figure_dpi, 200)
        self.assertIsNone(s.figure_size_in)
        self.assertFalse(s.figure_greyscale)
        self.assertEqual(tuple(s.data_files), ("csv",))


class TestWhatIsWritten(TempOut):

    def test_each_extra_figure_in_each_chosen_format(self):
        s = _study(extra_figures=("delivered", "losses", "energy"),
                   radio="SX1272", figure_formats=("png", "pdf"))
        got = sorted(self.plot(s))
        want = sorted(f"capacity{k}.{x}" for k in ("", "_delivered", "_losses", "_energy")
                      for x in ("png", "pdf"))
        self.assertEqual(got, want)

    def test_the_resolution_reaches_the_png(self):
        self.plot(_study(figure_dpi=100, figure_formats=("png",)))
        w100, _ = _png_size(os.path.join(self.out, "capacity.png"))
        self.plot(_study(figure_dpi=300, figure_formats=("png",)))
        w300, _ = _png_size(os.path.join(self.out, "capacity.png"))
        self.assertAlmostEqual(w300 / w100, 3.0, delta=0.05)

    def test_the_size_reaches_every_figure(self):
        s = _study(figure_size_in=(3.5, 2.6))
        for fig in (plotting.study_figure(s, _rows()),
                    plotting.delivered_figure(s, _rows()),
                    plotting.losses_figure(s, _rows()),
                    plotting.energy_figure(dataclasses.replace(s, radio="SX1272"), _rows())):
            self.assertEqual(tuple(fig.get_size_inches()), (3.5, 2.6))
            plt.close(fig)

    def test_csv_left_out_when_not_asked_for(self):
        csv_path, _ = experiment.write_results(_study(data_files=()), _rows(),
                                               out_dir=self.out)
        self.assertIsNone(csv_path)
        self.assertFalse(os.path.exists(os.path.join(self.out, "results.csv")))

    def test_every_kind_has_a_figure_and_every_figure_a_kind(self):
        self.assertEqual(set(plotting.EXTRA_FIGURES), set(FIGURE_KINDS))


class TestTheFiguresAgreeWithTheResults(unittest.TestCase):
    """Every number a figure draws is one the results hold, worked out the
    way its axis says."""

    def tearDown(self):
        plt.close("all")

    def _line(self, ax, label):
        return next(l for l in ax.get_lines() if l.get_label() == label)

    def test_delivered_is_sent_times_der_per_hour(self):
        s = _study(sim_time_s=1800.0)       # half an hour simulated
        ax = plotting.delivered_figure(s, _rows()).axes[0]
        line = self._line(ax, "SF8")
        rows = [r for r in _rows() if r["scenario"] == "SF8"]
        want = [r["transmitted_mean"] * r["der_mean"] * 2 for r in rows]
        for got, w in zip(line.get_ydata(), want):
            self.assertAlmostEqual(got, w)

    def test_offered_is_every_node_at_the_interval(self):
        s = _study(send_interval_s=120.0)
        ax = plotting.delivered_figure(s, _rows()).axes[0]
        line = self._line(ax, "offered: every packet delivered")
        for n, y in zip(line.get_xdata(), line.get_ydata()):
            self.assertAlmostEqual(y, n * 30.0)

    def test_the_circle_sits_on_the_crossing(self):
        s = _study()
        ax = plotting.delivered_figure(s, _rows()).axes[0]
        rows = [r for r in _rows() if r["scenario"] == "SF8"]
        xc = analysis.crossing([r["n_nodes"] for r in rows],
                               [r["der_mean"] for r in rows], s.der_threshold)
        circles = [l for l in ax.get_lines() if len(l.get_xdata()) == 1]
        self.assertIn(round(xc, 6), [round(float(l.get_xdata()[0]), 6) for l in circles])
        labels = [t.get_text() for t in ax.texts]
        self.assertIn(f"SF8 {xc:.0f}", labels)

    def test_losses_are_shares_of_the_packets_sent(self):
        fig = plotting.losses_figure(_study(), _rows())
        ax = fig.axes[0]
        self.assertEqual(ax.get_title(loc="left"), "SF8")
        rows = [r for r in _rows() if r["scenario"] == "SF8"]
        for key, label in plotting.LOSS_CAUSES:
            line = self._line(ax, label)
            for got, r in zip(line.get_ydata(), rows):
                self.assertAlmostEqual(got, 100 * r[key] / r["transmitted_mean"])

    def test_the_loss_panels_share_one_axis(self):
        fig = plotting.losses_figure(_study(), _rows())
        lims = {ax.get_ylim() for ax in fig.axes if ax.get_visible() and ax.lines}
        self.assertEqual(len(lims), 1)

    def test_energy_is_in_millijoules(self):
        s = _study(radio="SX1272")
        ax = plotting.energy_figure(s, _rows()).axes[0]
        line = self._line(ax, "SF8")
        rows = [r for r in _rows() if r["scenario"] == "SF8"]
        for got, r in zip(line.get_ydata(), rows):
            self.assertAlmostEqual(got, 1000 * r["nec_j_per_message_mean"])

    def test_energy_refuses_results_without_energy(self):
        rows = [dict(r, nec_j_per_message_mean=None) for r in _rows()]
        with self.assertRaisesRegex(ValueError, "radio"):
            plotting.energy_figure(_study(radio="SX1272"), rows)


class TestGreyscale(unittest.TestCase):

    def tearDown(self):
        plt.close("all")

    def test_no_colour_left_on_the_der_figure(self):
        from matplotlib.colors import to_rgb
        s = _study(highlight_scenario="SF8", figure_greyscale=True)
        fig = plotting.study_figure(s, _rows())
        for ax in fig.axes:
            for line in ax.get_lines():
                r, g, b = to_rgb(line.get_color())
                self.assertTrue(r == g == b, line.get_color())

    def test_colour_kept_when_not_asked(self):
        s = _study(highlight_scenario="SF8")
        ax = plotting.study_figure(s, _rows()).axes[0]
        self.assertIn(s.highlight_color, [l.get_color() for l in ax.get_lines()])


class TestARunRedrawsAsItRan(unittest.TestCase):

    def test_time_and_interval_come_from_the_record(self):
        payload = {"study": {"sim_time_s": 900.0, "send_interval_s": 300.0},
                   "results": _rows()}
        s = experiment.as_run(_study(), payload)
        self.assertEqual((s.sim_time_s, s.send_interval_s), (900.0, 300.0))

    def test_a_record_without_them_leaves_the_study(self):
        s = _study()
        self.assertIs(experiment.as_run(s, {"results": []}), s)


class TestTheCapacityTables(unittest.TestCase):

    CAP = {"SF8": {"capacity": 62.4, "ci_low": 58.1, "ci_high": 66.0},
           "ADR": {"capacity": None, "ci_low": None, "ci_high": None}}

    def test_markdown_rows_and_conditions(self):
        s = _study(capture_threshold_db=3.0)
        text = analysis.capacity_table_markdown(s, self.CAP)
        self.assertIn("| SF8 | 62.4 | [58.1, 66.0] |", text)
        self.assertIn("| ADR | no crossing | - |", text)
        for needed in ("receiver rule lorasim", "capture threshold 3 dB",
                       "orthogonal", "DER = 0.9"):
            self.assertIn(needed, text)

    def test_the_rejection_table_is_named(self):
        s = _study(inter_sf_rejection="EIGNER2021_SX1301")
        text = analysis.capacity_table_markdown(s, self.CAP)
        self.assertIn("EIGNER2021_SX1301", text)
        self.assertNotIn("orthogonal", text)

    def test_latex_escapes_and_compiles_without_packages(self):
        s = _study(name="my_site", inter_sf_rejection="CROCE2020_SX1272")
        text = analysis.capacity_table_latex(s, self.CAP)
        self.assertIn(r"my\_site", text)
        self.assertIn(r"CROCE2020\_SX1272", text)
        self.assertIn(r"95\%", text)
        self.assertNotIn("booktabs", text)
        self.assertNotIn(r"\toprule", text)
        self.assertIn(r"SF8 & 62.4 & [58.1, 66.0] \\", text)

    def test_written_only_when_asked(self):
        out = tempfile.mkdtemp(prefix="loracap-tab-")
        self.addCleanup(shutil.rmtree, out, True)
        got = analysis.write_capacity_tables(_study(data_files=("latex",)),
                                             self.CAP, out_dir=out)
        self.assertEqual([os.path.basename(p) for p in got],
                         [analysis.CAPACITY_TABLE_TEX])


class TestTheOptionsAreChecked(unittest.TestCase):

    def errors(self, **over):
        return study_mod.validate(_study(**over))[0]

    def assertNames(self, field, **over):
        self.assertTrue(any(field in e for e in self.errors(**over)), over)

    def test_defaults_are_clean(self):
        self.assertEqual(self.errors(), [])

    def test_unknown_names(self):
        self.assertNames("extra_figures", extra_figures=("bars",))
        self.assertNames("figure_formats", figure_formats=("jpg",))
        self.assertNames("data_files", data_files=("xlsx",))

    def test_energy_needs_a_radio(self):
        self.assertNames("extra_figures", extra_figures=("energy",))
        self.assertEqual(self.errors(extra_figures=("energy",), radio="SX1272",
                                     tx_power_dbm=14.0), [])

    def test_no_format_is_refused(self):
        self.assertNames("figure_formats", figure_formats=())

    def test_resolution_and_size(self):
        for dpi in (0, -5, 150.5, True):
            self.assertNames("figure_dpi", figure_dpi=dpi)
        for size in ((0, 3), (3,), (3, -1), ("a", 2), 3.5, (True, 2)):
            self.assertNames("figure_size_in", figure_size_in=size)
        self.assertEqual(self.errors(figure_size_in=(3.5, 2.6)), [])

    def test_file_name_cannot_leave_the_folder(self):
        for bad in ("a/b", "../x", "", "/abs", "a\\b"):
            self.assertNames("figure_basename", figure_basename=bad)
        self.assertEqual(self.errors(figure_basename="fig-1_a.v2"), [])

    def test_axis_limits(self):
        for bad in ((10, 5), (0, 10), (None, 10), (5,)):
            self.assertNames("plot_full_xlim", plot_full_xlim=bad)
            self.assertNames("plot_zoom_xlim", plot_zoom_xlim=bad)
        self.assertNames("plot_zoom_ylim", plot_zoom_ylim=(1.0, 0.5))
        self.assertEqual(self.errors(plot_full_xlim=(3, 300),
                                     plot_zoom_ylim=(0.5, 1.0)), [])

    def test_runs_below_two(self):
        for n in (0, 1, 2.5):
            self.assertNames("n_runs", n_runs=n)
        self.assertEqual(self.errors(n_runs=2), [])

    def test_every_option_is_written_to_study_py(self):
        order = [f for f, _ in study_mod.STUDY_FIELD_ORDER]
        for f in ("extra_figures", "figure_formats", "figure_dpi",
                  "figure_size_in", "figure_greyscale", "data_files"):
            self.assertIn(f, order)


class TestTheWebOffersTheStudysOwnDefaults(unittest.TestCase):

    def setUp(self):
        self.boot = server.api_bootstrap(None)

    def test_output_defaults(self):
        s = helpers.study()
        # compared as the page receives them, through JSON
        got = json.loads(json.dumps(self.boot["output_defaults"]))
        for k, v in got.items():
            self.assertEqual(v, json.loads(json.dumps(getattr(s, k))), k)
        self.assertEqual(self.boot["figure_kinds"], list(FIGURE_KINDS))
        self.assertEqual(self.boot["data_files"], list(DATA_FILES))

    def test_every_radio_with_its_source(self):
        offered = {r["value"]: r for r in self.boot["radios"]}
        self.assertEqual(set(offered), set(presets.TX_CURRENT_MA))
        for k, r in offered.items():
            self.assertEqual(r["source"], presets.TX_CURRENT_SOURCE[k])
            self.assertEqual((r["low_dbm"], r["high_dbm"]),
                             (min(presets.TX_CURRENT_MA[k]), max(presets.TX_CURRENT_MA[k])))


class TestTheFormWritesTheOptions(TempRoot):

    def test_options_reach_study_py_and_come_back(self):
        out = self.create(radio="SX1272", tx_power_dbm=14.0,
                          extra_figures=["energy", "losses"],
                          figure_formats=["png"], figure_dpi=300,
                          figure_size_in=[3.5, 2.6], figure_greyscale=True,
                          data_files=["md", "latex"])
        self.assertEqual(out["errors"], [])
        s = study_mod.load_study("formtest")
        self.assertEqual(tuple(s.extra_figures), ("energy", "losses"))
        self.assertEqual(tuple(s.figure_size_in), (3.5, 2.6))
        self.assertEqual((s.figure_dpi, s.figure_greyscale, s.radio),
                         (300, True, "SX1272"))
        self.assertEqual(tuple(s.data_files), ("md", "latex"))
        # written as tuples, as a study written by hand would have them
        for text in ("extra_figures=('energy', 'losses')", "figure_size_in=(3.5, 2.6)",
                     "data_files=('md', 'latex')", "figure_formats=('png',)"):
            self.assertIn(text, out["study_py"])

    def test_untouched_options_are_not_written(self):
        out = self.create()
        for f in ("extra_figures", "figure_formats", "figure_dpi",
                  "figure_size_in", "figure_greyscale", "data_files", "radio"):
            self.assertNotIn(f + "=", out["study_py"])


class TestTheDownload(TempRoot):

    def test_study_and_run_files_only(self):
        self.create()
        out = os.path.join(self.root, "formtest", "outputs")
        os.makedirs(os.path.join(out, "someexperiment"))
        for name in ("results.json", "capacity.json", "capacity.png"):
            with open(os.path.join(out, name), "w", encoding="utf-8") as f:
                f.write("{}")
        with open(os.path.join(out, "someexperiment", "results.json"), "w",
                  encoding="utf-8") as f:
            f.write("{}")
        names = zipfile.ZipFile(io.BytesIO(server.study_zip("formtest"))).namelist()
        self.assertEqual(sorted(names), sorted([
            "formtest/study.py", "formtest/outputs/results.json",
            "formtest/outputs/capacity.json", "formtest/outputs/capacity.png"]))

    def test_refused_before_a_run(self):
        self.create()
        with self.assertRaisesRegex(ValueError, "Run it first"):
            server.study_zip("formtest")

    def test_refused_outside_studies(self):
        # Refused for the name itself, before any file is looked at: a study
        # placed outside studies/ with a run in it must not be reachable.
        outside = os.path.join(os.path.dirname(self.root), "escaped", "outputs")
        os.makedirs(outside, exist_ok=True)
        self.addCleanup(shutil.rmtree, os.path.dirname(outside), True)
        with open(os.path.join(outside, "results.json"), "w", encoding="utf-8") as f:
            f.write("{}")
        for bad in ("../escaped", "a/b", "", ".hidden"):
            with self.assertRaisesRegex(ValueError, "letters, digits|Invalid study name"):
                server.study_zip(bad)


def _page():
    with open(PAGE, encoding="utf-8") as f:
        return f.read()


def _label(html, control_id):
    m = re.search(r'<label for="%s"[^>]*>(.*?)</label>' % re.escape(control_id), html, re.S)
    return m.group(1) if m else None


class TestThePage(unittest.TestCase):
    """Static checks of the page, since the suite has no browser. The
    behaviour (modes, summaries, jumps to hidden fields) was checked in a
    headless browser and is recorded in the design log."""

    def setUp(self):
        self.html = _page()

    def test_required_fields_are_marked(self):
        req = '<span class="req" aria-hidden="true">*</span>'
        for cid in ("f_name", "f_lat", "f_lon", "f_dwell"):
            self.assertIn(req, _label(self.html, cid) or "", cid)
            if cid != "f_dwell":
                self.assertRegex(self.html, r'id="%s"[^>]*aria-required="true"' % cid)
        for group in ("Site boundary (KML)", "Propagation model", "Scenarios"):
            self.assertRegex(self.html, re.escape(group) + r"\s*" + re.escape(req))

    def test_optional_fields_are_not_marked(self):
        for cid in ("f_site", "f_tx", "f_pl", "f_int", "f_th"):
            self.assertNotIn('class="req"', _label(self.html, cid) or "", cid)

    def test_site_example_is_not_the_reference_study(self):
        # The form is for any site, so its examples are not the one study
        # the repository ships.
        self.assertNotIn("Guamal", self.html)
        self.assertNotIn("3.91915", self.html)

    def test_every_marked_term_has_a_definition(self):
        terms = set(re.findall(r"^\s+'?([A-Za-z ]+)'?:'", self.html.split(
            "const TERMS={")[1].split("};")[0], re.M))
        marked = re.search(r"const TERM_RE=/\\b\(([^)]+)\)", self.html).group(1)
        for t in marked.split("|") + ["SF"]:
            self.assertIn(t, terms, t)

    def test_every_output_field_has_a_control_and_a_check_name(self):
        keys = re.search(r"const OUTPUT_KEYS=\[(.*?)\];", self.html, re.S).group(1)
        keys = re.findall(r"'(\w+)'", keys)
        fields = re.search(r"const FIELDS=\{(.*?)\n\};", self.html, re.S).group(1)
        for k in keys:
            m = re.search(r"\b%s:\['(\w+)'" % k, fields)
            self.assertIsNotNone(m, k)
            self.assertIn('id="%s"' % m.group(1), self.html, k)
        # Every output field the validator can name is shown on the Output
        # tab too. Greyscale is a plain switch and has nothing to check.
        for k in server.OUTPUT_FIELDS:
            if k != "figure_greyscale":
                self.assertIn(k, keys)

    def test_formats_on_the_page_are_the_studys(self):
        self.assertEqual(re.findall(r'class="o_fmt" id="o_fmt_(\w+)"', self.html),
                         list(FIGURE_FORMATS))
        self.assertEqual(re.findall(r'class="o_fig" value="(\w+)"', self.html),
                         list(FIGURE_KINDS))
        self.assertEqual(re.findall(r'class="o_data" value="(\w+)"', self.html),
                         list(DATA_FILES))

    def test_propagation_opens_as_not_set(self):
        # "entered by hand" on a page nobody has typed in described the
        # defaults as the user's decision.
        boot = self.html.split("async function boot(){")[1].split("\n}\n")[0]
        self.assertIn("setOrigin('unset');", boot)
        self.assertNotIn("setOrigin('manual');", boot.split("['f_n','f_ref','f_d0']")[0])

    def test_every_advanced_block_is_named(self):
        names = re.findall(r'class="adv" id="(\w+)" data-name="([^"]+)"', self.html)
        self.assertEqual(len(names), 6)
        for _id, name in names:
            self.assertTrue(name.startswith("advanced "), name)


if __name__ == "__main__":
    unittest.main()
