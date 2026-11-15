"""What the web page tells the person filling it in (design item 24).

The page names fields the way the form labels them, shows under each field
the range of values it accepts, and explains each named table with an
example. Every one of those is a statement about the code, so each is
checked against the code here: a range the page shows must be the range the
validator enforces, a label must belong to a real control, and an example
must come from the table it describes.

The page's logic is JavaScript and the suite is standard-library Python.
The data the page receives and the page's text are checked directly. The few
pure functions that turn that data into sentences are run in Node when it is
installed, and skipped when it is not.
"""
import json
import os
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser

from tests import helpers  # noqa: F401  (puts the package on sys.path)
from tests.test_webui import PAGE, form_values

from loracap import presets
from loracap import study as study_mod
from webui import server


def _page():
    with open(PAGE, encoding="utf-8") as f:
        return f.read()


class _Labels(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.labels, self._in_label = set(), [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "label":
            self._in_label = {"for": a.get("for"), "wraps": False}
            self.labels.append(self._in_label)
        elif tag in ("input", "select") and self._in_label is not None:
            self._in_label["wraps"] = True

    def handle_endtag(self, tag):
        if tag == "label":
            self._in_label = None


def _js_object(html, name):
    """The keys and control ids of a `const NAME={key:['id',...], ...}` or
    `{key:'id', ...}` literal in the page."""
    body = re.search(r"const " + name + r"=\{(.*?)\};", html, re.S).group(1)
    return dict(re.findall(r"(\w+):\s*\[?'([^']+)'", body))


class TestEveryLabelBelongsToAControl(unittest.TestCase):
    """A label with no control behind it is not read by a screen reader and
    does nothing when clicked."""

    def test_every_label_names_a_control_that_exists(self):
        p = _Labels()
        p.feed(_page())
        loose = [l for l in p.labels if not l["wraps"] and not l["for"]]
        self.assertEqual(loose, [])
        missing = [l["for"] for l in p.labels
                   if l["for"] and l["for"] not in p.ids]
        self.assertEqual(missing, [])


class TestChecksNameTheFieldAsTheFormDoes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.html = _page()
        cls.fields = _js_object(cls.html, "FIELDS")

    def test_every_mapped_name_is_a_study_field(self):
        import dataclasses
        names = {f.name for f in dataclasses.fields(study_mod.Study)}
        self.assertEqual(sorted(set(self.fields) - names), [])

    def test_every_mapped_control_exists_in_the_page(self):
        missing = [i for i in self.fields.values()
                   if f'id="{i}"' not in self.html]
        self.assertEqual(missing, [])

    def test_every_field_a_check_names_is_mapped(self):
        """Run the validator into errors that name fields, and require each
        field name it uses to be one the page can translate."""
        bad = server._study_from_values(form_values(
            payload_bytes=500, path_loss_ref_db=0, der_threshold=1.5,
            n_gateways=2, shadowing_sigma_db=-1, placement="polygon",
            path_loss_source=""))
        errors, warnings, _info = study_mod.validate(bad)
        import dataclasses
        names = {f.name for f in dataclasses.fields(study_mod.Study)}
        used = {w for m in errors + warnings
                for w in re.findall(r"\b[a-z]+(?:_[a-z0-9]+)+\b", m)
                if w in names}
        self.assertTrue(used, "the validator named no fields at all")
        self.assertEqual(sorted(used - set(self.fields)), [])


class TestTheRangesAreTheValidatorsOwn(unittest.TestCase):
    """Each accepted or recommended range is tried on both sides against the
    validator, so the page cannot show a range the code does not enforce."""

    @classmethod
    def setUpClass(cls):
        cls.limits = server.field_limits()

    def _messages(self, **over):
        errors, warnings, _ = study_mod.validate(
            server._study_from_values(form_values(**over)))
        return errors, warnings

    def _names(self, field, msgs):
        return any(field in m for m in msgs)

    def test_der_threshold(self):
        lim = self.limits["der_threshold"]
        for v, bad in ((lim["gt"], True), (lim["lt"], True), (0.5, False)):
            errors, _ = self._messages(der_threshold=v)
            self.assertEqual(self._names("der_threshold", errors), bad, v)

    def test_gateways(self):
        lim = self.limits["n_gateways"]
        self.assertFalse(self._names("n_gateways",
                                     self._messages(n_gateways=lim["ge"])[0]))
        self.assertTrue(self._names("n_gateways",
                                    self._messages(n_gateways=lim["le"] + 1)[0]))

    def test_loss_at_d0(self):
        lim = self.limits["path_loss_ref_db"]
        self.assertTrue(self._names("path_loss_ref_db",
                                    self._messages(path_loss_ref_db=lim["gt"])[0]))
        self.assertFalse(self._names("path_loss_ref_db",
                                     self._messages(path_loss_ref_db=lim["gt"] + 1)[0]))

    def test_shadowing(self):
        lim = self.limits["shadowing_sigma_db"]
        e, w = self._messages(shadowing_sigma_db=lim["ge"] - 0.1)
        self.assertTrue(self._names("shadowing_sigma_db", e))
        e, w = self._messages(shadowing_sigma_db=lim["warn_gt"])
        self.assertFalse(self._names("shadowing_sigma_db", e + w))
        e, w = self._messages(shadowing_sigma_db=lim["warn_gt"] + 0.1)
        self.assertTrue(self._names("shadowing_sigma_db", w))

    def test_runs_and_simulated_time(self):
        for field in ("n_runs", "sim_time_s"):
            lim = self.limits[field]
            _, w = self._messages(**{field: lim["warn_lt"] - 1})
            self.assertTrue(self._names(field, w), field)
            _, w = self._messages(**{field: lim["warn_lt"]})
            self.assertFalse(self._names(field, w), field)

    def test_every_range_has_a_control(self):
        html = _page()
        mapped = _js_object(html, "LIMIT_FIELDS")
        self.assertEqual(sorted(mapped), sorted(self.limits))

    def test_the_measured_ranges_come_from_their_tables(self):
        lows = [t[0] for t in presets.TERRAIN_EXPONENTS.values()]
        highs = [t[1] for t in presets.TERRAIN_EXPONENTS.values()]
        text = self.limits["path_loss_exponent"]["text"]
        self.assertIn(f"{min(lows)} to {max(highs)}", text)
        self.assertIn("doi:10.3390/s24123877", text)
        lo, hi = server.CAPTURE_THRESHOLD_MEASURED_DB
        self.assertIn(f"{hi:g} dB or less", server.CAPTURE_THRESHOLD_NOTE)
        self.assertIn(f"{study_mod.Study.__dataclass_fields__['capture_threshold_db'].default:g} dB",
                      self.limits["capture_threshold_db"]["text"])


class TestPayloadCeilings(unittest.TestCase):

    def test_every_row_is_the_regional_tables_own(self):
        for region, rows in server.payload_ceilings().items():
            self.assertTrue(rows, region)
            for r in rows:
                found = presets.data_rate_for(region, r["sf"], r["bw"], r["dwell"])
                self.assertEqual(found[1], r["max"], (region, r))

    def test_the_case_that_started_it(self):
        """SF10 in US915 carries 11 bytes, which is why the page no longer
        opens with SF10 marked and a 32-byte payload."""
        us = server.payload_ceilings()["US915"]
        self.assertEqual([r["max"] for r in us if r["sf"] == 10 and r["bw"] == 125], [11])

    def test_the_page_opens_with_only_the_fastest_sf(self):
        self.assertIn("cb.checked = prev.size ? prev.has(name) : sf===sfs[0];", _page())


class TestTablesHaveReadableNames(unittest.TestCase):

    def test_every_table_has_a_label_and_a_short_name(self):
        names = set(presets.INTER_SF_REJECTION_DB) | set(presets.LOCK_SURVIVAL_DB)
        self.assertEqual(sorted(names - set(server.TABLE_LABELS)), [])
        self.assertEqual(sorted(names - set(server.TABLE_SHORT)), [])

    def test_the_page_receives_them(self):
        b = server.api_bootstrap(None)
        for t in b["inter_sf_tables"] + b["lock_survival_tables"]:
            self.assertTrue(t["label"] and t["short"] and t["db"], t["value"])


NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node is not installed")
class TestTheSentencesThePageBuilds(unittest.TestCase):
    """The page's pure functions, extracted and run in Node."""

    @classmethod
    def setUpClass(cls):
        html = _page()
        def fn(name):
            return re.search(r"(function " + name + r"\(.*?\n\})", html, re.S).group(1)
        consts = re.search(r"(const FIELDS=\{.*?const TOUCHED_IDS=new Set\(\);)",
                           html, re.S).group(1)
        cls.prelude = "\n".join([consts, fn("fieldsIn"), fn("rejectionHow"),
                                 fn("survivalHow")])

    def _run(self, expr):
        code = self.prelude + "\nconsole.log(JSON.stringify(" + expr + "));"
        r = subprocess.run([NODE, "-e", code], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_the_rejection_example_reads_the_table(self):
        for name, db in presets.INTER_SF_REJECTION_DB.items():
            text = self._run(f"rejectionHow({json.dumps(db)})")
            lo, hi = min(db), max(db)
            nxt = min(db[lo])
            self.assertIn(f"SF{lo} is lost when an overlapping SF{nxt} packet "
                          f"arrives more than {-db[lo][nxt]:g} dB stronger", text, name)
            self.assertIn(f"SF{hi} is lost when an overlapping SF{lo} packet "
                          f"arrives more than {-db[hi][lo]:g} dB stronger", text, name)

    def test_the_survival_example_reads_the_table(self):
        for name, db in presets.LOCK_SURVIVAL_DB.items():
            text = self._run(f"survivalHow({json.dumps(db)})")
            hi = max(db)
            self.assertIn(f"on SF{hi} it must be at least {db[hi]:g} dB stronger", text)

    def test_field_names_are_found_where_a_check_names_them(self):
        found = self._run("fieldsIn(\"placement='polygon' but polygons_m is empty.\")")
        self.assertEqual(found, ["placement", "polygons_m"])

    def test_an_ordinary_word_is_not_taken_for_a_field(self):
        """'site' is a field and also a word: "site-specific" must stay."""
        self.assertEqual(self._run(
            "fieldsIn('the single most site-specific parameter here')"), [])


if __name__ == "__main__":
    unittest.main()
