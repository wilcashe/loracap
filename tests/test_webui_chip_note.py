"""The gateway chip note under the web form (design item 29).

Until this item the note showed the 125 kHz figures whatever the bandwidth:
eight channels and the SX1301's Table 12 for a study at 500 kHz, where the
simulation runs one channel on Table 14. It also offered XRange_SX1272, a
node radio, as a gateway chip, and with it the note read "null channels".

So the note is checked against the simulation itself. The server resolves
each bandwidth through a Study, and the tests compare what it sends with
what a Study resolves, plus a few figures pinned to the datasheet so that
both sides cannot drift together. The note's sentence is built in the page,
so the few lines that build it are run in Node when it is installed, with
the server's own data, and skipped when it is not.
"""
import json
import re
import shutil
import subprocess
import unittest

from tests import helpers  # noqa: F401  (puts the package on sys.path)
from tests.test_webui import PAGE

from loracap import presets
from loracap import study as study_mod
from webui import server


def _page():
    with open(PAGE, encoding="utf-8") as f:
        return f.read()


def _study(chip, bw):
    sfs = tuple(sorted(next(iter(presets.SENSITIVITY_DBM[chip].values()))))
    return study_mod.Study(name="oracle", chip=chip, bw_khz=bw,
                           spreading_factors=sfs)


class TestTheChipsOffered(unittest.TestCase):

    def test_only_concentrators_are_offered(self):
        b = server.api_bootstrap(None)
        self.assertEqual(b["chips"], ["SX1301", "SX1308"])
        self.assertEqual(sorted(b["chip_detail"]), b["chips"])

    def test_the_node_radio_stays_out_and_why(self):
        """It is out because it has no channel count, which the form has no
        field for, and not because it is missing from presets."""
        self.assertIn("XRange_SX1272", presets.SENSITIVITY_DBM)
        self.assertNotIn("XRange_SX1272", server.gateway_chips())
        with self.assertRaisesRegex(ValueError, "set n_channels"):
            _study("XRange_SX1272", 125).resolved_n_channels()

    def test_every_chip_offered_resolves_at_every_bandwidth(self):
        for chip in server.gateway_chips():
            for bw in server.lorawan_bandwidths():
                s = _study(chip, bw)
                self.assertGreater(s.resolved_n_channels(), 0, (chip, bw))
                self.assertIsNotNone(s.resolved_max_demod(), (chip, bw))


class TestTheNoteSaysWhatTheSimulationUses(unittest.TestCase):

    def test_the_bandwidths_are_the_regional_plans_own(self):
        self.assertEqual(server.lorawan_bandwidths(), [125, 250, 500])

    def test_every_figure_matches_a_study(self):
        for chip in server.gateway_chips():
            detail = server.chip_detail(chip)
            self.assertEqual(sorted(detail["by_bw"]), server.lorawan_bandwidths())
            for bw, at in detail["by_bw"].items():
                s = _study(chip, bw)
                table, derived_from = s.resolved_sensitivity_with_provenance()
                where = (chip, bw)
                self.assertEqual(at["channels"], s.resolved_n_channels(), where)
                self.assertEqual(at["max_demod"], s.resolved_max_demod(), where)
                self.assertEqual(at["derived_from"], derived_from, where)
                self.assertEqual(sorted(at["sensitivity"]), sorted(table), where)
                for sf, v in table.items():
                    self.assertAlmostEqual(at["sensitivity"][sf], v, delta=0.005,
                                           msg=where)

    def test_pinned_to_the_datasheet(self):
        """SX1301 datasheet V2.4: Table 12 at 125 kHz, Table 14 at 500 kHz,
        and above 125 kHz the one channel on IF8."""
        sx = server.chip_detail("SX1301")["by_bw"]
        self.assertEqual((sx[125]["channels"], sx[125]["sensitivity"][7]), (8, -126.5))
        self.assertEqual((sx[500]["channels"], sx[500]["sensitivity"][7]), (1, -120.5))
        self.assertEqual(sx[500]["sensitivity"][12], -133.5)
        self.assertIsNone(sx[500]["derived_from"])

    def test_a_derived_column_says_so(self):
        """The SX1308 has a 125 kHz table only, so 250 kHz is derived by
        10*log10(2) = 3.01 dB, the figure the checks quote."""
        at = server.chip_detail("SX1308")["by_bw"][250]
        self.assertEqual((at["derived_from"], at["shift_db"]), (125, 3.01))
        self.assertEqual(at["sensitivity"][7], -123.49)
        self.assertIsNone(server.chip_detail("SX1308")["by_bw"][125]["shift_db"])

    def test_the_bandwidth_field_redraws_the_note(self):
        self.assertIn("['input','change'].forEach(ev=>$('f_bw').addEventListener(ev, chipNote));",
                      _page())


NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node is not installed")
class TestTheSentence(unittest.TestCase):
    """chipNote run in Node with the server's data and a stub of the few
    page elements it touches."""

    @classmethod
    def setUpClass(cls):
        html = _page()
        def fn(name):
            return re.search(r"(function " + name + r"\(.*?\n\})", html, re.S).group(1)
        num = re.search(r"(const num = .*?;\n)", html).group(1)
        boot = json.dumps({"chip_detail": {c: server.chip_detail(c)
                                           for c in server.gateway_chips()}})
        stubs = """
let LANG='en', ES={}; const I18N_MISSES=new Set();
const BOOT=%s;
const els={f_chip:{value:''}, f_bw:{value:''}, chipnote:{parts:[],
  set innerHTML(v){this.parts=[];}, set textContent(v){this.parts=[v];},
  appendChild(n){this.parts.push(n.textContent);},
  append(...xs){xs.forEach(x=>this.parts.push(typeof x==='string'?x:x.textContent));}}};
const $=id=>els[id];
const document={createElement:()=>({textContent:''})};
const sourceSpan=s=>({textContent:'<'+s+'>'});
function note(chip, bw){ els.f_chip.value=chip; els.f_bw.value=bw; chipNote();
  return els.chipnote.parts.join(''); }
""" % boot
        cls.prelude = "\n".join([stubs, num, fn("fill"), fn("T"), fn("chipNote")])

    def _note(self, chip, bw):
        code = self.prelude + "\nconsole.log(JSON.stringify(note(%s, %s)));" % (
            json.dumps(chip), json.dumps(str(bw)))
        r = subprocess.run([NODE, "-e", code], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_at_125_khz(self):
        text = self._note("SX1301", 125)
        self.assertIn("At 125 kHz: sensitivity SF7 -126.5 ", text)
        self.assertIn("· 8 channels · 8 simultaneous demodulations", text)

    def test_at_500_khz_one_channel_and_its_own_table(self):
        text = self._note("SX1301", 500)
        self.assertIn("At 500 kHz: sensitivity SF7 -120.5 ", text)
        self.assertIn("SF12 -133.5 dBm · 1 channel · 8 simultaneous", text)
        self.assertNotIn("-126.5", text)
        self.assertNotIn("calculated", text)

    def test_a_calculated_column_says_so(self):
        """Worded as calculated rather than published, at the user's request:
        "derived" read as ambiguous in Spanish."""
        text = self._note("SX1308", 250)
        self.assertIn("SF7 -123.49 ", text)
        self.assertIn("no published figures at 250 kHz. These were calculated "
                      "by adding 3.01 dB to its 125 kHz figures", text)

    def test_a_bandwidth_no_plan_defines(self):
        text = self._note("SX1301", 300)
        self.assertIn("300 kHz is not a LoRaWAN uplink bandwidth", text)
        self.assertNotIn("channel", text)

    def test_no_chip(self):
        self.assertIn("No chip selected", self._note("", 125))


if __name__ == "__main__":
    unittest.main()
