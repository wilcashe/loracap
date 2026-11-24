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


if __name__ == "__main__":
    unittest.main()
