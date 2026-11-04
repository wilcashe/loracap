"""The experiment manifest behind `run.py reproduce`.

What these protect is not a number but the chain from a table back to the run
that produced it. Each failure mode below happened once: a short check
overwrote the run a table quoted, a variant's configuration lived only in a
temporary edit, and the same quantity ended up quoted five ways. The tests
use a tiny study in a temporary directory so the whole file runs in about a
second.
"""
import json
import os
import random
import shutil
import tempfile
import textwrap
import unittest

from tests import helpers  # noqa: F401  (puts the package on sys.path)

from loracap import experiment as experiment_mod
from loracap import reproduce, study as study_mod
from loracap.core import run_single_sim
from loracap.reproduce import Experiment, ManifestError, Variant

TINY_STUDY = textwrap.dedent('''
    from loracap import Study
    STUDY = Study(
        name="tiny", region="US915", bw_khz=125, chip="SX1308",
        payload_bytes=32, scenarios=("SF8",), spreading_factors=(7, 8, 9, 10),
        placement="disc", path_loss_source="test fixture",
        path_loss_exponent=2.159, path_loss_ref_db=130.32,
        path_loss_ref_distance_m=100.0, min_valid_distance_m=30.0,
        tx_power_dbm=22.0, tx_antenna_gain_db=3.0, rx_antenna_gain_db=6.0,
        send_interval_s=15.0, node_counts=(5, 20, 80, 320),
        sim_time_s=300.0, n_runs=3,
    )
''')

GRID = (5, 20, 80, 320)


def run_exp(**kw):
    base = dict(name="r", kind="run", description="test", n_runs=3,
                sim_time_s=300.0, base_seed=7, node_counts=GRID,
                scenarios=("SF8",))
    base.update(kw)
    return Experiment(**base)


