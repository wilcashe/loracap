"""The suite runs where the README says LoRaCAP runs (design item 44).

The README promises Python 3.8 or newer, and a simulator that needs only the
standard library. Until item 44 nothing ran the suite anywhere but Python
3.13 with matplotlib installed: on 3.8 two tests failed, and without
matplotlib five modules failed to import.
"""
import importlib.util
import unittest
from unittest import mock

from tests import helpers


class TestWithoutMatplotlib(unittest.TestCase):

    def test_a_figure_module_is_skipped_not_failed(self):
        real = importlib.util.find_spec

        def missing(name, *a, **k):
            return None if name == "matplotlib" else real(name, *a, **k)
        with mock.patch("importlib.util.find_spec", side_effect=missing):
            with self.assertRaises(unittest.SkipTest) as cm:
                helpers.require_matplotlib()
        self.assertIn("matplotlib is not installed", str(cm.exception))

    def test_nothing_is_skipped_when_it_is_there(self):
        # A SkipTest escaping here would mark this test skipped, not failed,
        # so it is caught and turned into a failure.
        with mock.patch("importlib.util.find_spec", return_value=object()):
            try:
                helpers.require_matplotlib()
            except unittest.SkipTest:
                self.fail("skipped although matplotlib is installed")

    def test_the_simulator_does_not_import_it(self):
        # What the README calls the simulation: no module of it may import
        # matplotlib at load time, or the skip above would hide a real break.
        import ast
        import glob
        import os
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "loracap")
        importers = []
        for path in glob.glob(os.path.join(root, "*.py")):
            if os.path.basename(path) == "plotting.py":
                continue
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in tree.body:   # module level only: lazy imports are fine
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""] + [a.name for a in node.names]
                if any(n.split(".")[0] in ("matplotlib", "plotting") for n in names):
                    importers.append(os.path.basename(path))
        self.assertEqual(importers, [])


class TestTheWorkflowKeepsThePromise(unittest.TestCase):
    """Design item 45: the CI runs the oldest Python the README promises, on
    the three operating systems, and once without matplotlib. Read as text,
    since the standard library has no YAML reader."""

    def setUp(self):
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, ".github", "workflows", "tests.yml"),
                  encoding="utf-8") as f:
            self.flow = f.read()
        with open(os.path.join(root, "README.md"), encoding="utf-8") as f:
            self.readme = f.read()

    def test_the_oldest_promised_python_is_run(self):
        import re
        oldest = re.search(r"Python (3\.\d+) or newer", self.readme).group(1)
        self.assertRegex(self.flow, r'python: \["%s", "3\.\d+"\]' % re.escape(oldest))

    def test_three_systems_and_a_run_without_matplotlib(self):
        self.assertIn("os: [ubuntu-latest, windows-latest, macos-latest]", self.flow)
        self.assertIn("--with-requirements requirements.txt python run.py test", self.flow)
        without = self.flow.split("without-matplotlib:", 1)[1]
        self.assertIn("python run.py test", without)
        self.assertNotIn("requirements", without.split("steps:", 1)[1])

    def test_nothing_forces_utf_8(self):
        # A user on Windows gets the system code page, so the tests must too.
        self.assertNotIn("PYTHONUTF8", self.flow)
        self.assertNotIn("PYTHONIOENCODING", self.flow)


if __name__ == "__main__":
    unittest.main()
