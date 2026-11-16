"""The web page in Spanish (design item 27).

The page's English is the key of every translation, as in gettext, and the
Spanish lives in webui/i18n_es.json. A translation can fail in two quiet
ways: a text with no Spanish entry falls back to English, and an entry whose
English no longer exists is never used. Neither raises an error, so both are
checked here, in both directions, for every place the page's text comes
from:

  the markup        elements marked data-i18n, keyed by their English
                    innerHTML, and attributes named by data-i18n-attr;
  the script        literal keys passed to T, htmlT, tset and msgT;
  the form's names  the FIELDS labels a check message is rewritten with, and
                    the glossary of abbreviations;
  the server        notes, ranges and table names in the bootstrap, the
                    errors server.py raises and the warnings it writes, and
                    the labels a fit carries.

What the simulator writes (check messages, a fit's warnings, the text of a
sweep, sources) is not translated, by the scope decided for the item, and is
not checked here.

Text in the markup that is not marked is an error unless it is a name that
reads the same in both languages, so a sentence added later without a mark
fails here rather than showing in English on a Spanish page.
"""
import ast
import json
import os
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser

from tests import helpers  # noqa: F401  (puts the package on sys.path)
from tests.test_webui import PAGE

from loracap import presets
from webui import server

WEBUI = os.path.dirname(PAGE)
DICT = os.path.join(WEBUI, "i18n_es.json")
SERVER = os.path.join(WEBUI, "server.py")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_es():
    return json.loads(_read(DICT))["strings"]


# ---------------------------------------------------------------------------
# The markup
# ---------------------------------------------------------------------------

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "source", "track", "wbr"}
# Text that reads the same in both languages: a name, a format, a symbol.
SAME_IN_BOTH = re.compile(
    r"^(LoRaCAP|English|Español|PDF|SVG|PNG|4/5 \(LoRaWAN\)|4/[5-8]|"
    r"[\w.]+\.(?:py|json|csv)|[*:.,…]|)$")
TRANSLATED_ATTRS = ("placeholder", "title", "aria-label", "data-name")
# Attribute values that read the same in both languages.
SAME_ATTRS = {"Language / Idioma"}


def _esc_text(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace("\xa0", "&nbsp;"))


def _esc_attr(v):
    return v.replace("&", "&amp;").replace('"', "&quot;").replace("\xa0", "&nbsp;")


def i18n_key(html):
    """The key the page computes: its innerHTML with whitespace collapsed."""
    return re.sub(r"\s+", " ", html).strip()


