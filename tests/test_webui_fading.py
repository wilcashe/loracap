"""The fading sigma on the web page (design item 35).

`fading_sigma_db` has been a study field since design item 3, drawn per
packet, but the page had no control for it. The CowNet study needed one, the
spread in time of a node standing still at 35 m, and it had to be added to
study.py by hand. The page now offers it beside the shadowing sigma.

Adding it showed a second fault. Once a fit or the environment model filled
the propagation block, its bar said only "filled in by the field fit" and
listed nothing, so a value typed by hand in that block, which no model fills,
sat hidden. The bar now credits the model only with the values it wrote, and
lists every other change.

The tests check the control, its default and range against the study's, the
round trip through study.py, and the bar's rule, run in Node with stubs when
Node is installed.
"""
import dataclasses
import json
import re
import shutil
import subprocess
import unittest

from tests.test_webui import PAGE, TempRoot

from loracap import study as study_mod
from webui import server


def _page():
    with open(PAGE, encoding="utf-8") as f:
        return f.read()


NODE = shutil.which("node")


class TestTheControl(unittest.TestCase):

    def setUp(self):
        self.html = _page()

    def test_in_the_propagation_block_at_the_studys_default(self):
        default = {f.name: f.default for f in dataclasses.fields(study_mod.Study)}
        block = self.html[self.html.index('id="adv_prop"'):self.html.index('<!-- 4. traffic')]
        field = re.search(r'<input id="f_fading"[^>]*value="([\d.]+)"', block)
        self.assertIsNotNone(field)
        self.assertEqual(float(field.group(1)), default["fading_sigma_db"])
        self.assertIn("fading_sigma_db:num('f_fading',%g)" % default["fading_sigma_db"], self.html)
        self.assertIn("fading_sigma_db:['f_fading',", self.html)
        self.assertIn("fading_sigma_db:'f_fading'", self.html)
        self.assertIn('class="srcnote" data-for="f_fading"', block)

    def test_its_range_is_the_validators(self):
        lim = server.field_limits()["fading_sigma_db"]

        def messages(value):
            from tests import helpers
            e, w, _ = study_mod.validate(helpers.study(fading_sigma_db=value))
            return [m for m in e + w if "fading_sigma_db" in m]
        self.assertTrue(messages(lim["ge"] - 0.1))
        self.assertFalse(messages(lim["warn_gt"]))
        self.assertTrue(messages(lim["warn_gt"] + 0.1))


class TestStudyPy(TempRoot):

    def test_written_and_read_back(self):
        out = self.create(name="fadingtest", fading_sigma_db=8.7)
        self.assertEqual(out["errors"], [])
        self.assertIn("    fading_sigma_db=8.7,", out["study_py"])
        self.assertEqual(study_mod.load_study("fadingtest").fading_sigma_db, 8.7)


@unittest.skipUnless(NODE, "Node is not installed")
class TestTheBarBehindAModel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        html = _page()

        def fn(name):
            return re.search(r"(function " + name + r"\(.*?\n\})", html, re.S).group(1)
        stubs = """
const els={};
const $=id=>(els[id]=els[id]||{value:''});
let LASTFIT=null, ADOPTED_R2=null, MODEL_WRITTEN={};
function setOrigin(){} function schedule(){}
"""
        cls.prelude = "\n".join([stubs, fn("handChanges"), fn("written"), fn("useFit")])

    def js(self, body):
        r = subprocess.run([NODE, "-e", self.prelude + "\n" + body],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_a_field_the_model_never_fills_is_listed(self):
        out = self.js("""console.log(JSON.stringify(handChanges(
            [{id:'f_fading', value:'8.7'}, {id:'f_n', value:'2.188'}], {f_n:'2.188'})
            .map(c=>c.id)));""")
        self.assertEqual(out, ["f_fading"])

    def test_a_field_edited_after_the_model_is_listed(self):
        out = self.js("""console.log(JSON.stringify(handChanges(
            [{id:'f_sigma', value:'5'}], {f_sigma:'7.11'}).map(c=>c.id)));""")
        self.assertEqual(out, ["f_sigma"])

    def test_what_the_fit_wrote_is_credited_to_it(self):
        fit = {"label": "binned (10 m)", "path_loss_exponent": 2.188,
               "path_loss_ref_db": 91.85, "path_loss_ref_distance_m": 100,
               "min_distance_m": 30, "max_distance_m": 380, "n_points": 33,
               "shadowing_sigma_db": 7.11, "r_squared": 0.446}
        out = self.js("LASTFIT={fits:[%s], equipment:null}; useFit(0);"
                      "console.log(JSON.stringify(MODEL_WRITTEN));" % json.dumps(fit))
        self.assertEqual(sorted(out), ["f_d0", "f_maxd", "f_minv", "f_n", "f_plsrc",
                                       "f_ref", "f_sigma"])
        self.assertEqual(out["f_sigma"], "7.11")
        # Design item 39: the farthest measurement comes with the fit.
        self.assertEqual(out["f_maxd"], "380.0")
        # A fit without a loss or a sigma writes neither, so neither is its.
        bare = dict(fit, shadowing_sigma_db=None)
        bare.pop("path_loss_ref_db")
        out = self.js("LASTFIT={fits:[%s], equipment:null}; useFit(0);"
                      "console.log(JSON.stringify(MODEL_WRITTEN));" % json.dumps(bare))
        self.assertEqual(sorted(out), ["f_maxd", "f_minv", "f_n", "f_plsrc"])


class TestTheModelHandsBackTheBar(unittest.TestCase):

    def test_the_environment_model_and_the_reset(self):
        html = _page()
        self.assertIn("MODEL_WRITTEN=written(['f_n','f_ref','f_maxd','f_plsrc']);", html)
        self.assertIn("if(o!=='fit' && o!=='terrain') MODEL_WRITTEN={};", html)
        self.assertIn("handChanges(ch.map(c=>({...c, id:c.el.id, value:ctlState(c.el)})), MODEL_WRITTEN)", html)


if __name__ == "__main__":
    unittest.main()
