"""The web interface's receiver-model controls.

The interface only ever writes a study.py, so what matters is that the three
choices reach that file and come back from it unchanged, that the page is
offered exactly the options the engine has, and that leaving everything at
its default writes a study that behaves as one written by hand would.

The server's handlers are called directly, with the studies root redirected
to a temporary directory so nothing is written into the repository. The page
itself is checked for the controls and the keys it sends, since the suite
has no browser.
"""
import os
import re
import shutil
import tempfile
import unittest
from unittest import mock

from tests import helpers
from tests.helpers import GUAMAL_STUDY_FIELDS

from loracap import presets
from loracap import study as study_mod
from loracap.core import RECEIVER_MODELS
from webui import server

PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
    helpers.__file__))), "webui", "index.html")


def form_values(**over):
    """What the page posts for a minimal disc-placed study."""
    v = dict(name="formtest", region="US915", bw_khz=125, chip="SX1308",
             spreading_factors=[7, 8, 9, 10], payload_bytes=32,
             scenarios=["SF8"], placement="disc",
             path_loss_source="test fixture", send_interval_s=60.0,
             node_counts=[5, 20, 80, 320], **GUAMAL_STUDY_FIELDS)
    v.update(over)
    return v


class TempRoot(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="loracap-webui-")
        patcher = mock.patch.object(study_mod, "studies_root",
                                    lambda start=None: self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.root, True)

    def create(self, **over):
        return server.api_create({"values": form_values(**over)})


class TestTheOptionsOffered(unittest.TestCase):

    def setUp(self):
        self.boot = server.api_bootstrap(None)

    def test_every_engine_rule_is_offered_with_a_note(self):
        offered = [m["value"] for m in self.boot["receiver_models"]]
        self.assertEqual(offered, list(RECEIVER_MODELS))
        for m in self.boot["receiver_models"]:
            self.assertTrue(m["note"].strip())

    def test_the_defaults_are_the_studys_own(self):
        s = helpers.study()
        self.assertEqual(self.boot["default_receiver_model"], s.receiver_model)
        self.assertEqual(self.boot["default_capture_threshold_db"],
                         s.capture_threshold_db)

    def test_every_rejection_table_is_offered_with_its_source(self):
        offered = {t["value"]: t["source"] for t in self.boot["inter_sf_tables"]}
        self.assertEqual(set(offered), set(presets.INTER_SF_REJECTION_DB))
        for name, src in offered.items():
            self.assertEqual(src, presets.INTER_SF_REJECTION_SOURCE[name])


class TestTheLockRefinementsOffered(unittest.TestCase):

    def setUp(self):
        self.boot = server.api_bootstrap(None)

    def test_every_survival_table_is_offered_with_its_source(self):
        offered = {t["value"]: t["source"] for t in self.boot["lock_survival_tables"]}
        self.assertEqual(set(offered), set(presets.LOCK_SURVIVAL_DB))
        for name, src in offered.items():
            self.assertEqual(src, presets.LOCK_SURVIVAL_SOURCE[name])

    def test_recapture_defaults_to_the_studys_own(self):
        self.assertEqual(self.boot["default_header_recapture"],
                         helpers.study().header_recapture)
        self.assertTrue(self.boot["header_recapture_note"].strip())


class TestWhatTheFormWrites(TempRoot):

    def test_the_lock_refinements_reach_study_py(self):
        out = self.create(receiver_model="lock",
                          lock_survival="EIGNER2021_SX1301",
                          header_recapture=True)
        self.assertEqual(out["errors"], [])
        cfg = study_mod.load_study("formtest").to_sim_config()
        self.assertEqual(cfg.lock_survival_db,
                         presets.lock_survival("EIGNER2021_SX1301"))
        self.assertTrue(cfg.header_recapture)

    def test_the_three_choices_reach_study_py_and_come_back(self):
        out = self.create(receiver_model="lock", capture_threshold_db=3.0,
                          inter_sf_rejection="CROCE2020_SX1272")
        self.assertEqual(out["errors"], [])
        s = study_mod.load_study("formtest")
        self.assertEqual(s.receiver_model, "lock")
        self.assertEqual(s.capture_threshold_db, 3.0)
        self.assertEqual(s.to_sim_config().inter_sf_rejection_db,
                         presets.inter_sf_rejection("CROCE2020_SX1272"))

    def test_the_defaults_write_a_study_that_behaves_as_before(self):
        out = self.create(receiver_model="lorasim", capture_threshold_db=6.0)
        self.assertNotIn("inter_sf_rejection", out["study_py"])
        cfg = study_mod.load_study("formtest").to_sim_config()
        self.assertEqual(cfg.receiver_model, "lorasim")
        self.assertEqual(cfg.capture_threshold_db, 6.0)
        self.assertIsNone(cfg.inter_sf_rejection_db)

    def test_check_reports_what_was_chosen(self):
        out = self.create(inter_sf_rejection="CROCE2020_SX1272")
        self.assertTrue(any("inter-SF rejection on" in i for i in out["info"]))


class TestLiveValidation(unittest.TestCase):

    def check(self, **over):
        return server.api_validate({"values": form_values(**over)})["errors"]

    def test_a_valid_choice_passes(self):
        self.assertEqual(self.check(receiver_model="lock",
                                    inter_sf_rejection="CROCE2020_SX1272"), [])

    def test_an_unknown_rule_is_an_error_not_a_crash(self):
        self.assertTrue(any("receiver_model" in e
                            for e in self.check(receiver_model="nonesuch")))

    def test_an_unknown_table_is_an_error_not_a_crash(self):
        self.assertTrue(any("nonesuch" in e
                            for e in self.check(inter_sf_rejection="nonesuch")))


class TestThePage(unittest.TestCase):
    """No browser in the suite, so the page is checked for the controls and
    for the keys its values() sends."""

    @classmethod
    def setUpClass(cls):
        with open(PAGE, encoding="utf-8") as f:
            cls.html = f.read()

    def test_the_controls_exist(self):
        for el in ('id="f_rx"', 'id="f_capthr"', 'id="f_isf"', 'id="rxnote"'):
            self.assertIn(el, self.html)

    def test_values_sends_the_three_keys(self):
        body = re.search(r"function values\(\)\{(.*?)\n\}", self.html, re.S).group(1)
        for key in ("receiver_model:", "capture_threshold_db:",
                    "v.inter_sf_rejection="):
            self.assertIn(key, body)

    def test_values_sends_the_refinements_only_under_the_lock_rule(self):
        body = re.search(r"function values\(\)\{(.*?)\n\}", self.html, re.S).group(1)
        guarded = re.search(r"if\(v\.receiver_model==='lock'\)\{(.*?)\}\n", body, re.S)
        self.assertIsNotNone(guarded)
        self.assertIn("v.lock_survival=", guarded.group(1))
        self.assertIn("v.header_recapture=true", guarded.group(1))

    def test_the_refinement_controls_exist(self):
        for el in ('id="f_lsurv"', 'id="f_hrec"'):
            self.assertIn(el, self.html)

    def test_the_controls_are_built_at_start(self):
        boot = re.search(r"async function boot\(\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertIn("buildReceiver();", boot)


if __name__ == "__main__":
    unittest.main()
