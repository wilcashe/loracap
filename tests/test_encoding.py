"""Every text file is read and written as UTF-8, whatever the platform.

The web page showed "Choose KMLâ€¦" for "Choose KML…" and "dâ‚€" for "d₀" on
Windows. The server opened index.html without naming an encoding, so Python
used the locale's, cp1252 on a Spanish Windows, and every non-ASCII character
in the page came out as two or three wrong ones. On Linux the locale is
UTF-8, which is why nothing here noticed. The study.py the web form writes
had the same fault in the other direction: written in cp1252, it is not
valid Python source, which is read as UTF-8.

Two checks. The first reads the source and requires every text-mode open()
to name its encoding, so the fault cannot come back anywhere, including in
code nobody thinks of as handling text. The second runs the three paths the
fault reached under a locale that is not UTF-8, in a child process, so the
symptom itself is checked and not only the rule meant to prevent it.
"""
import ast
import os
import subprocess
import sys
import textwrap
import unittest

from tests import helpers

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(helpers.__file__)))
CHECKED = ("loracap", "webui", "tools", "tests", "run.py")


def _python_files():
    for entry in CHECKED:
        path = os.path.join(ROOT, entry)
        if path.endswith(".py"):
            yield path
            continue
        for dirpath, _dirs, files in os.walk(path):
            for fn in files:
                if fn.endswith(".py"):
                    yield os.path.join(dirpath, fn)


