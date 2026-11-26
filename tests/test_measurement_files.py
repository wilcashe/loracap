"""Measurement files as spreadsheets save them (design item 49).

A spreadsheet set to Spanish saves "CSV" with semicolons between the columns,
in the Windows code page, and with decimal commas in the numbers. The fit read
commas and UTF-8 only: a semicolon file stopped with every column name joined
into one, a .tsv (which the page offers to open) the same way, and a
Windows-1252 file stopped the command-line tool with a Python traceback.

Now the separator is read from the header line, the text is UTF-8 or else
Windows-1252, and how the file was read is shown. A decimal comma is still
refused, by the user's decision, but by name and with the fix.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests import helpers
from tests.test_webui import PAGE

from loracap import pathloss
from webui import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GW = (3.9, -73.8)

# Forty points along a line from the gateway, RSSI falling 25 dB a decade with
# a fixed jitter. Written out with four decimals, so the same numbers come back
# from every separator and encoding.
_JITTER = (1.3, -0.7, 2.1, -1.9, 0.4, -0.2, 1.1, -2.4, 0.9, -1.2)


def _rows():
    import math
    out = []
    for i in range(40):
        d = 40 + 9 * i
        rssi = -55 - 25 * math.log10(d) + _JITTER[i % len(_JITTER)]
        out.append((f"{rssi:.4f}", f"{GW[0] + d / 111195:.6f}", f"{GW[1]:.6f}"))
    return out


def _text(sep, extra_name="ubicación", extra="lote ñ", rows=None):
    lines = [sep.join(["rssi", "latitude", "longitude", extra_name])]
    lines += [sep.join(list(r) + [extra]) for r in (rows or _rows())]
    return "\n".join(lines) + "\n"


def _fits(text):
    header, rows = pathloss.read_csv(text, is_text=True)
    return pathloss.analyse(header, rows, *GW)["fits"]


class TestTheSeparator(unittest.TestCase):

    def test_every_separator_gives_the_same_fit(self):
        reference = _fits(_text(","))
        for sep in (";", "\t"):
            self.assertEqual(_fits(_text(sep)), reference, repr(sep))

    def test_the_separator_is_named(self):
        for sep, name in ((",", "comma"), (";", "semicolon"), ("\t", "tab")):
            _h, _r, fmt = pathloss.read_measurements(_text(sep), is_text=True)
            self.assertEqual(fmt, {"delimiter": name, "encoding": None})

    def test_decimal_commas_do_not_pull_it_to_the_comma(self):
        text = "rssi;latitude;longitude\n" + "".join(
            f"-83,5;3,9{i:02d};-73,8\n" for i in range(5))
        self.assertEqual(pathloss.sniff_delimiter(text), (";", "semicolon"))

    def test_a_quoted_separator_in_a_name_is_not_a_separator(self):
        self.assertEqual(pathloss.sniff_delimiter('rssi,"note; free text",latitude,longitude\n'),
                         (",", "comma"))
        self.assertEqual(pathloss.sniff_delimiter('rssi;"lat,lon";latitude;longitude\n'),
                         (";", "semicolon"))
        # Split blindly, this header has six fields by semicolon and four by comma. Read as
        # CSV, the quoted name is one field and the commas separate four.
        self.assertEqual(pathloss.sniff_delimiter(
            '"note; one; two; three; four; five",rssi,latitude,longitude\n'), (",", "comma"))

    def test_one_column_or_blank_lines_first_go_to_the_comma(self):
        self.assertEqual(pathloss.sniff_delimiter("rssi\n-80\n"), (",", "comma"))
        self.assertEqual(pathloss.sniff_delimiter("\n\nrssi;latitude\n"), (";", "semicolon"))

    def test_read_csv_still_returns_two_values(self):
        header, rows = pathloss.read_csv(_text(";"), is_text=True)
        self.assertEqual(header[:3], ["rssi", "latitude", "longitude"])
        self.assertEqual(len(rows), 40)


class TestTheEncoding(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def _file(self, name, data):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_utf8_with_and_without_its_mark_and_windows_1252(self):
        text = _text(";")
        cases = (("plain.csv", text.encode("utf-8"), "UTF-8"),
                 ("bom.csv", b"\xef\xbb\xbf" + text.encode("utf-8"), "UTF-8"),
                 ("excel.csv", text.encode("cp1252"), "Windows-1252"))
        reference = _fits(text)
        for name, data, encoding in cases:
            header, rows, fmt = pathloss.read_measurements(self._file(name, data))
            self.assertEqual(fmt, {"delimiter": "semicolon", "encoding": encoding}, name)
            # The accent survives, so a column named with one is still found.
            self.assertEqual(header[3], "ubicación", name)
            self.assertEqual(rows[0]["ubicación"], "lote ñ", name)
            self.assertEqual(pathloss.analyse(header, rows, *GW)["fits"], reference, name)

    def test_text_in_neither_is_refused_by_name(self):
        # 0x81 has no character in Windows-1252, and 0xff starts nothing in UTF-8.
        with self.assertRaises(ValueError) as caught:
            pathloss.decode_measurements(b"rssi\n\x81\xff\n")
        self.assertIn("neither UTF-8 nor Windows-1252", str(caught.exception))


class TestADecimalComma(unittest.TestCase):

    def test_in_every_row_it_is_an_error_that_names_a_value(self):
        rows = [tuple(v.replace(".", ",") for v in r) for r in _rows()]
        with self.assertRaises(ValueError) as caught:
            _fits(_text(";", rows=rows))
        message = str(caught.exception)
        self.assertIn("No rows had usable RSSI and coordinates.", message)
        self.assertIn(f"'{rows[0][0]}' use a comma as the decimal mark", message)
        self.assertIn("Save the file with a point as the decimal mark.", message)

    def test_in_some_rows_it_is_a_warning_with_the_count(self):
        rows = _rows()
        rows[3:8] = [tuple(v.replace(".", ",") for v in r) for r in rows[3:8]]
        header, data = pathloss.read_csv(_text(";", rows=rows), is_text=True)
        res = pathloss.analyse(header, data, *GW)
        self.assertEqual(res["n_skipped"], 5)
        self.assertEqual(res["n_usable"], 35)
        notes = [w for w in res["warnings"] if w["kind"] == "decimal_comma"]
        self.assertEqual(len(notes), 1)
        self.assertIn("5 of 40 rows were skipped.", notes[0]["message"])
        self.assertIn("use a comma as the decimal mark", notes[0]["message"])

    def test_other_unreadable_values_are_counted_without_that_note(self):
        rows = _rows()
        rows[3:8] = [("NA", r[1], r[2]) for r in rows[3:8]]
        header, data = pathloss.read_csv(_text(",", rows=rows), is_text=True)
        res = pathloss.analyse(header, data, *GW)
        self.assertEqual(res["n_skipped"], 5)
        self.assertEqual([w for w in res["warnings"] if w["kind"] == "decimal_comma"], [])

    def test_a_decimal_comma_is_never_read_as_a_number(self):
        # Converting it would read a file that mixes both marks half one way
        # and half the other, so the value stays unread whatever the separator.
        rows = _rows()
        rows[0] = ('"' + rows[0][0].replace(".", ",") + '"', rows[0][1], rows[0][2])
        header, data = pathloss.read_csv(_text(",", rows=rows), is_text=True)
        res = pathloss.analyse(header, data, *GW)
        self.assertEqual((res["n_usable"], res["n_skipped"]), (39, 1))


class TestTheServer(unittest.TestCase):

    def test_the_separator_travels_back(self):
        for sep, name in ((",", "comma"), (";", "semicolon"), ("\t", "tab")):
            res = server.api_fit({"csv": _text(sep), "lat": GW[0], "lon": GW[1]})
            self.assertEqual(res["file_format"], {"delimiter": name})
            self.assertEqual(res["fits"], _fits(_text(",")))


class TestTheTool(unittest.TestCase):

    def _run(self, data):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        path = os.path.join(d, "field.csv")
        with open(path, "wb") as f:
            f.write(data)
        # The whole environment is kept: Python does not start on Windows
        # without SYSTEMROOT (design item 45).
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", "fit_path_loss.py"), path,
             "--lat", str(GW[0]), "--lon", str(GW[1])],
            capture_output=True, text=True, encoding="utf-8", env=dict(os.environ))

    def test_a_windows_1252_file_is_read_and_said_so(self):
        r = self._run(_text(";").encode("cp1252"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("as Windows-1252 text, columns separated by semicolons.", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_a_decimal_comma_stops_with_the_message(self):
        rows = [tuple(v.replace(".", ",") for v in r) for r in _rows()]
        r = self._run(_text(";", rows=rows).encode("utf-8"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("use a comma as the decimal mark", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_text_in_neither_stops_with_the_message(self):
        r = self._run(b"rssi,latitude,longitude\n\x81\xff,1,2\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("neither UTF-8 nor Windows-1252", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node is not installed")
class TestThePage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(PAGE, encoding="utf-8") as f:
            cls.html = f.read()

    def _node(self, js):
        r = helpers.run_node(js)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_the_bytes_are_decoded_as_python_decodes_them(self):
        fn = re.search(r"(function decodeCsv\(.*?\n\})", self.html, re.S).group(1)
        text = _text(";")
        cases = [list(text.encode("utf-8")), list(b"\xef\xbb\xbf" + text.encode("utf-8")),
                 list(text.encode("cp1252"))]
        got = self._node(fn + "\nconsole.log(JSON.stringify(%s.map(b=>"
                         "decodeCsv(new Uint8Array(b)))));" % json.dumps(cases))
        expected = [pathloss.decode_measurements(bytes(b)) for b in cases]
        self.assertEqual([[g["text"], g["encoding"]] for g in got],
                         [[t, e] for t, e in expected])
        self.assertEqual(got[1]["text"], text)   # the mark is dropped

    def test_bytes_python_refuses_the_page_refuses(self):
        fn = re.search(r"(function decodeCsv\(.*?\n\})", self.html, re.S).group(1)
        refused = [b"rssi\n" + bytes([c]) + b"\xe9\n" for c in (0x81, 0x8D, 0x8F, 0x90, 0x9D)]
        accepted = [b"rssi\n\x80\xe9\n"]   # the euro sign, then an accent
        for data in refused:
            with self.assertRaises(ValueError):
                pathloss.decode_measurements(data)
        self.assertEqual(pathloss.decode_measurements(accepted[0])[1], "Windows-1252")
        got = self._node(fn + "\nconsole.log(JSON.stringify(%s.map(b=>"
                         "decodeCsv(new Uint8Array(b)))));"
                         % json.dumps([list(b) for b in refused + accepted]))
        self.assertEqual(got[:5], [None] * 5)
        self.assertEqual(got[5], {"text": "rssi\n€é\n", "encoding": "Windows-1252"})

    def _render(self, res):
        """showFit run on a stand-in for the page, returning the first three
        messages as (class, text) in English and in Spanish."""
        show = re.search(r"(function showFit\(.*?\n\})", self.html, re.S).group(1)
        words = re.search(r"(const SEPARATOR_WORD=\{.*?\};)", self.html).group(1)
        with open(os.path.join(ROOT, "webui", "i18n_es.json"), encoding="utf-8") as f:
            es = json.load(f)["strings"]
        js = "\n".join([
            "function mk(tag,cls,text){ return {tag, cls:cls||'', text:text||'', kids:[],"
            " title:'', append(...x){this.kids.push(...x);}, appendChild(x){this.kids.push(x);"
            " return x;}, set innerHTML(v){this.kids=[];}}; }",
            "const ES=%s; let LANG='en';" % json.dumps(es, ensure_ascii=False),
            "const fill=(t,v)=>t.replace(/\\{(\\w+)\\}/g,(m,k)=>{const x=v[k];"
            " return typeof x==='function'?x():String(x);});",
            "const T=(k,v)=>fill(LANG==='en'?k:(ES[k]||k), v||{});",
            "const tset=(el,k)=>{ el.text=k; return el; }, tsetx=tset;",
            "const msgT=(kind,k,v)=>{ const d=mk('div','msg '+kind); d.key=k; d.vars=v; return d; };",
            "const msgEn=(kind,t)=>mk('div','en '+kind,t), useFit=()=>{};",
            "let CSVENCODING='Windows-1252';",
            words,
            "const out=mk('div'), $=id=>out;",
            show,
            "showFit(%s);" % json.dumps(res),
            "const said=[]; for(const lang of ['en','es']){ LANG=lang;",
            "  said.push(out.kids.slice(0,3).map(d=>[d.cls, d.key ? T(d.key, d.vars) : d.text])); }",
            "console.log(JSON.stringify(said));"])
        return self._node(js)

    def test_the_file_is_described_above_the_numbers_in_both_languages(self):
        res = server.api_fit({"csv": _text(";"), "lat": GW[0], "lon": GW[1]})
        res.update(n_skipped=3, equipment=None)
        en, es_ = self._render(res)
        self.assertEqual(en[0], ["msg i", "Columns separated by semicolons, "
                                          "text read as Windows-1252."])
        self.assertEqual(en[1], ["msg w", "Rows skipped because a value could not be "
                                          "read as a number: 3."])
        self.assertEqual(es_[0], ["msg i", "Columnas separadas por punto y coma, "
                                           "texto leído como Windows-1252."])
        self.assertEqual(es_[1], ["msg w", "Filas descartadas porque un valor no se pudo "
                                           "leer como número: 3."])
        self.assertTrue(en[2][1].startswith("40 usable rows"), en[2])

    def test_no_skipped_line_when_nothing_was_skipped(self):
        res = server.api_fit({"csv": _text("\t"), "lat": GW[0], "lon": GW[1]})
        res.update(equipment=None)
        self.assertEqual(res["n_skipped"], 0)
        en, _es = self._render(res)
        self.assertEqual(en[0][1], "Columns separated by tabs, text read as Windows-1252.")
        # The line after the description is the usable-rows count, the same
        # line the test above finds third.
        self.assertTrue(en[1][1].startswith("40 usable rows"), en[1])

if __name__ == "__main__":
    unittest.main()
