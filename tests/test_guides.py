"""The first-use guides quote the code (design item 48).

docs/GETTING_STARTED.md and docs/GUIA_DE_INICIO.md tell a reader new to
Python what to type, what the example prints and what the page calls each
button. Every one of those quotations has a source in the repository, and
this module compares each against it, so a renamed button, a changed
default or a regenerated example fails here instead of leaving a guide that
describes a program that no longer exists. The README's own layout said 528
tests long after there were more, which is the drift this guards against.
"""
import json
import os
import re
import unittest

from tests import helpers  # noqa: F401  (puts the package on sys.path)

from loracap import analysis, pathloss, presets
from loracap import study as study_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN = os.path.join(ROOT, "docs", "GETTING_STARTED.md")
ES = os.path.join(ROOT, "docs", "GUIA_DE_INICIO.md")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _flat(text):
    return " ".join(text.split())


# Labels the guides name, as the page shows them in each language. The
# English is the page's own text (and its key in i18n_es.json); the Spanish
# is that key's translation.
PAGE_LABELS = (
    ("Basic", "Básico"),
    ("Advanced", "Avanzado"),
    ("Checks", "Comprobaciones"),
    ("Choose KML…", "Elegir KML…"),
    ("I have field measurements", "Tengo mediciones de campo"),
    ("Choose measurements CSV…", "Elegir CSV de mediciones…"),
    ("Use", "Usar"),
    ("doubtful", "dudoso"),
    ("Write study.py", "Escribir study.py"),
    ("Run simulation", "Ejecutar la simulación"),
    ("6. Output", "6. Salida"),
    ("no crossing", "sin cruce"),
)

# Fit labels: the page shows these, with {width} filled from the bin width.
FIT_LABELS = (
    ("unbinned", "sin agrupar"),
    ("binned ({width} m)", "agrupado ({width} m)"),
    ("per position", "por posición"),
)


class TestTheGuidesAreFound(unittest.TestCase):
    def test_each_guide_links_the_other_and_the_readme_links_both(self):
        en, es, readme = _read(EN), _read(ES), _read(os.path.join(ROOT, "README.md"))
        self.assertIn("(GUIA_DE_INICIO.md)", en)
        self.assertIn("(GETTING_STARTED.md)", es)
        self.assertIn("(docs/GETTING_STARTED.md)", readme)
        self.assertIn("(docs/GUIA_DE_INICIO.md)", readme)
        for text in (en, es):
            self.assertIn("(../README.md)", text)


class TestTheExampleIsQuotedAsItRuns(unittest.TestCase):
    """The plain `run iot4cows` the guides walk through is the `headline`
    experiment, whose committed capacity.json is what a reader must get."""

    @classmethod
    def setUpClass(cls):
        cls.study = study_mod.load_study("iot4cows")
        with open(os.path.join(ROOT, "studies", "iot4cows", "outputs", "headline",
                               "capacity.json"), encoding="utf-8") as f:
            cls.cap = json.load(f)
        errors, warnings, info = study_mod.validate(cls.study)
        cls.report = study_mod.format_report(cls.study, errors, warnings, info)

    def test_the_capacity_block_is_what_run_prints(self):
        block = analysis.format_capacity(self.cap["capacity"], self.cap["der_threshold"])
        for path in (EN, ES):
            self.assertIn(block, _read(path), path)

    def test_the_quoted_check_line_is_what_check_prints(self):
        m = re.search(r"```\n(SF9 reaches .*?)```", _read(EN), re.S)
        self.assertIsNotNone(m)
        quoted = _flat(m.group(1))
        self.assertIn(quoted, _flat(self.report))
        self.assertIn(m.group(1), _read(ES))

    def test_the_example_settings_the_guides_state(self):
        s = self.study
        self.assertEqual(s.payload_bytes, 32)
        self.assertEqual(s.send_interval_s, 15.0)
        self.assertEqual(tuple(s.scenarios), ("SF7", "SF8", "SF9"))
        self.assertEqual(len(s.node_counts), 27)
        self.assertEqual(s.n_runs, 30)
        self.assertEqual(s.der_threshold, 0.9)
        area = float(re.search(r"Deployment area: ([\d.]+) ha", self.report).group(1))
        self.assertEqual(f"{area:.1f}", "88.5")
        en, es = _flat(_read(EN)), _flat(_read(ES))
        self.assertIn("81 points (3 scenarios times 27 node counts), 30 runs each", en)
        self.assertIn("81 puntos (3 escenarios por 27 cantidades de nodos), con 30", es)
        self.assertIn("a 32-byte payload and a report every 15 seconds", en)
        self.assertIn("un payload de 32 bytes y un reporte cada 15 segundos", es)
        self.assertIn("an 88.5 ha site", en)
        self.assertIn("un sitio de 88.5 ha", es)


class TestTheGuidesAgreeWithTheReadme(unittest.TestCase):
    def setUp(self):
        self.readme = _read(os.path.join(ROOT, "README.md"))
        self.en, self.es = _flat(_read(EN)), _flat(_read(ES))

    def test_the_oldest_python(self):
        oldest = re.search(r"Python (3\.\d+) or newer", self.readme).group(1)
        self.assertIn(f"Python {oldest} or newer", self.en)
        self.assertIn(f"Python {oldest} o posterior", self.es)

    def test_the_test_count(self):
        count = re.search(r"(\d+) checks, about twenty seconds", self.readme).group(1)
        self.assertIn(f"This runs {count} checks", self.en)
        self.assertIn(f"corre {count} pruebas", self.es)
        self.assertIn(f"tests/ {count} fast checks", _flat(self.readme))

    def test_the_count_is_the_suite_itself(self):
        # A module that cannot import without matplotlib is counted as one
        # skipped case, so the count is only exact where it imports.
        try:
            import matplotlib  # noqa: F401
        except ImportError:
            self.skipTest("matplotlib is not installed, so the figure modules count once each")
        suite = unittest.TestLoader().discover(os.path.join(ROOT, "tests"), top_level_dir=ROOT)
        count = re.search(r"(\d+) checks, about twenty seconds", self.readme).group(1)
        self.assertEqual(suite.countTestCases(), int(count))