def _opens_without_encoding(source: str):
    """Line numbers of open() calls in text mode that name no encoding.

    A mode that is not a literal counts as text mode, since nothing proves
    it binary, and a call with **kwargs is assumed to carry the encoding.
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "open"):
            continue
        kw = {k.arg for k in node.keywords}
        if "encoding" in kw or None in kw:
            continue
        mode = node.args[1] if len(node.args) > 1 else next(
            (k.value for k in node.keywords if k.arg == "mode"), None)
        if (isinstance(mode, ast.Constant) and isinstance(mode.value, str)
                and "b" in mode.value):
            continue
        found.append(node.lineno)
    return found


class TestEveryTextFileStatesItsEncoding(unittest.TestCase):

    def test_no_open_relies_on_the_locale(self):
        offenders = []
        for path in _python_files():
            with open(path, encoding="utf-8") as f:
                lines = _opens_without_encoding(f.read())
            offenders += [f"{os.path.relpath(path, ROOT)}:{n}" for n in lines]
        self.assertEqual(offenders, [], "open() without encoding= reads and "
                         "writes in the locale's encoding, cp1252 on a "
                         "Spanish Windows")

    def test_the_scan_reaches_every_part_that_opens_files(self):
        """The fault was in webui/, not in the package, so a scan narrowed
        to loracap/ would have passed while the page was broken."""
        scanned = {os.path.relpath(p, ROOT) for p in _python_files()}
        for path in ("run.py", "webui/server.py", "tools/kml_to_polygon.py",
                     "loracap/pathloss.py", "tests/test_reproduce.py"):
            self.assertIn(path, scanned)

    def test_the_scan_finds_what_it_is_meant_to(self):
        """A scan that finds nothing proves nothing unless it can find."""
        self.assertEqual(_opens_without_encoding(
            "open(p)\nopen(p, 'w')\nopen(p, mode='r')\nopen(p, m)\n"),
            [1, 2, 3, 4])
        self.assertEqual(_opens_without_encoding(
            "open(p, 'rb')\nopen(p, mode='wb')\nopen(p, encoding='utf-8')\n"
            "open(p, 'w', encoding='utf-8')\nopen(p, **kw)\nf.open(p)\n"),
            [])


CHILD = textwrap.dedent(r'''
    import io, locale, os, shutil, sys, tempfile, threading, urllib.request
    from unittest import mock
    sys.path.insert(0, os.getcwd())
    if locale.getpreferredencoding(False).lower().replace("-", "") == "utf8":
        print("SKIP"); sys.exit(0)

    from http.server import ThreadingHTTPServer
    from loracap import pathloss, study as study_mod
    from tests.test_webui import form_values
    from webui import server

    # 1. The page, as a browser receives it.
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    page = urllib.request.urlopen(url).read().decode("utf-8")
    httpd.shutdown()
    print("page", "Choose KML\u2026" in page and "d\u2080" in page
          and "\u00e2\u20ac" not in page)

    # 2. A study written by the form, with non-ASCII text, loaded back.
    root = tempfile.mkdtemp()
    source = "Gonzalez-Palacio et al., the review\u2019s \u03c3 = 7.4 dB"
    with mock.patch.object(study_mod, "studies_root", lambda start=None: root):
        server.api_create({"values": form_values(path_loss_source=source)})
        loaded = study_mod.load_study("formtest", root)
    shutil.rmtree(root, True)
    print("study", loaded.path_loss_source == source)

    # 3. A measurements CSV saved with a byte-order mark, as Excel does.
    fd, csv_path = tempfile.mkstemp(suffix=".csv")
    os.write(fd, "\ufeffrssi,latitude,longitude,site\n-100,3.9,-73.8,Guamal\u2013Meta\n"
             .encode("utf-8")); os.close(fd)
    header, rows = pathloss.read_csv(csv_path)
    os.remove(csv_path)
    print("csv", header[0] == "rssi" and rows[0]["site"] == "Guamal\u2013Meta")
''')


def _non_utf8_env():
    return {"PATH": os.environ.get("PATH", ""), "LC_ALL": "C", "LANG": "C",
            "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0",
            "PYTHONDONTWRITEBYTECODE": "1"}


class TestRedirectedOutput(unittest.TestCase):
    """Redirected to a file, the command line printed in the locale's
    encoding, and `reproduce reference` stopped at the first character it
    could not encode."""

    def test_reference_tables_redirected_under_a_non_utf8_locale(self):
        probe = subprocess.run(
            [sys.executable, "-c", "import locale;"
             "print(locale.getpreferredencoding(False))"],
            env=_non_utf8_env(), capture_output=True, text=True)
        if probe.stdout.strip().lower().replace("-", "") == "utf8":
            self.skipTest("this platform cannot run Python in a non-UTF-8 "
                          "locale")
        r = subprocess.run([sys.executable, "run.py", "reproduce", "reference"],
                           cwd=ROOT, env=_non_utf8_env(), capture_output=True,
                           timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        self.assertIn("BW\u2082/BW\u2081", r.stdout.decode("utf-8"))


    def test_a_terminal_that_cannot_show_a_character_does_not_stop(self):
        try:
            import pty
        except ImportError:
            self.skipTest("no pseudo-terminal on this platform")
        master, slave = pty.openpty()
        code = ("import sys; sys.path.insert(0, '.'); import run; "
                "run._utf8_output(); print('BW\\u2082 ok')")
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                           env=_non_utf8_env(), stdout=slave,
                           stderr=subprocess.PIPE, timeout=60)
        os.close(slave)
        try:
            raw = os.read(master, 1024)
        except OSError:     # nothing was written before the child exited
            raw = b""
        os.close(master)
        if "\u2082".encode("utf-8") in raw:
            self.skipTest("the terminal here encodes UTF-8 anyway")
        shown = raw.decode("ascii", "replace")
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        self.assertIn("BW? ok", shown)


class TestUnderANonUtf8Locale(unittest.TestCase):
    """The ASCII locale is stricter than cp1252, where the fault showed: a
    character it cannot decode is an error instead of a wrong character, so
    a regression fails loudly here rather than printing garbage."""

    @classmethod
    def setUpClass(cls):
        r = subprocess.run([sys.executable, "-c", CHILD], cwd=ROOT,
                           env=_non_utf8_env(),
                           capture_output=True, text=True, encoding="utf-8",
                           timeout=120)
        cls.out = r.stdout.split("\n")
        cls.err = r.stderr

    def setUp(self):
        if "SKIP" in self.out:
            self.skipTest("this platform cannot run Python in a non-UTF-8 "
                          "locale")

    def _line(self, what):
        for line in self.out:
            if line.startswith(what + " "):
                return line
        self.fail(f"the child never reached {what!r}:\n{self.err[-1500:]}")

    def test_the_page_arrives_intact(self):
        self.assertEqual(self._line("page"), "page True")

    def test_a_study_from_the_form_loads_back_unchanged(self):
        self.assertEqual(self._line("study"), "study True")

    def test_a_measurements_csv_with_a_byte_order_mark_reads(self):
        self.assertEqual(self._line("csv"), "csv True")


if __name__ == "__main__":
    unittest.main()
