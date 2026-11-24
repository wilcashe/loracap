"""The equipment the field measurements were taken with (design item 32).

An RSSI becomes a loss of the terrain only through the power and antennas
that sent it. Until this item the page took them from the study's radio
fields at the moment the CSV was loaded, and never again. Loaded before the
real equipment was typed, the CowNet loss at 100 m came out 11.7 dB too low,
and "Use" copied it into the model without a word.

Now the measurements pane has fields of its own for the campaign's
equipment. The tests check that the fit reads those and only those, that a
blank one derives no loss, that the fit is redone whenever an input it reads
changes, and that the model records the equipment it came from. The page's
functions run in Node with a stub of the few elements they touch, and are
skipped when Node is not installed.
"""
import json
import math
import re
import shutil
import subprocess
import unittest

from tests import helpers  # noqa: F401  (puts the package on sys.path)
from tests.test_webui import PAGE

from webui import server


def _page():
    with open(PAGE, encoding="utf-8") as f:
        return f.read()


NODE = shutil.which("node")

# The CowNet campaign (2025-11-28): a 20 dBm collar, 2.1 dBi on the node,
# 5.1 dBi on the gateway, 0.5 dB of node losses and 1.0 dB of cable.
COWNET = {"m_tx": "20", "m_gtx": "2.1", "m_grx": "5.1", "m_loss": "1.5"}
# The study's own radio fields at the page's defaults.
STUDY_DEFAULTS = {"f_tx": "14", "f_gtx": "0", "f_grx": "0", "f_cable": "0"}


@unittest.skipUnless(NODE, "Node is not installed")
class TestTheRequest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        html = _page()

        def fn(name):
            return re.search(r"((?:async )?function " + name + r"\(.*?\n\})", html, re.S).group(1)
        num = re.search(r"(const num = .*?;\n)", html).group(1)
        ids = re.search(r"(const EQUIPMENT_IDS=.*?;\n)", html).group(1)
        stubs = """
let LANG='en', ES={}; const I18N_MISSES=new Set();
const els={};
const $=id=>(els[id]=els[id]||{value:'', innerHTML:'', appendChild(){}});
function setForm(v){ for(const k in v) $(k).value=v[k]; }
let LASTFIT=null, CSVTEXT=null, FITSEQ=0, POSTED=null, DELAYS=[];
async function post(url, body){
  POSTED={url, body};
  const wait=DELAYS.length ? DELAYS.shift() : 0;
  await new Promise(r=>setTimeout(r, wait));
  return {fits:[], warnings:[], sent:body.tx_power_dbm};
}
function msgT(){ return {}; } function msgX(){ return {}; } function showFit(){}
function setOrigin(){} function schedule(){}
let MODEL_WRITTEN={};
"""
        cls.prelude = "\n".join([stubs, num, ids, fn("fill"), fn("T"), fn("measuredWith"),
                                 fn("fitRequest"), fn("runFit"), fn("useFit"), fn("written"),
                                 fn("parseCoord"), fn("coord")])

    def js(self, body):
        r = helpers.run_node(self.prelude + "\n(async()=>{" + body + "})();")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def request(self, form):
        return self.js("setForm(%s); console.log(JSON.stringify(fitRequest('csv')));"
                       % json.dumps(form))

    def base(self, **over):
        form = {"f_lat": "5.501139", "f_lon": "-73.492939", "f_d0": "100", "f_minv": "30"}
        form.update(STUDY_DEFAULTS)
        form.update(over)
        return form

    def test_the_campaign_equipment_is_what_converts(self):
        r = self.request(self.base(**COWNET))
        self.assertEqual(r["tx_power_dbm"], 20)
        self.assertAlmostEqual(r["net_gain_db"], 2.1 + 5.1 - 1.5, places=9)
        self.assertEqual((r["d0_m"], r["min_distance_m"]), (100, 30))

    def test_the_studys_radio_does_not_enter(self):
        """The bug: loading the CSV with the study's defaults in place."""
        a = self.request(self.base(**COWNET))
        b = self.request(self.base(**COWNET, f_tx="27", f_gtx="9", f_grx="12", f_cable="4"))
        self.assertEqual(a, b)

    def test_a_blank_field_derives_no_loss(self):
        for blank in COWNET:
            with self.subTest(blank=blank):
                form = self.base(**COWNET)
                form[blank] = ""
                r = self.request(form)
                self.assertIsNone(r["tx_power_dbm"])
                self.assertEqual(r["net_gain_db"], 0)

    def test_a_fit_remembers_its_equipment(self):
        out = self.js("setForm(%s); CSVTEXT='rssi,latitude,longitude'; await runFit();"
                      "console.log(JSON.stringify({posted: POSTED.body, eq: LASTFIT.equipment}));"
                      % json.dumps(self.base(**COWNET)))
        self.assertEqual(out["posted"]["tx_power_dbm"], 20)
        self.assertEqual(out["eq"]["tx"], 20)
        self.assertAlmostEqual(out["eq"]["net"], 5.7, places=9)

    def test_a_late_answer_to_an_old_request_is_dropped(self):
        """Two quick edits: the first fit answers after the second."""
        out = self.js("setForm(%s); CSVTEXT='x'; DELAYS=[80, 0];"
                      "const a=runFit(); $('m_tx').value='14'; const b=runFit();"
                      "await Promise.all([a, b]);"
                      "console.log(JSON.stringify([LASTFIT.sent, LASTFIT.equipment.tx]));"
                      % json.dumps(self.base(**COWNET)))
        self.assertEqual(out, [14, 14])

    def test_the_model_records_its_equipment(self):
        fit = {"label": "binned (10 m)", "n_points": 33, "path_loss_exponent": 2.188,
               "r_squared": 0.446, "shadowing_sigma_db": 7.11, "path_loss_ref_db": 91.85,
               "path_loss_ref_distance_m": 100, "min_distance_m": 30, "max_distance_m": 380}
        out = self.js("LASTFIT={fits:[%s], equipment:{tx:20, net:5.7}}; useFit(0);"
                      "console.log(JSON.stringify([$('f_ref').value, $('f_plsrc').value]));"
                      % json.dumps(fit))
        self.assertEqual(out[0], "91.85")
        self.assertTrue(out[1].endswith(
            ", measured at 20 dBm with a net antenna gain of 5.7 dB"), out[1])