class _Markup(HTMLParser):
    """Reads the page's markup the way the browser serialises it, which is
    what the script's innerHTML returns and so what it looks keys up by."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.keys, self.attr_keys = [], []
        self.unmarked_text, self.unmarked_attrs = [], []
        self._stack = []          # (tag, recording-depth marker)
        self._rec = None          # [buffer, depth] while inside data-i18n
        self._skip = 0            # inside script, style or code

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        names = (a.get("data-i18n-attr") or "").split(",")
        for n in TRANSLATED_ATTRS:
            if n in a and a[n] is not None:
                if n in names:
                    self.attr_keys.append(i18n_key(a[n]))
                elif a[n] not in SAME_ATTRS:
                    self.unmarked_attrs.append((tag, n, a[n]))
        if self._rec is not None:
            self._rec[0].append("<" + tag + "".join(
                f' {k}="{_esc_attr(v if v is not None else "")}"' for k, v in attrs) + ">")
            if tag not in VOID:
                self._rec[1] += 1
            return
        if tag in ("script", "style", "code"):
            self._skip += 1
        if "data-i18n" in a and tag not in VOID:
            self._rec = [[], 1]

    def handle_endtag(self, tag):
        if self._rec is not None:
            self._rec[1] -= 1
            if self._rec[1] == 0:
                self.keys.append(i18n_key("".join(self._rec[0])))
                self._rec = None
            else:
                self._rec[0].append("</" + tag + ">")
            return
        if tag in ("script", "style", "code"):
            self._skip -= 1

    def handle_data(self, data):
        if self._rec is not None:
            self._rec[0].append(_esc_text(data))
        elif not self._skip and not SAME_IN_BOTH.match(data.strip()):
            self.unmarked_text.append(data.strip())


def markup():
    html = _read(PAGE)
    body = html[html.index("<body>"):html.index("<script>")]
    p = _Markup()
    p.feed(body)
    p.close()
    return p


# ---------------------------------------------------------------------------
# The script
# ---------------------------------------------------------------------------

def script():
    html = _read(PAGE)
    return html[html.index("<script>"):html.index("</script>")]


def _js_unescape(lit):
    out, i = [], 0
    while i < len(lit):
        c = lit[i]
        if c == "\\":
            n = lit[i + 1]
            if n == "u":
                out.append(chr(int(lit[i + 2:i + 6], 16)))
                i += 6
                continue
            out.append({"n": "\n", "t": "\t"}.get(n, n))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _args(js, start):
    """The source of each argument of the call whose '(' is at start-1."""
    args, depth, cur, i = [], 0, [], start
    while i < len(js):
        c = js[i]
        if c in "'\"":
            j = i + 1
            while js[j] != c:
                j += 2 if js[j] == "\\" else 1
            cur.append(js[i:j + 1])
            i = j + 1
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                args.append("".join(cur).strip())
                return args
            depth -= 1
        elif c == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    raise ValueError("unbalanced call at %d" % start)


LITERAL = re.compile(r"^'(?:[^'\\]|\\.)*'(?:\s*\+\s*'(?:[^'\\]|\\.)*')*$")
# Each translating function, and which of its arguments is the key.
CALLS = {"T": 0, "htmlT": 0, "tset": 1, "msgT": 1}


def script_calls():
    """(function, key source) for every call of a translating function, and
    the literal keys among them."""
    js = script()
    calls = []
    for fn, pos in CALLS.items():
        for m in re.finditer(r"(?<![\w$.])" + fn + r"\(", js):
            if re.search(r"function\s+$", js[:m.start()][-12:]):
                continue
            calls.append((fn, _args(js, m.end())[pos]))
    return calls


def literal_value(src):
    return "".join(_js_unescape(x[1:-1]) for x in re.findall(r"'(?:[^'\\]|\\.)*'", src))


def script_keys():
    return [literal_value(src) for _fn, src in script_calls() if LITERAL.match(src)]


def _js_object_body(name):
    js = script()
    return re.search(r"const " + name + r"=\{(.*?)\n\};", js, re.S).group(1)


def field_labels():
    return [_js_unescape(lbl) for lbl in
            re.findall(r"\w+:\['\w+','((?:[^'\\]|\\.)*)'\]", _js_object_body("FIELDS"))]


def glossary():
    body = _js_object_body("TERMS")
    return [(_js_unescape(k), _js_unescape(v)) for k, v in
            re.findall(r"^\s+'?([A-Za-z ]+)'?:'((?:[^'\\]|\\.)*)'", body, re.M)]


# ---------------------------------------------------------------------------
# The server
# ---------------------------------------------------------------------------

def bootstrap_texts():
    """Every sentence the bootstrap carries that the page shows translated.
    Sources are citations and stay as written, so they are not here."""
    b = server.api_bootstrap({})
    out = [m["note"] for m in b["receiver_models"]]
    out += [b[k] for k in ("capture_threshold_note", "orthogonal_note",
                           "lock_survival_default_note", "header_recapture_note")]
    for t in b["inter_sf_tables"] + b["lock_survival_tables"]:
        out += [t["label"], t["short"]]
    out += [lim["text"] for lim in b["limits"].values()]
    out += list(b["terrains"])          # environments, named in sentences
    return out


def _render(node):
    """A message the server builds, with each value replaced by a sample, as
    the page receives it."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for i, v in enumerate(node.values):
            parts.append(v.value if isinstance(v, ast.Constant) else "S%d" % i)
        return "".join(parts)
    return None


