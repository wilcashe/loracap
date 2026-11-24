"""Gateway coordinates in degrees, minutes and seconds (design item 36).

The CowNet gateway's position came as 5°30′04,10″ N, 73°29′34,58″ W, the way
a GPS or a survey sheet gives it, and the page took decimal degrees only, so
it had to be converted by hand. A slip in that conversion moves the whole
site. The page now reads either form, shows the decimal degrees it read a
written-out coordinate as, and sends only the decimal value onward.

The parser runs in Node with the page's own code, when Node is installed.
"""
import json
import math
import re
import shutil
import subprocess
import unittest

from tests import helpers

from tests.test_webui import PAGE

from webui import server

NODE = shutil.which("node")


def _page():
    with open(PAGE, encoding="utf-8") as f:
        return f.read()


def dms(d, m, s):
    return d + m / 60 + s / 3600


@unittest.skipUnless(NODE, "Node is not installed")
class TestTheParser(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        html = _page()
        cls.fn = re.search(r"(function parseCoord\(.*?\n\})", html, re.S).group(1)

    def parse(self, cases):
        """cases: list of (text, axis). Returns the parsed values, None for NaN."""
        body = "console.log(JSON.stringify(%s.map(([t,a])=>{const v=parseCoord(t,a);"\
               "return isNaN(v)?null:v;})));" % json.dumps(cases)
        r = helpers.run_node(self.fn + "\n" + body)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_decimal_degrees_unchanged(self):
        self.assertEqual(self.parse([["5.501139", "lat"], ["-73.492939", "lon"],
                                     ["  42.0347 ", "lat"], ["181", "lon"], ["+5.501139", "lat"]]),
                         [5.501139, -73.492939, 42.0347, 181, 5.501139])

    def test_the_cownet_gateway_as_written(self):
        lat, lon = dms(5, 30, 4.10), -dms(73, 29, 34.58)
        got = self.parse([["5°30′04,10″ N", "lat"], ["73°29′34,58″ W", "lon"],
                          ["5°30'04.10\"N", "lat"], ["5º30’04.10” N", "lat"],
                          ["5 30 4.10 N", "lat"], ["N 5°30′04.10″", "lat"],
                          ["73°29′34.58″ O", "lon"], ["-73 29 34.58", "lon"]])
        for v, want in zip(got, [lat, lon, lat, lat, lat, lat, lon, lon]):
            self.assertIsNotNone(v)
            self.assertTrue(math.isclose(v, want, abs_tol=1e-9), (v, want))

    def test_south_and_degrees_with_minutes_only(self):
        got = self.parse([["33°52′ S", "lat"], ["151°12.5′ E", "lon"]])
        self.assertTrue(math.isclose(got[0], -dms(33, 52, 0)))
        self.assertTrue(math.isclose(got[1], dms(151, 12.5, 0)))

    def test_what_is_not_a_coordinate(self):
        bad = [["", "lat"], ["abc", "lat"], ["5°65′00″ N", "lat"], ["5°30′60″ N", "lat"],
               ["73°29′34″ W", "lat"], ["5°30′ N", "lon"], ["-5°30′ S", "lat"],
               ["5.5 30", "lat"], ["5 30.5 10", "lat"], ["5 30 4 10", "lat"],
               ["5°30′04″ N N", "lat"], ["1e3", "lon"], ["+5°30′ S", "lat"],
               ["+-5", "lat"]]
        self.assertEqual(self.parse(bad), [None] * len(bad))


@unittest.skipUnless(NODE, "Node is not installed")
class TestWritingTheStudy(unittest.TestCase):
    """site_polygon.py records the gateway the boundary was projected around.
    A coordinate that stops reading as one after the KML is loaded used to
    reach the server as null, after it had already made the study's folder."""

    def write(self, lat, place="polygon", rings=True):
        html = _page()
        fns = [re.search(r"((?:async )?function " + f + r"\(.*?\n\})", html, re.S).group(1)
               for f in ("parseCoord", "coord", "createStudy")]
        js = "\n".join([
            "const els={f_name:{value:'s'}, f_lat:{value:%s}, f_lon:{value:'-73.492939'},"
            " f_place:{value:%s}, f_over:{checked:false}, btn_run:{}, createwhy:{},"
            " createout:{innerHTML:'', kids:[], appendChild(x){this.kids.push(x);}}};"
            % (json.dumps(lat), json.dumps(place)),
            "const $=id=>els[id], msgT=(k,t)=>({k,t}), msgX=(k,t)=>({k,t}), msgEn=msgX;",
            "let RINGS=%s, RING_NAMES=['a'], CREATED=null; const sent=[];"
            % ("[[[0,0],[10,0],[10,10]]]" if rings else "null"),
            "async function post(p,b){ sent.push(b.lat); throw new Error('stop'); }",
            "function values(){ return {}; }",
            *fns,
            "createStudy().then(()=>console.log(JSON.stringify("
            "{sent, said: els.createout.kids.map(m=>m.t)})));"])
        r = helpers.run_node(js)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_a_slip_stops_before_the_server(self):
        self.assertEqual(self.write("5°65′ N"),
                         {"sent": [], "said": ["Enter the gateway position first."]})

    def test_a_coordinate_goes_as_decimal_degrees(self):
        got = self.write("5°30′04.10″ N")
        self.assertTrue(math.isclose(got["sent"][0], dms(5, 30, 4.10)), got)

    def test_without_a_boundary_the_position_is_not_needed(self):
        # Neither placement on a disc nor a study without a KML writes the
        # gateway into site_polygon.py, so neither is stopped here.
        self.assertEqual(self.write("abc", place="disc")["sent"], [None])
        self.assertEqual(self.write("abc", rings=False)["sent"], [None])


class TestThePage(unittest.TestCase):

    def setUp(self):
        self.html = _page()

    def test_the_fields_take_text(self):
        for fid in ("f_lat", "f_lon"):
            tag = re.search(r'<input id="%s"[^>]*>' % fid, self.html).group(0)
            self.assertIn('type="text"', tag)

    def test_every_reader_uses_the_parsed_value(self):
        self.assertNotRegex(self.html, r"num\('f_lat'|num\('f_lon'|\$\('f_lat'\)\.value===")
        for reader in ("/api/kml',{kml:KMLTEXT,lat:coord('f_lat'),lon:coord('f_lon')}",
                       "return {csv, lat:coord('f_lat'), lon:coord('f_lon'),",
                       "ring_names:RING_NAMES,lat:coord('f_lat'),lon:coord('f_lon'),"):
            self.assertIn(reader, self.html)
        self.assertIn("const v = isCoord ? coord(id) : parseFloat(el.value);", self.html)

    def test_the_range_says_both_forms(self):
        lim = server.field_limits()
        self.assertIn("degrees, minutes and seconds with N or S", lim["lat"]["text"])
        self.assertIn("degrees, minutes and seconds with E or W", lim["lon"]["text"])


if __name__ == "__main__":
    unittest.main()
