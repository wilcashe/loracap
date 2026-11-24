"""A doubtful fit is flagged on its own (design item 38).

The checks that need a fitted model were made on the pair of fits: an
exponent was absurd only if one of the two was, and distance failed to
predict RSSI only if it failed for both. One sound fit covered the other.
CowNet's unbinned fit, n = 0.643 with R² = 0.06, passed in silence because
the binned fit had R² = 0.45, and adopting it on the page gave SF7 a reach of
453 209 078 m with no word from any check. Each fit is now checked on its
own, the page marks a doubtful one beside its button, and `check` looks at
the exponent and R² of any study, however its model was written.
"""
import json
import math
import random
import re
import shutil
import subprocess
import unittest

from tests import helpers
from tests.test_webui import PAGE

from loracap import pathloss, presets
from loracap import study as study_mod

GW_LAT, GW_LON = 5.0, -73.0
SQUARE = [[(-500.0, -500.0), (500.0, -500.0), (500.0, 500.0), (-500.0, 500.0)]]
M_PER_DEG_LAT = 111_195.0   # the haversine's own, at the radius pathloss uses


def _rows(points):
    """(distance north of the gateway in m, RSSI in dBm) -> the CSV, read as
    the page and the tool read one."""
    text = "rssi,latitude,longitude\n" + "".join(
        f"{v:.2f},{GW_LAT + d / M_PER_DEG_LAT:.8f},{GW_LON:.8f}\n" for d, v in points)
    return pathloss.read_csv(text, is_text=True)


def _line(n, distances, noise=0.0, seed=1):
    rng = random.Random(seed)
    return [(d, -40 - 10 * n * math.log10(d) + rng.gauss(0, noise)) for d in distances]


def _analyse(points):
    header, rows = _rows(points)
    return pathloss.analyse(header, rows, GW_LAT, GW_LON, tx_power_dbm=14)


def _by_label(res):
    return {f["label"]: f for f in res["fits"]}


class TestEachFitIsCheckedOnItsOwn(unittest.TestCase):

    def test_a_sound_campaign_raises_nothing(self):
        res = _analyse(_line(2.5, range(40, 800, 7), noise=3))
        self.assertEqual([w["kind"] for w in res["warnings"]
                          if w["kind"] in ("no_trend", "exponent_outside_measured",
                                           "negative_exponent", "implausible_exponent")], [])
        self.assertFalse(any(f["doubtful"] for f in res["fits"]))

    def test_one_sound_fit_no_longer_covers_the_other(self):
        # CowNet's shape: a node left standing at one spot for most of the
        # campaign, its packets scattered by fading, and a short walk out. The
        # binned fit sees the walk, the unbinned one mostly the scatter.
        points = _line(2.5, [35.0] * 400, noise=14, seed=3)
        points += _line(2.5, range(40, 400, 12), noise=1, seed=4)
        res = _analyse(points)
        fits = _by_label(res)
        unbinned, binned = fits["unbinned"], fits["binned (10 m)"]
        self.assertLess(unbinned["r_squared"], pathloss.NO_TREND_R2)
        self.assertGreater(binned["r_squared"], pathloss.NO_TREND_R2)
        self.assertTrue(unbinned["doubtful"])
        self.assertFalse(binned["doubtful"])
        flagged = [(w["kind"], w["fit"]) for w in res["warnings"] if "fit" in w]
        self.assertIn(("no_trend", "unbinned"), flagged)
        self.assertNotIn("binned (10 m)", [f for _k, f in flagged])
        msg = next(w["message"] for w in res["warnings"] if w.get("fit") == "unbinned")
        self.assertTrue(msg.startswith("The unbinned fit"), msg)

    def test_an_exponent_below_any_measured(self):
        res = _analyse(_line(1.0, range(40, 800, 7), noise=0.5))
        lo, hi = presets.measured_exponent_span()
        kinds = {(w["kind"], w["fit"]) for w in res["warnings"] if "fit" in w}
        self.assertEqual(kinds, {("exponent_outside_measured", "unbinned"),
                                 ("exponent_outside_measured", "binned (10 m)")})
        msg = res["warnings"][-1]["message"]
        self.assertIn(f"{lo:g} to {hi:g}", msg)
        self.assertIn("doi:10.3390/s24123877", msg)

    def test_the_stronger_kinds_keep_their_place(self):
        neg = _analyse(_line(-1.0, range(40, 800, 7), noise=0.5))
        self.assertEqual({w["kind"] for w in neg["warnings"] if "fit" in w},
                         {"negative_exponent"})
        steep = _analyse(_line(9.0, range(40, 800, 7), noise=0.5))
        self.assertEqual({w["kind"] for w in steep["warnings"] if "fit" in w},
                         {"implausible_exponent"})

    def test_the_span_is_the_tables(self):
        self.assertEqual(presets.measured_exponent_span(), (1.45, 5.97))