class TestThePageIsNamedAsItReads(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _read(os.path.join(ROOT, "webui", "index.html"))
        cls.es_strings = json.loads(_read(os.path.join(ROOT, "webui", "i18n_es.json")))["strings"]
        cls.en, cls.es = _flat(_read(EN)), _flat(_read(ES))

    def test_each_label_is_the_pages_own(self):
        for en, es in PAGE_LABELS:
            self.assertEqual(self.es_strings.get(en), es, en)
            # On the page as markup (>Label<) or as text the script writes ('Label').
            self.assertTrue(f">{en}<" in self.html or f"'{en}'" in self.html, en)
            self.assertIn(f'"{en}"', self.en, en)
            self.assertIn(f'"{es}"', self.es, es)

    def test_the_fit_labels_and_their_bin_width(self):
        import inspect
        width = inspect.signature(pathloss.analyse).parameters["bin_width_m"].default
        self.assertEqual(width, 10.0)
        for en, es in FIT_LABELS:
            self.assertEqual(self.es_strings.get(en), es, en)
            self.assertIn("| " + en.replace("{width}", "10") + " |", self.en)
            self.assertIn("| " + es.replace("{width}", "10") + " |", self.es)

    def test_the_address_and_port(self):
        run_py = _read(os.path.join(ROOT, "run.py"))
        self.assertIn('"--port", type=int, default=8765', run_py)
        for text in (self.en, self.es):
            self.assertIn("http://127.0.0.1:8765/", text)
            self.assertIn("python3 run.py serve --port 8800", text)

    def test_the_page_starts_from_3_to_300_nodes(self):
        self.assertEqual(list(study_mod.Study.__dataclass_fields__["node_counts"]
                              .default_factory()), study_mod.node_counts_logspace(3, 300))
        server = _read(os.path.join(ROOT, "webui", "server.py"))
        self.assertIn('"default_node_counts": study_mod.node_counts_logspace(3, 300)', server)
        self.assertIn("3 to 300 on a study written by the page", _flat(self.en))
        self.assertIn("de 3 a 300 en un estudio escrito por la página", _flat(self.es))


class TestTheRulesTheGuidesState(unittest.TestCase):
    def setUp(self):
        self.en, self.es = _flat(_read(EN)), _flat(_read(ES))

    def test_the_regions_that_ask_for_the_dwell_time(self):
        self.assertEqual(set(presets.DWELL_TIME_REGIONS), {"AU915", "AS923"})
        self.assertIn("AU915 and AS923 also ask for the uplink dwell time", self.en)
        self.assertIn("AU915 y AS923 piden además el uplink dwell time", self.es)

    def test_what_marks_a_fit_doubtful(self):
        low, high = presets.measured_exponent_span()
        self.assertEqual(pathloss.NO_TREND_R2, 0.15)
        self.assertIn(f"an exponent outside {low} to {high}", self.en)
        self.assertIn("less than 15% of the spread in RSSI", self.en)
        self.assertIn(f"exponente fuera de {low} a {high}", self.es)
        self.assertIn("menos del 15 % de la dispersión del RSSI", self.es)

    def test_the_30_m_floor(self):
        import inspect
        floor = inspect.signature(pathloss.analyse).parameters["min_distance_m"].default
        self.assertEqual(floor, 30.0)
        self.assertIn("closer than 30 m to the gateway are left out by default", self.en)
        self.assertIn("a menos de 30 m del gateway se excluyen por defecto", self.es)

    def test_a_decimal_comma_gives_the_message_quoted(self):
        quoted = "use a comma as the decimal mark"
        rows = "".join(f"-8{i % 10};3,9{i:02d};-73,8\n" for i in range(20))
        header, rows = pathloss.read_csv("rssi;latitude;longitude\n" + rows, is_text=True)
        with self.assertRaises(ValueError) as caught:
            pathloss.analyse(header, rows, 3.9, -73.8)
        self.assertIn(quoted, str(caught.exception))
        for text in (self.en, self.es):
            self.assertIn(f'"{quoted}"', text)

    def test_the_separators_and_encodings_the_guides_name(self):
        self.assertEqual([n for _d, n in pathloss.DELIMITERS],
                         ["comma", "semicolon", "tab"])
        self.assertEqual(pathloss.decode_measurements("ó".encode("utf-8"))[1], "UTF-8")
        self.assertEqual(pathloss.decode_measurements("ó".encode("cp1252"))[1],
                         "Windows-1252")
        self.assertIn("separated by commas, semicolons or tabs", self.en)
        self.assertIn("separadas por comas, punto y coma o tabuladores", self.es)

    def test_an_unknown_column_gives_the_message_quoted(self):
        quoted = "Could not find a column for rssi, latitude, longitude"
        with self.assertRaises(ValueError) as caught:
            pathloss.analyse(["a", "b"], [], 3.9, -73.8)
        self.assertIn(quoted, str(caught.exception))
        for text in (self.en, self.es):
            self.assertIn(f'"{quoted}"', text)

    def test_the_message_without_matplotlib(self):
        quoted = "matplotlib is not installed, so no figure was drawn."
        self.assertIn(quoted, _read(os.path.join(ROOT, "run.py")))
        for text in (self.en, self.es):
            self.assertIn(f'"{quoted}"', text)


if __name__ == "__main__":
    unittest.main()
