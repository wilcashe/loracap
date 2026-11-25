"""The version lives outside the code digest (design item 46).

Every saved result records a SHA-256 of the package's .py files, and a
regeneration is needed whenever it changes. The version used to sit in
__init__.py, inside that digest, so raising it meant running every
experiment again, and commit 925adaa kept reporting 2.2.0 for newer code
rather than pay for that. It now lives in loracap/VERSION.
"""
import os
import re
import shutil
import tempfile
import unittest

import loracap
from loracap import reproduce

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "loracap")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestTheVersion(unittest.TestCase):

    def test_read_from_the_file(self):
        self.assertEqual(loracap.__version__, _read(os.path.join(PKG, "VERSION")).strip())
        self.assertRegex(loracap.__version__, r"^\d+\.\d+\.\d+$")

    def test_the_citation_agrees(self):
        cff = re.search(r"^version: (\S+)$", _read(os.path.join(ROOT, "CITATION.cff")), re.M)
        self.assertEqual(cff.group(1), loracap.__version__)

    def test_the_changelog_has_a_section_for_it(self):
        self.assertIn(f"## {loracap.__version__} (", _read(os.path.join(ROOT, "CHANGELOG.md")))


class TestTheDigestIgnoresIt(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for fn in os.listdir(PKG):
            if fn.endswith(".py") or fn == "VERSION":
                shutil.copy(os.path.join(PKG, fn), self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_raising_the_version_keeps_the_digest(self):
        before = reproduce.code_digest(self.tmp)
        with open(os.path.join(self.tmp, "VERSION"), "w", encoding="utf-8") as f:
            f.write("9.9.9\n")
        self.assertEqual(reproduce.code_digest(self.tmp), before)

    def test_changing_the_code_changes_it(self):
        before = reproduce.code_digest(self.tmp)
        with open(os.path.join(self.tmp, "core.py"), "a", encoding="utf-8") as f:
            f.write("\n# a change\n")
        self.assertNotEqual(reproduce.code_digest(self.tmp), before)

    def test_the_package_folder_is_the_default(self):
        self.assertEqual(reproduce.code_digest(), reproduce.code_digest(PKG))

    def test_no_python_file_states_the_version(self):
        # A version typed back into a .py file would enter the digest again.
        for fn in os.listdir(PKG):
            if fn.endswith(".py"):
                self.assertNotRegex(_read(os.path.join(PKG, fn)),
                                    r"""__version__\s*=\s*["']\d""", fn)


if __name__ == "__main__":
    unittest.main()