class TestTheWiring(unittest.TestCase):

    def test_every_input_the_fit_reads_redoes_it(self):
        """The equipment, and the gateway position, d0 and floor, which the
        request also carries. A moved gateway changes every distance."""
        html = _page()
        self.assertIn("const EQUIPMENT_IDS=['m_tx','m_gtx','m_grx','m_loss'];", html)
        self.assertIn("EQUIPMENT_IDS.concat(['f_lat','f_lon','f_d0','f_minv'])\n"
                      "  .forEach(id=>$(id).addEventListener('change', runFit));", html)

    def test_the_fields_are_on_the_measurements_pane(self):
        html = _page()
        pane = html[html.index('<div id="pane_fit"'):html.index('<div id="pane_terrain"')]
        for i in COWNET:
            self.assertIn(f'<input id="{i}" type="number" step="any">', pane)
            self.assertIn(f'<label for="{i}"', pane)


class TestTheServerUsesWhatItIsGiven(unittest.TestCase):
    """The loss at d0 moves one for one with the equipment sent, so 11.7 dB
    of equipment is 11.7 dB of model."""

    CSV = "rssi,latitude,longitude\n" + "\n".join(
        f"{-40 - 22 * math.log10(10 + 7 * i):.2f},{5.501139 + (10 + 7 * i) / 111320:.7f},-73.492939"
        for i in range(40))

    def fit(self, tx, net):
        r = server.api_fit({"csv": self.CSV, "lat": 5.501139, "lon": -73.492939,
                            "tx_power_dbm": tx, "net_gain_db": net, "d0_m": 100,
                            "min_distance_m": 30})
        return r["fits"][1]

    def test_the_difference_is_the_equipments(self):
        a, b = self.fit(14, 0.0), self.fit(20, 5.7)
        self.assertAlmostEqual(b["path_loss_ref_db"] - a["path_loss_ref_db"], 11.7, places=6)
        self.assertAlmostEqual(a["path_loss_exponent"], b["path_loss_exponent"], places=12)

    def test_without_equipment_no_loss(self):
        self.assertNotIn("path_loss_ref_db", self.fit(None, 0.0))


if __name__ == "__main__":
    unittest.main()