class TestCheckLooksAtTheModel(unittest.TestCase):

    def _check(self, **over):
        errors, warnings, _info = study_mod.validate(helpers.study(**over))
        return errors, warnings

    def _about_exponent(self, msgs):
        return [m for m in msgs if "path_loss_exponent" in m]

    def test_a_measured_exponent_passes(self):
        for n in (1.45, 2.188, 5.97):
            errors, warnings = self._check(path_loss_exponent=n)
            self.assertEqual(self._about_exponent(errors + warnings), [], n)

    def test_outside_the_measured_span_is_warned(self):
        for n in (0.643, 1.44, 5.98, 9.0):
            errors, warnings = self._check(path_loss_exponent=n)
            self.assertEqual(self._about_exponent(errors), [], n)
            self.assertEqual(len(self._about_exponent(warnings)), 1, n)

    def test_no_slope_is_an_error(self):
        # It also used to stop check itself, dividing by the exponent to
        # report each reach.
        for n in (0.0, -0.5):
            for placement in ("polygon", "disc"):
                errors, _w = self._check(path_loss_exponent=n, placement=placement,
                                         polygons_m=SQUARE)
                self.assertEqual(len(self._about_exponent(errors)), 1, (n, placement))

    def test_a_fit_without_a_trend_is_warned_even_with_its_sigma(self):
        # The older warning fired only with sigma at 0, so a fit with no trend
        # and its residual in shadowing_sigma_db passed.
        _e, warnings = self._check(path_loss_r_squared=0.05, shadowing_sigma_db=9.88)
        self.assertTrue(any("barely predicts" in w for w in warnings), warnings)
        _e, warnings = self._check(path_loss_r_squared=0.15, shadowing_sigma_db=9.88)
        self.assertFalse(any("barely predicts" in w for w in warnings), warnings)

    def test_the_reference_studies_are_not_touched(self):
        for name in ("iot4cows", "bor2016_sn1", "bor2016_sn3"):
            errors, warnings, _i = study_mod.validate(study_mod.load_study(name))
            self.assertEqual(self._about_exponent(errors + warnings), [], name)
            self.assertFalse(any("barely predicts" in w for w in warnings), name)


NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node is not installed")
class TestThePageMarksTheRow(unittest.TestCase):

    def test_only_the_doubtful_row_is_marked(self):
        with open(PAGE, encoding="utf-8") as f:
            html = f.read()
        show = re.search(r"(function showFit\(.*?\n\})", html, re.S).group(1)
        fit = {"min_distance_m": 30, "shadowing_sigma_db": 7.1, "path_loss_ref_db": 91.9,
               "n_points": 33}
        r = {"n_usable": 270, "n_kept": 270, "distance_min_m": 30, "distance_max_m": 380,
             "warnings": [], "equipment": None,
             "fits": [dict(fit, label="unbinned", path_loss_exponent=0.643,
                           r_squared=0.05, doubtful=True),
                      dict(fit, label="binned (10 m)", path_loss_exponent=2.188,
                           r_squared=0.45, doubtful=False)]}
        js = "\n".join([
            "function mk(tag,cls,text){ return {tag, cls:cls||'', text:text||'', kids:[],"
            " title:'', append(...x){this.kids.push(...x);}, appendChild(x){this.kids.push(x);"
            " return x;}, set innerHTML(v){this.kids=[];}}; }",
            "const tset=(el,k)=>{ el.text=k; return el; }, tsetx=tset, T=k=>k;",
            "const msgT=(k,t)=>mk('div','msg',t), msgEn=msgT, useFit=()=>{};",
            "const out=mk('div'), $=id=>out;",
            show,
            "showFit(%s);" % json.dumps(r),
            "const t=out.kids.find(x=>x.tag==='table');",
            "console.log(JSON.stringify(t.kids.slice(1).map(tr=>{",
            "  const cell=tr.kids[tr.kids.length-1];",
            "  return cell.kids.filter(x=>x.cls==='pill warn').map(x=>[x.text, x.title]); })));"])
        out = subprocess.run([NODE, "-e", js], capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout),
                         [[["doubtful", "See the warnings above the table."]], []])


if __name__ == "__main__":
    unittest.main()
