"""check, split into its groups (design item 47).

`study.validate` was one function of 518 lines. It is now a short list of
calls, one per group of checks, made in the order the messages always came
out in. Over 3004 generated studies the split gave the same errors, warnings
and information, word for word and in the same order, except where the old
function stopped with a traceback: a spreading factor missing from an
explicit sensitivity table (KeyError) and a send interval of 0
(ZeroDivisionError). Those now come back as errors.
"""
import ast
import os
import unittest

from loracap import study as study_mod
from tests import helpers

SQUARE = [[(-500.0, -500.0), (500.0, -500.0), (500.0, 500.0), (-500.0, 500.0)]]


class TestWhatUsedToStopCheck(unittest.TestCase):

    def test_a_spreading_factor_without_a_sensitivity(self):
        # A table measured at SF9 only, as CowNet's unexplained threshold was.
        for placement in ("polygon", "disc"):
            errors, _w, info = study_mod.validate(helpers.study(
                sensitivity_dbm={9: -117.4}, placement=placement, polygons_m=SQUARE,
                scenarios=("SF7", "SF9", "MULTI"), max_measured_distance_m=500.0))
            self.assertIn("sensitivity_dbm has no entry for SF7.", errors)
            self.assertTrue(any(i.startswith("  SF9: sensitivity -117.4 dBm") for i in info))
            self.assertFalse(any(i.startswith("  SF7:") for i in info))

    def test_a_send_interval_of_zero_or_less(self):
        for interval in (0.0, -20.0):
            errors, warnings, _i = study_mod.validate(helpers.study(
                send_interval_s=interval, sim_time_s=60.0))
            self.assertIn(f"send_interval_s must be positive, not {interval!r}.", errors)
            self.assertFalse(any("transmissions per node" in w for w in warnings))

    def test_a_short_run_still_counts_its_transmissions(self):
        errors, warnings, _i = study_mod.validate(helpers.study(
            send_interval_s=20.0, sim_time_s=60.0))
        self.assertFalse(any("send_interval_s" in e for e in errors))
        self.assertIn("sim_time_s = 60 gives about 3 transmissions per node. "
                      "Short runs under-represent collisions.", warnings)


class TestTheShape(unittest.TestCase):

    def test_no_function_in_study_py_grows_back(self):
        # The longest group is about 80 lines. A function past 150 is a sign
        # that checks are being added in one block again.
        path = os.path.join(os.path.dirname(study_mod.__file__), "study.py")
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        long = [(n.name, n.end_lineno - n.lineno + 1) for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.end_lineno - n.lineno + 1 > 150]
        self.assertEqual(long, [])


if __name__ == "__main__":
    unittest.main()