class TempStudy(unittest.TestCase):
    """A throwaway studies root holding one tiny study."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="loracap-test-")
        os.makedirs(os.path.join(self.root, "tiny"))
        with open(os.path.join(self.root, "tiny", "study.py"), "w",
                  encoding="utf-8") as f:
            f.write(TINY_STUDY)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def json_files(self, directory):
        for dirpath, _dirs, files in os.walk(directory):
            for fn in files:
                if fn.endswith(".json"):
                    yield os.path.join(dirpath, fn)


class TestManifestIsCheckedBeforeAnythingRuns(unittest.TestCase):
    """A manifest error found after an hour of simulation costs the hour."""

    def assertRejected(self, *exps):
        with self.assertRaises(ManifestError):
            reproduce.check_manifest(list(exps))

    def test_a_valid_manifest_passes(self):
        reproduce.check_manifest([run_exp()])

    def test_run_must_state_its_grid(self):
        """The grid is not inherited from the study. A value that is not
        written next to the result is one nobody can check."""
        self.assertRejected(run_exp(node_counts=()))

    def test_run_must_state_its_scenarios(self):
        self.assertRejected(run_exp(scenarios=()))

    def test_names_are_unique(self):
        self.assertRejected(run_exp(), run_exp())

    def test_names_are_safe_directory_names(self):
        self.assertRejected(run_exp(name="../escape"))

    def test_unknown_kind(self):
        self.assertRejected(run_exp(kind="simulate"))

    def test_explicit_fields_cannot_also_be_overridden(self):
        """Two places that state the repetitions would sooner or later
        disagree about them."""
        self.assertRejected(run_exp(overrides={"n_runs": 30}))
        self.assertRejected(run_exp(variants=(Variant("a", "a", {"node_counts": (1, 2)}),)))

    def test_overrides_must_be_study_fields(self):
        self.assertRejected(run_exp(overrides={"shadowing": 4.0}))

    def test_one_run_has_no_spread(self):
        self.assertRejected(run_exp(n_runs=1))

    def test_a_sweep_takes_no_grid(self):
        """Bisection picks its own node counts. A stated grid would be read
        as the one used, and it would not be."""
        self.assertRejected(Experiment(
            name="s", kind="sweep", description="", n_runs=3, sim_time_s=300.0,
            base_seed=7, node_counts=GRID,
            options=dict(scenario="SF8", low=2.0, high=3.0, steps=3)))

    def test_kind_options_are_required(self):
        self.assertRejected(Experiment(
            name="s", kind="sweep", description="", n_runs=3, sim_time_s=300.0,
            base_seed=7, options=dict(scenario="SF8")))

    def test_several_variants_all_need_names(self):
        self.assertRejected(run_exp(variants=(Variant("", "a"), Variant("b", "b"))))

    def test_a_figure_needs_a_single_variant(self):
        """Every variant would write the same figure file, so all but the
        last would be lost without a word."""
        self.assertRejected(run_exp(figure=True, variants=(
            Variant("a", "a"), Variant("b", "b"))))

    def test_energy_rows_must_exist(self):
        """Caught here, not when the table is printed after the run."""
        self.assertRejected(run_exp(options=dict(energy_nodes=(7,))))

    def test_only_run_takes_variants(self):
        self.assertRejected(Experiment(
            name="v", kind="validate", description="", n_runs=3,
            sim_time_s=300.0, base_seed=7, node_counts=(10, 20),
            options=dict(scenario="SF8"),
            variants=(Variant("a", "a"), Variant("b", "b"))))


class TestShippedManifests(unittest.TestCase):
    """Every shipped experiment resolves to a study that validates, checked
    without simulating, so a broken manifest fails here in milliseconds."""

    def test_every_experiment_variant_validates(self):
        found = 0
        for name in study_mod.list_studies():
            if not reproduce.has_manifest(name):
                continue
            base = study_mod.load_study(name)
            for exp in reproduce.load_manifest(name):
                for v in exp.variants:
                    found += 1
                    with self.subTest(study=name, experiment=exp.name,
                                      variant=v.name):
                        s = reproduce.effective_study(base, exp, v)
                        errors, _w, _i = study_mod.validate(s)
                        self.assertEqual(errors, [])
        self.assertGreater(found, 0, "no shipped study carries a manifest")


class TestCanonicalOutputsAreIsolated(TempStudy):
    """REGRESSION. A four-run check once replaced the eight-run validation a
    table was copied from, because every invocation wrote the same file."""

    def test_an_experiment_writes_into_its_own_directory(self):
        exp = run_exp(name="headline")
        summary = reproduce.run_experiment("tiny", exp, root=self.root,
                                           log=lambda *_: None)
        expected = os.path.join(self.root, "tiny", "outputs", "headline")
        for path in summary["written"]:
            self.assertEqual(os.path.dirname(path), expected)

    def test_an_ad_hoc_write_cannot_touch_it(self):
        exp = run_exp(name="headline")
        reproduce.run_experiment("tiny", exp, root=self.root, log=lambda *_: None)
        canonical = os.path.join(self.root, "tiny", "outputs", "headline",
                                 "results.json")
        with open(canonical, "rb") as f:
            before = f.read()

        s = study_mod.load_study("tiny", self.root)
        rows = experiment_mod.run_study(s, progress=False)
        _csv, adhoc = experiment_mod.write_results(s, rows, root=self.root)

        self.assertNotEqual(os.path.abspath(adhoc), os.path.abspath(canonical))
        with open(canonical, "rb") as f:
            self.assertEqual(f.read(), before)

    def test_variants_get_one_directory_each(self):
        exp = run_exp(name="pair", variants=(
            Variant("a", "A"), Variant("b", "B", {"shadowing_sigma_db": 6.0})))
        reproduce.run_experiment("tiny", exp, root=self.root, log=lambda *_: None)
        for v in ("a", "b"):
            self.assertTrue(os.path.isfile(os.path.join(
                self.root, "tiny", "outputs", "pair", v, "results.json")))


class TestEveryFileCarriesItsProvenance(TempStudy):
    """A JSON that cannot say how it was made cannot back a table."""

    REQUIRED = ("experiment", "kind", "n_runs", "sim_time_s", "base_seed",
                "node_counts", "n_bootstrap", "study", "code_sha256",
                "generated", "regenerate")

    def check_dir(self, exp):
        reproduce.run_experiment("tiny", exp, root=self.root, plot=False,
                                 log=lambda *_: None)
        d = os.path.join(self.root, "tiny", "outputs", exp.name)
        paths = list(self.json_files(d))
        self.assertTrue(paths)
        for path in paths:
            with open(path, encoding="utf-8") as f:
                prov = json.load(f).get("provenance")
            with self.subTest(file=os.path.basename(path)):
                self.assertIsNotNone(prov, f"{path} has no provenance")
                for key in self.REQUIRED:
                    self.assertIn(key, prov)
                self.assertEqual(prov["experiment"], exp.name)
                self.assertEqual(prov["n_runs"], exp.n_runs)
                self.assertEqual(prov["base_seed"], exp.base_seed)
                self.assertEqual(prov["sim_time_s"], exp.sim_time_s)
                # The recorded study is the one that RAN, not the base one.
                self.assertEqual(prov["study"]["n_runs"], exp.n_runs)
                self.assertEqual(prov["study"]["base_seed"], exp.base_seed)

    def test_run(self):
        self.check_dir(run_exp(name="run1"))

    def test_validate(self):
        self.check_dir(Experiment(
            name="val", kind="validate", description="", n_runs=2,
            sim_time_s=120.0, base_seed=7, node_counts=(5, 20),
            options=dict(scenario="SF8")))

    def test_intercept(self):
        self.check_dir(Experiment(
            name="icpt", kind="intercept", description="", n_runs=2,
            sim_time_s=120.0, base_seed=7,
            options=dict(scenario="SF8", n_nodes=20, offsets_db=(-5.0, 0.0))))

    def test_compare(self):
        self.check_dir(run_exp(
            name="cmp", kind="compare",
            options=dict(variant="exponent_only", terrain="rural")))

    def test_ad_hoc_files_say_they_are_ad_hoc(self):
        s = study_mod.load_study("tiny", self.root)
        prov = reproduce.adhoc_provenance(s, ["run", "tiny"])
        self.assertEqual(prov["source"], "ad hoc")
        self.assertIn("run tiny", prov["command"])
        self.assertIn("code_sha256", prov)


class TestTheSameConfigurationGivesTheSameNumber(TempStudy):
    """INVARIANT. The fitted row of a model comparison is the headline run
    under another command. With the same seed, grid, repetitions and
    bootstrap count it must be the same number to the last digit, which is
    what lets one quantity be quoted once instead of five ways."""

    def test_compare_fitted_equals_run(self):
        common = dict(n_runs=3, sim_time_s=300.0, base_seed=11,
                      node_counts=GRID, scenarios=("SF8",), n_bootstrap=200)
        run = run_exp(name="headline", **common)
        cmp = run_exp(name="cmp", kind="compare",
                      options=dict(variant="exponent_only", terrain="rural"),
                      **common)
        quiet = dict(root=self.root, plot=False, log=lambda *_: None)
        reproduce.run_experiment("tiny", run, **quiet)
        reproduce.run_experiment("tiny", cmp, **quiet)
        out = os.path.join(self.root, "tiny", "outputs")
        with open(os.path.join(out, "headline", "capacity.json"),
                  encoding="utf-8") as f:
            headline = json.load(f)["capacity"]["SF8"]
        with open(os.path.join(out, "cmp", "model_comparison.json"),
                  encoding="utf-8") as f:
            fitted = json.load(f)["comparison"]["variants"][0]["capacity"]["SF8"]
        self.assertIsNotNone(headline["capacity"])
        for key in ("capacity", "ci_low", "ci_high"):
            self.assertEqual(headline[key], fitted[key], key)


class TestIntervalDoesNotDependOnNeighbours(unittest.TestCase):
    """REGRESSION. With one bootstrap stream shared across scenarios, MULTI
    and SF7 had the same capacity on the worked example but intervals that
    differed, only because other scenarios were resampled first."""

    def test_a_scenario_interval_is_the_same_alone_or_with_others(self):
        from loracap import analysis
        rng = random.Random(1)
        rows = []
        for scen, slope in (("A", 0.002), ("B", 0.004)):
            for n in (5, 20, 40, 80):
                runs = [max(0.0, 1 - slope * n + rng.gauss(0, 0.02))
                        for _ in range(8)]
                rows.append({"scenario": scen, "n_nodes": n, "der_runs": runs,
                             "der_mean": sum(runs) / len(runs)})
        both = analysis.capacity_with_ci(rows, n_boot=300)
        alone = analysis.capacity_with_ci(
            [r for r in rows if r["scenario"] == "B"], n_boot=300)
        self.assertIsNotNone(both["B"]["capacity"])
        self.assertEqual(both["B"], alone["B"])


class TestOverridesReachTheEngine(TempStudy):

    def test_a_variant_override_changes_what_is_simulated(self):
        """A variant whose override was dropped would quietly rerun the base
        configuration and label it as something else."""
        exp = run_exp(name="sh", scenarios=("MULTI",), variants=(
            Variant("clear", "clear"),
            Variant("shadowed", "shadowed", {"shadowing_sigma_db": 12.0})))
        reproduce.run_experiment("tiny", exp, root=self.root, plot=False,
                                 log=lambda *_: None)
        d = os.path.join(self.root, "tiny", "outputs", "sh")
        loaded = {}
        for v in ("clear", "shadowed"):
            with open(os.path.join(d, v, "results.json"),
                      encoding="utf-8") as f:
                loaded[v] = json.load(f)
        self.assertEqual(loaded["shadowed"]["study"]["shadowing_sigma_db"], 12.0)
        self.assertEqual(loaded["clear"]["study"]["shadowing_sigma_db"], 0.0)
        spread = {v: [r["rssi_spread_db_mean"] for r in loaded[v]["results"]]
                  for v in loaded}
        self.assertNotEqual(spread["clear"], spread["shadowed"])


class TestNodesPerSpreadingFactor(unittest.TestCase):
    """Orthogonality between spreading factors is how ADR's margin buys
    capacity, so how the nodes are spread over them is reported."""

    def test_every_node_on_air_is_counted_once(self):
        cfg = helpers.config(shadowing_sigma_db=12.0)
        for scen in ("SF8", "MULTI", "ADR"):
            r = run_single_sim(cfg, 80, 120_000.0, scen, random.Random(3))
            with self.subTest(scenario=scen):
                self.assertEqual(sum(r["nodes_per_sf"].values())
                                 + r["unreachable_nodes"], 80)

    def test_a_fixed_rate_puts_everyone_on_it(self):
        r = run_single_sim(helpers.config(), 40, 120_000.0, "SF9",
                           random.Random(4))
        self.assertEqual(r["nodes_per_sf"], {9: 40})


class TestTables(TempStudy):

    def test_a_table_quotes_the_saved_numbers_and_says_where_from(self):
        exp = run_exp(name="headline")
        reproduce.run_experiment("tiny", exp, root=self.root, plot=False,
                                 log=lambda *_: None)
        text = reproduce.render_tables("tiny", exp, root=self.root)
        with open(os.path.join(self.root, "tiny", "outputs", "headline",
                               "capacity.json"),
                  encoding="utf-8") as f:
            cap = json.load(f)["capacity"]["SF8"]["capacity"]
        self.assertIn(f"{cap:.1f}", text)
        self.assertIn("experiment `headline`", text)
        self.assertIn("3 runs per point", text)
        self.assertIn("seed 7", text)
        self.assertIn("python3 run.py reproduce tiny --only headline", text)


if __name__ == "__main__":
    unittest.main()