def server_messages():
    """The errors server.py raises and the warnings it writes for the page.
    raise ValueError(str(e)) passes on the simulator's own message."""
    tree = ast.parse(_read(SERVER))
    out = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)
                and getattr(n.exc.func, "id", None) == "ValueError" and n.exc.args):
            text = _render(n.exc.args[0])
            if text is not None:
                out.append(text)
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "append" and isinstance(n.func.value, ast.Subscript)
                and getattr(n.func.value.slice, "value", None) == "warnings"):
            out.append(_render(n.args[0]))
    return out


def fit_labels():
    """The labels a fit carries, from a fit of a small synthetic campaign."""
    import math
    rows = ["latitude,longitude,rssi"]
    for i in range(60):
        d = 40 + i * 25.0
        lat = 4.0 + d / 111320.0
        rows.append(f"{lat:.7f},-73.0,{-40 - 30 * math.log10(d / 40):.1f}")
    r = server.api_fit({"csv": "\n".join(rows), "lat": 4.0, "lon": -73.0,
                        "tx_power_dbm": 14})
    return [f["label"] for f in r["fits"]]


# ---------------------------------------------------------------------------
# Looking a text up as the page does
# ---------------------------------------------------------------------------

def _template_re(key):
    names, parts = [], []
    for p in re.split(r"(\{\w+\})", key):
        m = re.fullmatch(r"\{(\w+)\}", p)
        if m:
            names.append(m.group(1))
            parts.append(r"([\s\S]+?)")
        else:
            parts.append(re.escape(p))
    return re.compile("^" + "".join(parts) + "$")


def lookup(es, text):
    """The entry the page's TX would use for a text, or None. Mirrors TXr in
    index.html: an exact entry first, then the longest template that fits."""
    if text in es:
        return text
    for key in sorted((k for k in es if re.search(r"\{\w+\}", k)), key=len, reverse=True):
        if _template_re(key).match(text):
            return key
    return None


# ---------------------------------------------------------------------------
# The tests
# ---------------------------------------------------------------------------

