"""Fading apart from shadowing in a field fit (design item 40).

A fit's residual holds two spreads the simulator draws apart: shadowing,
fixed for each node, and fading, drawn afresh for every packet. CowNet put
a fit's residual into shadowing and a figure from its standing node into
fading, about 11.2 dB together, while its data show about 8.8 dB in all. A
position measured more than once shows fading alone, as the spread between
its packets. Pooled over every such position it gives fading, and a third fit,
over each position once with the mean of its packets, leaves shadowing.
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

from loracap import pathloss

GW_LAT, GW_LON = 5.0, -73.0
M_PER_DEG_LAT = 111_194.93   # the radius the haversine uses, in metres per degree


def _csv(rows):
    """[(distance north in m, position index, rssi)] -> header, rows. Rows of
    one position get exactly the same coordinates, as a logger writes them
    for a node standing still. The index moves a position east by a
    millimetre a step, so two positions at one distance are still two places
    and no distance moves by more than a fraction of a metre."""
    text = "rssi,latitude,longitude\n" + "".join(
        f"{v:.2f},{GW_LAT + d / M_PER_DEG_LAT:.9f},{GW_LON + k * 1e-8:.9f}\n"
        for d, k, v in rows)
    return pathloss.read_csv(text, is_text=True)


def _campaign(shadow, fade, seed=7, positions=300, stays=((35, 150), (90, 60), (140, 40))):
    """A walk of single packets and a few long stays, from a known model."""
    rng = random.Random(seed)
    rows, k = [], 0
    for i in range(positions):
        d = 40 + 360 * rng.random()
        offset = rng.gauss(0, shadow)
        rows.append((d, k, -40 - 25 * math.log10(d) + offset + rng.gauss(0, fade)))
        k += 1
    for d, n in stays:
        offset = rng.gauss(0, shadow)
        rows += [(d, k, -40 - 25 * math.log10(d) + offset + rng.gauss(0, fade))
                 for _ in range(n)]
        k += 1
    return rows


def _analyse(rows, **kw):
    header, data = _csv(rows)
    return pathloss.analyse(header, data, GW_LAT, GW_LON, tx_power_dbm=14, **kw)


def _fit(res, label):
    return next(f for f in res["fits"] if f["label"] == label)


class TestPooledFading(unittest.TestCase):

    def test_pooled_by_degrees_of_freedom(self):
        by = {"a": [(30, -80.0), (30, -84.0)],              # s^2 = 8,  1 dof
              "b": [(60, -90.0), (60, -92.0), (60, -94.0)],  # s^2 = 4,  2 dof
              "c": [(90, -99.0)]}                            # one packet, no dof
        f = pathloss.pooled_fading(by)
        self.assertEqual(f["dof"], 3)
        self.assertAlmostEqual(f["sigma_db"], math.sqrt((8 + 8) / 3))
        self.assertEqual([g["n"] for g in f["groups"]], [3, 2])

    def test_no_repeated_position_no_fading(self):
        self.assertIsNone(pathloss.pooled_fading({"a": [(30, -80.0)], "b": [(60, -90.0)]}))


def _tolerance(sigma, dof):
    """Three standard errors of a standard deviation estimated with dof
    degrees of freedom, sigma / sqrt(2 dof) each."""
    return 3 * sigma / math.sqrt(2 * dof)


class TestTheSplit(unittest.TestCase):

    def test_recovers_both_spreads(self):
        res = _analyse(_campaign(shadow=6.0, fade=4.0))
        fit = _fit(res, "per position")
        self.assertAlmostEqual(res["fading"]["sigma_db"], 4.0,
                               delta=_tolerance(4.0, res["fading"]["dof"]))
        self.assertAlmostEqual(fit["fading_sigma_db"], res["fading"]["sigma_db"])
        self.assertAlmostEqual(fit["shadowing_sigma_db"], 6.0, delta=1.0)
        self.assertAlmostEqual(fit["path_loss_exponent"], 2.5, delta=0.3)
        self.assertEqual(fit["n_points"], 303)
        # The residual is kept beside the split, and is larger than shadowing.
        self.assertGreater(fit["residual_sigma_db"], fit["shadowing_sigma_db"])
        self.assertFalse(fit["doubtful"])

    def test_a_mean_of_several_packets_keeps_less_fading(self):
        # Every position measured four times: each mean keeps a quarter of the
        # fading variance, and only that quarter comes off the residual.
        rng = random.Random(11)
        rows = []
        for k in range(250):
            d = 40 + 360 * rng.random()
            offset = rng.gauss(0, 5.0)
            rows += [(d, k, -40 - 25 * math.log10(d) + offset + rng.gauss(0, 8.0))
                     for _ in range(4)]
        res = _analyse(rows)
        fit = _fit(res, "per position")
        self.assertAlmostEqual(fit["shadowing_sigma_db"], 5.0, delta=0.8)
        # Taking off the whole of fading would leave almost nothing.
        whole = fit["residual_sigma_db"] ** 2 - fit["fading_sigma_db"] ** 2
        self.assertLess(whole, 5.0 ** 2 / 2)

    def test_the_other_fits_mix_the_two(self):
        res = _analyse(_campaign(shadow=6.0, fade=4.0))
        for label in ("unbinned", "binned (10 m)"):
            self.assertNotIn("fading_sigma_db", _fit(res, label))

    def test_spread_that_is_all_fading(self):
        res = _analyse(_campaign(shadow=0.0, fade=8.8, seed=3))
        fit = _fit(res, "per position")
        self.assertEqual(fit["shadowing_sigma_db"], 0.0)
        self.assertAlmostEqual(fit["fading_sigma_db"], 8.8,
                               delta=_tolerance(8.8, res["fading"]["dof"]))
        kinds = [(w["kind"], w.get("fit")) for w in res["warnings"]]
        self.assertIn(("no_shadowing_left", "per position"), kinds)
        # Saying the split found no shadowing is no reason to doubt the fit.
        self.assertFalse(fit["doubtful"])

    def test_without_repeated_positions_there_is_no_third_fit(self):
        res = _analyse(_campaign(shadow=6.0, fade=4.0, stays=()))
        self.assertIsNone(res["fading"])
        self.assertEqual([f["label"] for f in res["fits"]], ["unbinned", "binned (10 m)"])

    def test_too_few_positions_keep_the_fading_and_drop_the_fit(self):
        rows = [(50, 0, -80 + j % 3) for j in range(10)] + [(120, 1, -90 + j % 2)
                                                           for j in range(10)]
        res = _analyse(rows)
        self.assertEqual(res["fading"]["dof"], 18)
        self.assertNotIn("per position", [f["label"] for f in res["fits"]])

    def test_positions_below_the_floor_stay_out(self):
        rows = _campaign(shadow=6.0, fade=4.0, stays=((20, 100), (90, 60)))
        res = _analyse(rows)
        self.assertEqual([g["n"] for g in res["fading"]["groups"]], [60])

    def test_the_snippet_carries_both(self):
        res = _analyse(_campaign(shadow=6.0, fade=4.0))
        text = pathloss.study_snippet(_fit(res, "per position"))
        self.assertRegex(text, r"    shadowing_sigma_db=\d+\.\d\d,\n    fading_sigma_db=\d+\.\d\d,\n")
        self.assertNotIn("fading_sigma_db", pathloss.study_snippet(_fit(res, "unbinned")))


class TestCheckReadsTheSplit(unittest.TestCase):

    def _discarded(self, **over):
        from loracap import study as study_mod
        from tests import helpers
        _e, warnings, _i = study_mod.validate(helpers.study(**over))
        return any("discarded rather than modelled" in w for w in warnings)

    def test_a_spread_put_in_fading_is_not_discarded(self):
        # The per position fit can leave shadowing at 0 with the whole spread
        # in fading, and check then said the spread was being thrown away.
        self.assertFalse(self._discarded(path_loss_r_squared=0.318,
                                         shadowing_sigma_db=0.0, fading_sigma_db=8.81))
        self.assertTrue(self._discarded(path_loss_r_squared=0.318,
                                        shadowing_sigma_db=0.0, fading_sigma_db=0.0))
        self.assertFalse(self._discarded(path_loss_r_squared=0.318,
                                         shadowing_sigma_db=7.0, fading_sigma_db=0.0))


NODE = shutil.which("node")


def _page():
    with open(PAGE, encoding="utf-8") as f:
        return f.read()


def _fn(html, name):
    return re.search(r"(function " + name + r"\(.*?\n\})", html, re.S).group(1)


@unittest.skipUnless(NODE, "Node is not installed")
class TestThePage(unittest.TestCase):

    FIT = {"label": "per position", "path_loss_exponent": 2.013, "path_loss_ref_db": 91.09,
           "path_loss_ref_distance_m": 100, "min_distance_m": 30, "max_distance_m": 379.8,
           "n_points": 98, "shadowing_sigma_db": 0.0, "fading_sigma_db": 8.8087,
           "r_squared": 0.318}

    def run_js(self, code):
        r = helpers.run_node(code)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def adopt(self, fit):
        html = _page()
        stubs = ("const els={}; const $=id=>(els[id]=els[id]||{value:''});"
                 "let LASTFIT=null, ADOPTED_R2=null, MODEL_WRITTEN={};"
                 "function setOrigin(){} function schedule(){}")
        return self.run_js("\n".join([
            stubs, _fn(html, "written"), _fn(html, "useFit"),
            "$('f_fading').value='8.7';",
            "LASTFIT={fits:[%s], equipment:null}; useFit(0);" % json.dumps(fit),
            "console.log(JSON.stringify({fading:$('f_fading').value, "
            "sigma:$('f_sigma').value, written:MODEL_WRITTEN}));"]))

    def test_adopting_the_split_fills_both(self):
        out = self.adopt(self.FIT)
        self.assertEqual(out["fading"], "8.81")
        self.assertEqual(out["sigma"], "0.00")
        self.assertEqual(out["written"]["f_fading"], "8.81")

    def test_the_other_fits_leave_fading_alone(self):
        fit = dict(self.FIT, label="binned (10 m)", shadowing_sigma_db=7.11)
        fit.pop("fading_sigma_db")
        out = self.adopt(fit)
        self.assertEqual(out["fading"], "8.7")
        self.assertNotIn("f_fading", out["written"])

    def test_the_fit_panel_says_where_fading_came_from(self):
        html = _page()
        show = _fn(html, "showFit")
        base = {"n_usable": 270, "n_kept": 270, "distance_min_m": 30, "distance_max_m": 380,
                "warnings": [], "equipment": None, "fits": [dict(self.FIT, doubtful=False)]}
        js = "\n".join([
            "function mk(tag,cls,text){ return {tag, cls:cls||'', text:text||'', kids:[],"
            " title:'', append(...x){this.kids.push(...x);}, appendChild(x){this.kids.push(x);"
            " return x;}, set innerHTML(v){this.kids=[];}}; }",
            "const tset=(el,k)=>{ el.text=k; return el; }, tsetx=tset, T=k=>k, useFit=()=>{};",
            "const msgT=(k,t,v)=>mk('div','msg',t.replace(/\\{(\\w+)\\}/g,(m,n)=>v?v[n]:m)), msgEn=msgT;",
            "const out=mk('div'), $=id=>out;", show,
            "const said=r=>{ showFit(r); return out.kids.filter(x=>x.cls==='msg').map(x=>x.text); };",
            "console.log(JSON.stringify([said(%s), said(%s)]));" % (
                json.dumps(dict(base, fading={"sigma_db": 8.8087, "dof": 172,
                                              "groups": [{}, {}, {}, {}]})),
                json.dumps(dict(base, fading=None)))])
        with_, without = self.run_js(js)
        self.assertIn("Fading σ 8.81 dB, from 4 positions measured more than once "
                      "(172 degrees of freedom). The per position fit takes it out of "
                      "the spread, and what is left is shadowing.", with_)
        self.assertIn("No position was measured more than once, so fading cannot be "
                      "told apart from shadowing.", without)


if __name__ == "__main__":
    unittest.main()
