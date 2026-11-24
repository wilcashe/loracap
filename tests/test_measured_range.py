"""Where the model stops being measured (design item 39).

A field fit is a straight line through the distances that were measured.
Past the farthest of them every received power is that line extrapolated,
and nothing said so. CowNet's campaign stops at 380 m while its paddock
reaches 401 m, and with the unbinned fit adopted the checks reported SF7
reaching 453 209 078 m and called range no constraint. `max_measured_distance_m`
records how far the model was measured. It changes no draw and no result:
`check`, the page and the site map use it to say what lies beyond it.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from tests import helpers
from tests.test_webui import PAGE

import matplotlib
matplotlib.use("Agg")

from loracap import pathloss, plotting, sitemap
from loracap import study as study_mod
from webui import server

SQUARE = [[(-500.0, -500.0), (500.0, -500.0), (500.0, 500.0), (-500.0, 500.0)]]
CORNER = 707   # the square's farthest point from the gateway, rounded
NOTE = "(an extrapolation: the measurements stop at"


def _check(**over):
    return study_mod.validate(helpers.study(**over))


class TestTheField(unittest.TestCase):

    def test_unknown_by_default_and_silent(self):
        self.assertIsNone(study_mod.Study.__dataclass_fields__[
            "max_measured_distance_m"].default)
        errors, warnings, info = _check(placement="polygon", polygons_m=SQUARE)
        self.assertEqual(errors, [])
        self.assertFalse(any("measurement" in m for m in warnings + info))
        self.assertFalse(any(NOTE in m for m in info))

    def test_what_is_refused(self):
        for bad in (0, -5.0, 20.0, 30.0, True, "380"):
            errors, _w, _i = _check(max_measured_distance_m=bad)
            self.assertTrue(any("max_measured_distance_m" in e for e in errors), bad)
        # True is 1, past a floor under a metre, and still no distance.
        errors, _w, _i = _check(max_measured_distance_m=True, min_valid_distance_m=0.5)
        self.assertTrue(any("max_measured_distance_m" in e for e in errors))

    def test_a_distance_past_the_floor_passes(self):
        for good in (31, 380.4, 2210.0):
            errors, _w, _i = _check(max_measured_distance_m=good)
            self.assertEqual(errors, [], good)

    def test_a_reference_beyond_the_measurements(self):
        _e, warnings, _i = _check(max_measured_distance_m=80.0)
        self.assertTrue(any("d0 = 100 m lies beyond the farthest measurement, at 80 m"
                            in w for w in warnings), warnings)
        _e, warnings, _i = _check(max_measured_distance_m=100.0)
        self.assertFalse(any("lies beyond the farthest measurement" in w
                             for w in warnings), warnings)


class TestTheSite(unittest.TestCase):

    def test_a_site_past_the_measurements_is_warned(self):
        _e, warnings, _i = _check(placement="polygon", polygons_m=SQUARE,
                                  max_measured_distance_m=500.0)
        hit = [w for w in warnings if w.startswith("The site extends")]
        self.assertEqual(len(hit), 1, warnings)
        self.assertIn(f"{CORNER} m from the gateway", hit[0])
        self.assertIn("farthest measurement at 500 m", hit[0])

    def test_a_site_inside_them_is_not(self):
        _e, warnings, _i = _check(placement="polygon", polygons_m=SQUARE,
                                  max_measured_distance_m=CORNER + 1.0)
        self.assertFalse(any(w.startswith("The site extends") for w in warnings))

    def test_each_reach_past_them_says_so(self):
        _e, _w, info = _check(placement="polygon", polygons_m=SQUARE,
                              max_measured_distance_m=CORNER + 1.0)
        lines = [m for m in info if m.startswith("  SF")]
        self.assertEqual(len(lines), 4)
        # Guamal's model reaches past 700 m at every data rate.
        for line in lines:
            self.assertIn(f"{NOTE} {CORNER + 1} m)", line)
        _e, _w, info = _check(placement="polygon", polygons_m=SQUARE,
                              max_measured_distance_m=100_000.0)
        self.assertFalse(any(NOTE in m for m in info))

    def test_a_disc_wider_than_the_measurements(self):
        _e, warnings, _i = _check(placement="disc", scenarios=("SF8", "SF10"),
                                  max_measured_distance_m=500.0)
        hit = [w for w in warnings if "places its nodes on a disc" in w]
        self.assertEqual([w.split()[0] for w in hit], ["SF8", "SF10"])
        _e, warnings, _i = _check(placement="disc", max_measured_distance_m=100_000.0)
        self.assertFalse(any("places its nodes on a disc" in w for w in warnings))


class TestWhereItIsWritten(unittest.TestCase):

    def test_study_py_round_trip(self):
        values = dict(name="rt", max_measured_distance_m=380.4)
        text = study_mod.render_study_module(values, use_site_polygon=False)
        self.assertIn("max_measured_distance_m=380.4", text)
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "rt"))
            with open(os.path.join(d, "rt", "study.py"), "w", encoding="utf-8") as f:
                f.write(text)
            self.assertEqual(study_mod.load_study("rt", root=d).max_measured_distance_m,
                             380.4)
        # Unknown stays unknown.
        text = study_mod.render_study_module(dict(name="rt", max_measured_distance_m=None),
                                             use_site_polygon=False)
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "rt"))
            with open(os.path.join(d, "rt", "study.py"), "w", encoding="utf-8") as f:
                f.write(text)
            self.assertIsNone(study_mod.load_study("rt", root=d).max_measured_distance_m)

    def test_the_fit_tools_snippet(self):
        fit = {"path_loss_exponent": 2.188, "path_loss_ref_db": 91.85,
               "path_loss_ref_distance_m": 100.0, "min_distance_m": 30.0,
               "max_distance_m": 380.37, "r_squared": 0.446, "shadowing_sigma_db": 7.11,
               "label": "binned (10 m)", "n_points": 33}
        self.assertIn("    max_measured_distance_m=380.4,\n", pathloss.study_snippet(fit))

    def test_iot4cows_states_its_range(self):
        s = study_mod.load_study("iot4cows")
        self.assertEqual(s.max_measured_distance_m, 2210.0)
        self.assertIn("30 m to 2.21 km", s.path_loss_source)
        errors, warnings, info = study_mod.validate(s)
        self.assertEqual(errors, [])
        self.assertFalse(any(w.startswith("The site extends") for w in warnings))
        notes = {m.split(":")[0].strip() for m in info if m.startswith("  SF") and NOTE in m}
        self.assertEqual(notes, {"SF8", "SF9", "SF10"})

    def test_the_template_leaves_it_unknown(self):
        with open(os.path.join(os.path.dirname(PAGE), "..", "studies", "_template",
                               "study.py"), encoding="utf-8") as f:
            self.assertIn("max_measured_distance_m=None,", f.read())


class TestTheServer(unittest.TestCase):

    def test_the_reach_table_marks_an_extrapolation(self):
        values = dict(name="t", region="US915", bw_khz=125, chip="SX1308",
                      payload_bytes=32, scenarios=["SF7", "SF8"], placement="disc",
                      path_loss_source="test", max_measured_distance_m=2000.0,
                      **helpers.GUAMAL_STUDY_FIELDS)
        r = server.api_validate({"values": values, "rings": None})
        self.assertEqual(r["errors"], [])
        by = {x["scenario"]: x for x in r["reach"]}
        self.assertLess(by["SF7"]["reach_m"], 2000)
        self.assertGreater(by["SF8"]["reach_m"], 2000)
        self.assertEqual([by["SF7"]["extrapolated"], by["SF8"]["extrapolated"]],
                         [False, True])
        self.assertEqual(by["SF8"]["measured_to_m"], 2000.0)

    def test_the_range_under_the_field(self):
        lim = server.field_limits()["max_measured_distance_m"]
        self.assertEqual(lim["gt"], 0)


NODE = shutil.which("node")


class TestThePage(unittest.TestCase):

    def setUp(self):
        with open(PAGE, encoding="utf-8") as f:
            self.html = f.read()

    def test_the_field_and_what_fills_it(self):
        self.assertRegex(self.html, r'<input id="f_maxd" type="number" step="any" value="">')
        self.assertIn("max_measured_distance_m:num('f_maxd',null),", self.html)
        self.assertIn("$('f_maxd').value=f.max_distance_m.toFixed(1);", self.html)
        # An environment model was measured nowhere.
        terrain = re.search(r"\n(async )?function applyTerrain\(.*?\n\}", self.html, re.S).group(0)
        self.assertIn("$('f_maxd').value='';", terrain)

    @unittest.skipUnless(NODE, "Node is not installed")
    def test_the_reach_table_marks_the_row(self):
        body = re.search(r"r\.reach\.forEach\(x=>\{(.*?)\n      \}\);", self.html, re.S).group(1)
        js = "\n".join([
            "function mk(tag,cls,text){ return {tag, cls:cls||'', text:text||'', kids:[],"
            " title:'', append(...x){this.kids.push(...x);}, appendChild(x){this.kids.push(x);"
            " return x;}}; }",
            "const tset=(el,k)=>{ el.text=k; return el; };",
            "const T=(k,v)=>k.replace(/\\{(\\w+)\\}/g,(m,n)=>v[n]);",
            "const t=mk('table');",
            "[{scenario:'SF7', reach_m:1820, covers:true, extrapolated:false, measured_to_m:2000},",
            " {scenario:'SF8', reach_m:2371, covers:true, extrapolated:true, measured_to_m:2000}]",
            ".forEach(x=>{" + body + "\n});",
            "console.log(JSON.stringify(t.kids.map(tr=>tr.kids[1].kids.map(p=>[p.text,p.title]))));"])
        r = subprocess.run([NODE, "-e", js], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout),
                         [[], [["extrapolated", "Beyond the farthest measurement, 2000 m."]]])


class TestTheMap(unittest.TestCase):

    def setUp(self):
        self.s = helpers.study(placement="polygon", polygons_m=SQUARE,
                               extra_figures=("site_map",), site_map_nodes=20,
                               max_measured_distance_m=2000.0, scenarios=("SF7", "SF8"))

    def _labels(self, data):
        fig = plotting.site_map_figure(self.s, data)
        return [t.get_text() for t in fig.axes[0].get_legend().get_texts()]

    def test_recorded_and_drawn(self):
        data = sitemap.snapshot(self.s, "SF8", 20)
        self.assertEqual(data["max_measured_distance_m"], 2000.0)
        labels = self._labels(data)
        self.assertIn("farthest measurement, 2.00 km, beyond the frame", labels)
        reach = [l for l in labels if "median reach" in l]
        self.assertEqual(len(reach), 2)
        self.assertNotIn("extrapolated", reach[0])
        self.assertIn(", extrapolated, beyond the frame", reach[1])

    def test_a_map_from_before_draws_as_it_did(self):
        data = sitemap.snapshot(self.s, "SF8", 20)
        data.pop("max_measured_distance_m")
        labels = self._labels(data)
        self.assertFalse(any("farthest measurement" in l or "extrapolated" in l
                             for l in labels), labels)


if __name__ == "__main__":
    unittest.main()