class TestEveryTextHasItsSpanish(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.es = load_es()

    def test_the_markup(self):
        m = markup()
        self.assertGreater(len(m.keys), 100)
        for k in m.keys + m.attr_keys:
            self.assertIn(k, self.es, k)

    def test_the_script(self):
        keys = script_keys()
        self.assertGreater(len(keys), 100)
        for k in keys:
            self.assertIn(k, self.es, k)

    def test_the_names_the_checks_use(self):
        for label in field_labels():
            self.assertIsNotNone(lookup(self.es, label), label)

    def test_the_glossary(self):
        for name, definition in glossary():
            self.assertIsNotNone(lookup(self.es, definition), definition)
            # An abbreviation is the same in both languages; a name in words
            # is not.
            if " " in name:
                self.assertIn(name, self.es, name)

    def test_what_the_bootstrap_carries(self):
        for text in bootstrap_texts():
            self.assertIsNotNone(lookup(self.es, text), text)

    def test_what_the_server_raises_and_warns(self):
        msgs = server_messages()
        self.assertGreater(len(msgs), 10)
        for text in msgs:
            self.assertIsNotNone(lookup(self.es, text), text)

    def test_the_labels_of_a_fit(self):
        for label in fit_labels():
            self.assertIsNotNone(lookup(self.es, label), label)


class TestNoEntryIsStale(unittest.TestCase):
    """An entry whose English is gone from the page is never used, and its
    Spanish drifts unnoticed from what the page says."""

    def test_every_entry_is_used(self):
        es = load_es()
        m = markup()
        used = set(m.keys) | set(m.attr_keys) | set(script_keys())
        used |= {n for n, _d in glossary() if n in es}
        for text in (field_labels() + [d for _n, d in glossary()] + bootstrap_texts()
                     + server_messages() + fit_labels()):
            hit = lookup(es, text)
            if hit:
                used.add(hit)
        self.assertEqual(sorted(set(es) - used), [])


class TestEveryKeyInTheScriptIsALiteral(unittest.TestCase):
    """A key built at run time cannot be found by the tests above, so the
    translating functions take a literal, or the parameter that passes one
    on."""

    def test_literal_keys(self):
        for fn, src in script_calls():
            # key and s.key are the layer itself passing a literal on.
            self.assertTrue(LITERAL.match(src) or src in ("key", "s.key"), f"{fn}({src}")

    def test_no_sentence_is_written_untranslated(self):
        js = script()
        # A message or a text written with an English literal.
        for pat in (r"\bmsg\('[eiws]',\s*'", r"\.textContent\s*=\s*'[A-Za-z]{2,}[^']*\s"):
            self.assertEqual(re.findall(pat, js), [], pat)
        # Markup written with words in it, outside its tags.
        for lit in re.findall(r"innerHTML\s*\+?=\s*'((?:[^'\\]|\\.)*)'", js):
            # A literal may end inside a tag that the next one closes.
            self.assertNotRegex(re.sub(r"<[^>]*(?:>|$)", "", lit), r"[A-Za-z]{2,} [A-Za-z]{2,}", lit)


SAME_ON_BOTH_SIDES = [
    "2. Radio", "Total", "error", "{n} error", "no", "rural", "campus",
    "Gateways", "Eigner 2021, gateway", "Coding rate", "Validity floor (m)",
    "d\u2080 (m)", "Uplink dwell time",
    'Uplink dwell time<span class="req" aria-hidden="true">*</span>',
]


class TestTheSpanishKeepsWhatTheEnglishCarries(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.es = load_es()

    def test_markup(self):
        # The same tags with the same attributes: a required mark or a
        # <code> lost in translation is a different page.
        tag = r"</?(?:b|code|span)\b[^>]*>"     # "<name>" is a placeholder, not a tag
        for en, es in self.es.items():
            self.assertEqual(sorted(re.findall(tag, en)), sorted(re.findall(tag, es)), en)

    def test_placeholders(self):
        for en, es in self.es.items():
            self.assertEqual(sorted(re.findall(r"\{(\w+)\}", en)),
                             sorted(re.findall(r"\{(\w+)(?:\|t)?\}", es)), en)

    def test_numbers(self):
        # A figure in a sentence is the same figure in Spanish, with a
        # decimal point in both languages.
        for en, es in self.es.items():
            self.assertEqual(sorted(re.findall(r"\d+(?:\.\d+)?", en)),
                             sorted(re.findall(r"\d+(?:\.\d+)?", es)), en)

    def test_house_style(self):
        for en, es in self.es.items():
            text = re.sub(r"<[^>]+>|&\w+;", "", es)
            self.assertNotIn("—", text, en)          # no em dash
            self.assertNotRegex(text, r"\by,", en)
            for m in re.finditer(";", text):
                self.assertTrue(text[m.end():].lstrip().startswith("sin embargo"), en)

    def test_no_entry_is_left_in_english(self):
        # The same text on both sides only where Spanish writes it so: a
        # name, a term the glossary keeps in English, or a word spelled alike.
        same = sorted(en for en, es in self.es.items() if en == es)
        self.assertEqual(same, sorted(SAME_ON_BOTH_SIDES))


class TestThePageCarriesItsLanguage(unittest.TestCase):

    def test_the_server_sends_the_dictionary(self):
        self.assertEqual(server.api_bootstrap({})["translations"]["es"], load_es())

    def test_the_lang_attribute_follows_the_choice(self):
        # WCAG 2.2, 3.1.1: a screen reader reads Spanish as Spanish.
        js = script()
        body = re.search(r"function setLang\(l, opening\)\{(.*?)\n\}", js, re.S).group(1)
        self.assertIn("document.documentElement.lang=l", body)

    def test_the_choice_starts_from_the_browser_and_is_remembered(self):
        js = script()
        body = re.search(r"function initialLang\(\)\{(.*?)\n\}", js, re.S).group(1)
        self.assertIn("localStorage.getItem('loracap.lang')", body)
        self.assertIn("navigator.languages", body)

    def test_the_checks_say_they_are_in_english(self):
        es = load_es()
        html = _read(PAGE)
        self.assertIn('id="checks_lang" hidden data-i18n', html)
        self.assertIn("Los mensajes de las comprobaciones vienen del simulador y se "
                      "muestran en inglés.", " ".join(es.values()))

    def test_the_simulators_messages_are_marked_english(self):
        js = script()
        body = re.search(r"function fieldMsg\(kind, text\)\{(.*?)\n\}", js, re.S).group(1)
        self.assertIn("body.lang='en'", body)


NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node is not installed")
class TestTheLookupInThePage(unittest.TestCase):
    """The page's own lookup functions, extracted and run in Node with the
    Spanish dictionary, so what is tested is what the browser runs."""

    @classmethod
    def setUpClass(cls):
        js = script()

        def fn(name):
            return re.search(r"(function " + name + r"\(.*?\n\})", js, re.S).group(1)
        cls.prelude = "\n".join([
            "let LANG='es', ES=" + json.dumps(load_es()) + ", ES_TEMPLATES=[];",
            "const I18N_MISSES=new Set();",
            fn("fill"), fn("T"), fn("TXr"), fn("TX"), fn("compileTemplates"),
            fn("rejectionHow"), "compileTemplates();"])

    def _run(self, expr):
        code = self.prelude + "\nconsole.log(JSON.stringify(" + expr + "));"
        r = subprocess.run([NODE, "-e", code], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_a_sentence_built_by_the_page(self):
        db = presets.INTER_SF_REJECTION_DB["CROCE2020_SX1272"]
        text = self._run(f"rejectionHow({json.dumps(db)})")
        self.assertTrue(text.startswith("Cómo se aplica:"), text)
        self.assertIn("se pierde cuando un paquete en SF", text)
        self.assertEqual(self._run("[...I18N_MISSES]"), [])

    def test_a_server_sentence_with_a_value_to_translate(self):
        # The environment's name arrives inside the English sentence and is
        # translated in the Spanish one.
        en = ("The range for 'forest' pools only 3 studies, so it describes the "
              "few sites that were measured rather than the environment as a class.")
        self.assertEqual(self._run(f"TXr({json.dumps(en)})"), {
            "text": "El rango de 'bosque' reúne solo 3 estudios, así que describe "
                    "los pocos sitios que se midieron más que el entorno como clase.",
            "hit": True})

    def test_a_range_with_a_citation(self):
        text = server.field_limits()["path_loss_exponent"]["text"]
        out = self._run(f"TX({json.dumps(text)})")
        self.assertTrue(out.startswith("medido de "), out)
        self.assertIn("doi:10.3390/s24123877", out)

    def test_the_simulators_text_passes_unchanged(self):
        en = "n_runs=1 gives a confidence interval of zero width."
        self.assertEqual(self._run(f"TXr({json.dumps(en)})"), {"text": en, "hit": False})

    def test_a_missing_key_falls_back_to_english_and_is_listed(self):
        self.assertEqual(self._run("[T('No such {thing}', {thing:'key'}), [...I18N_MISSES]]"),
                         ["No such key", ["No such {thing}"]])

    def test_english_is_the_key_itself(self):
        self.assertEqual(self._run("(LANG='en', T('{n} errors', {n:3}))"), "3 errors")


class TestTheMarkupIsAllMarked(unittest.TestCase):

    def test_text(self):
        self.assertEqual(markup().unmarked_text, [])

    def test_attributes(self):
        self.assertEqual(markup().unmarked_attrs, [])


if __name__ == "__main__":
    unittest.main()
