"""The boundary follows the gateway (design item 41).

The page projects the KML into metres around the gateway once, when the file
is loaded. A position typed or corrected afterwards left the rings around the
old one, and site_polygon.py then recorded the new position beside rings
measured from the old: a file that contradicts itself, in the same way a
mistyped coordinate once gave an exponent of 36. Loading the file before the
position was refused, and the file had to be chosen again.

The page now keeps the KML text and projects it again whenever the position
changes, and holds no rings at all while the position does not read as one.
The page's own functions run in Node with a stand-in for the server.
"""
import json
import re
import shutil
import subprocess
import unittest

from tests import helpers

from tests.test_webui import PAGE

NODE = shutil.which("node")

KML = "<kml>boundary</kml>"


def _page():
    with open(PAGE, encoding="utf-8") as f:
        return f.read()


@unittest.skipUnless(NODE, "Node is not installed")
class TestTheBoundaryFollowsTheGateway(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        html = _page()

        def fn(name):
            return re.search(r"((?:async )?function " + name + r"\(.*?\n\})", html,
                             re.S).group(1)
        handler = re.search(r"(let KMLTEXT=null, KMLSEQ=0;.*?\n\};)", html, re.S).group(1)
        # The server stand-in places one ring point at the gateway's latitude,
        # so the rings say which position they were projected around. Each
        # answer waits until the test releases it, to test the order.
        cls.prelude = "\n".join([
            "const els={}, listeners={};",
            "const $=id=>(els[id]=els[id]||{value:'', kids:[], set innerHTML(v){this.kids=[];},",
            "  appendChild(x){this.kids.push(x);}, addEventListener(ev,f){listeners[id+':'+ev]=f;}});",
            "let RINGS=null, RING_NAMES=null, TOUCHED=false; const TOUCHED_IDS=new Set();",
            "const msgT=(k,t)=>({t}), msgX=msgT, tplain=()=>{}, showKml=()=>{};",
            "let validations=0; function schedule(){ validations++; }",
            "const sent=[], pending=[];",
            "function post(path, body){ sent.push([path, body.kml, body.lat, body.lon]);",
            "  return new Promise(res=>pending.push(()=>res({rings:[[[0, body.lat]]],",
            "    names:['PASTOREO'], max_radius_m:401})));}",
            "async function release(i){ pending[i](); await new Promise(r=>setTimeout(r,0)); }",
            fn("parseCoord"), fn("coord"),
            handler, fn("projectKml"),
            "['f_lat','f_lon'].forEach(id=>$(id).addEventListener('change', projectKml));",
            "const file={files:[{name:'PASTOREO.kml', text:async()=>%s}]};" % json.dumps(KML),
            "const said=()=>els.kmlout.kids.map(m=>m.t);",
        ])

    def run_js(self, body):
        code = self.prelude + "\n(async()=>{\n" + body + "\n})();"
        r = helpers.run_node(code)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_a_corrected_position_projects_again(self):
        out = self.run_js("""
          $('f_lat').value='5.6'; $('f_lon').value='-73.492939';
          const load=$('kmlfile').onchange({target:file}); await new Promise(r=>setTimeout(r,0));
          await release(0); await load;
          const first=JSON.stringify(RINGS);
          $('f_lat').value='5°30′04.10″ N';
          const again=listeners['f_lat:change'](); await release(1); await again;
          console.log(JSON.stringify({first, rings:RINGS, sent}));""")
        self.assertEqual(out["first"], json.dumps([[[0, 5.6]]], separators=(",", ":")))
        self.assertAlmostEqual(out["rings"][0][0][1], 5.501139, places=6)
        self.assertEqual([s[1] for s in out["sent"]], [KML, KML])
        self.assertEqual(len(out["sent"]), 2)

    def test_the_file_can_come_before_the_position(self):
        out = self.run_js("""
          await $('kmlfile').onchange({target:file});
          const before={rings:RINGS, said:said(), sent:sent.length};
          $('f_lat').value='5.501139'; $('f_lon').value='-73.492939';
          const p=listeners['f_lon:change'](); await release(0); await p;
          console.log(JSON.stringify({before, rings:RINGS, said:said()}));""")
        self.assertIsNone(out["before"]["rings"])
        self.assertEqual(out["before"]["sent"], 0)
        self.assertTrue(out["before"]["said"][0].startswith("Enter the gateway latitude"))
        self.assertEqual(out["rings"], [[[0, 5.501139]]])
        self.assertEqual(out["said"], [])

    def test_no_rings_while_the_position_does_not_read(self):
        out = self.run_js("""
          $('f_lat').value='5.501139'; $('f_lon').value='-73.492939';
          const load=$('kmlfile').onchange({target:file}); await new Promise(r=>setTimeout(r,0));
          await release(0); await load;
          const n=validations;
          $('f_lat').value='5°65′ N'; await listeners['f_lat:change']();
          console.log(JSON.stringify({rings:RINGS, names:RING_NAMES, said:said(),
                                      revalidated:validations>n, sent:sent.length}));""")
        self.assertIsNone(out["rings"])
        self.assertIsNone(out["names"])
        self.assertTrue(out["said"][0].startswith("Enter the gateway latitude"))
        self.assertTrue(out["revalidated"])
        self.assertEqual(out["sent"], 1)

    def test_a_late_answer_does_not_undo_a_later_one(self):
        out = self.run_js("""
          $('f_lat').value='5.1'; $('f_lon').value='-73.0';
          const a=$('kmlfile').onchange({target:file}); await new Promise(r=>setTimeout(r,0));
          $('f_lat').value='5.2'; const b=listeners['f_lat:change']();
          await release(1); await b;
          await release(0); await a;
          console.log(JSON.stringify(RINGS));""")
        self.assertEqual(out, [[[0, 5.2]]])

    def test_nothing_to_project_before_a_file(self):
        out = self.run_js("""
          $('f_lat').value='5.2'; $('f_lon').value='-73.0';
          await listeners['f_lat:change']();
          console.log(JSON.stringify({sent:sent.length, rings:RINGS}));""")
        self.assertEqual(out, {"sent": 0, "rings": None})


class TestTheWiring(unittest.TestCase):

    def test_both_coordinates_project_on_change(self):
        self.assertIn("['f_lat','f_lon'].forEach(id=>$(id).addEventListener('change', "
                      "projectKml));", _page())


if __name__ == "__main__":
    unittest.main()
