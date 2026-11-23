"""The LoRaWAN header on air (design item 33).

The payload length PL in the airtime formula is everything the radio sends
after the LoRa header. In a LoRaWAN uplink that is the application payload
plus 13 bytes of LoRaWAN: MHDR, FHDR without options, FPort and MIC. Up to
version 2.1.0 LoRaCAP passed the application payload straight to the formula,
so every LoRaWAN uplink was timed 13 bytes short. The payload ceiling, on the
other hand, was checked against the same number read correctly as the
application payload. The two readings disagreed, and the airtime one was
wrong: a 14-byte CowNet reading at SF9 took 164.864 ms instead of 226.304 ms.

The tests pin the airtime to values worked by hand from the Semtech formula,
check that the ceiling still reads the application payload, that the two Bor
studies keep the bare 20-byte frame their published airtime needs, that a bad
value is refused with a message naming the field, and that the field reaches
a study.py written by the web page and comes back.
"""
import dataclasses
import re
import unittest

from tests import helpers
from tests.test_webui import PAGE, TempRoot

from loracap import study as study_mod
from loracap.core import airtime_ms

# Worked by hand: T = (8 + 4.25 + n_payload) * 2^SF / BW, with
# n_payload = 8 + ceil((8 PL - 4 SF + 28 + 16) / (4 (SF - 2 DE))) * (CR + 4),
# explicit header, CRC on, CR 4/5, DE only at SF11 and SF12 at 125 kHz.
#   SF9, PL 27: ceil(224 / 36) = 7, n = 43, 55.25 * 4.096 ms = 226.304 ms
#   SF9, PL 14: ceil(120 / 36) = 4, n = 28, 40.25 * 4.096 ms = 164.864 ms
#   SF8, PL 45: ceil(372 / 32) = 12, n = 68, 80.25 * 2.048 ms = 164.352 ms
#   SF8, PL 32: ceil(268 / 32) = 9,  n = 53, 65.25 * 2.048 ms = 133.632 ms
#   SF12, PL 20, CR 4/8: ceil(156 / 40) = 4, n = 40, 52.25 * 32.768 ms = 1712.128 ms
COWNET_SF9_WITH_HEADER_MS = 226.304
COWNET_SF9_WITHOUT_HEADER_MS = 164.864
IOT4COWS_SF8_WITH_HEADER_MS = 164.352
IOT4COWS_SF8_PUBLISHED_MS = 133.632       # Table 3 of the article: 133.63 ms
BOR_SN1_PUBLISHED_MS = 1712.13


class TestTheFrameOnAir(unittest.TestCase):

    def test_the_default_is_the_lorawan_minimum(self):
        default = {f.name: f.default for f in dataclasses.fields(study_mod.Study)}
        self.assertEqual(default["lorawan_overhead_bytes"], 13)
        self.assertEqual(helpers.study(payload_bytes=32).frame_bytes(), 45)

    def test_the_airtime_counts_the_header(self):
        cfg = helpers.study(payload_bytes=14, scenarios=("SF9",)).to_sim_config()
        self.assertEqual(cfg.payload_bytes, 27)
        self.assertAlmostEqual(airtime_ms(cfg, 9), COWNET_SF9_WITH_HEADER_MS, places=3)

    def test_zero_times_the_payload_alone(self):
        s = helpers.study(payload_bytes=14, lorawan_overhead_bytes=0, scenarios=("SF9",))
        self.assertEqual(s.frame_bytes(), 14)
        self.assertAlmostEqual(airtime_ms(s.to_sim_config(), 9),
                               COWNET_SF9_WITHOUT_HEADER_MS, places=3)

    def test_the_iot4cows_collar_sends_45_bytes(self):
        s = study_mod.load_study("iot4cows")
        self.assertEqual((s.payload_bytes, s.lorawan_overhead_bytes, s.frame_bytes()),
                         (32, 13, 45))
        self.assertAlmostEqual(airtime_ms(s.to_sim_config(), 8),
                               IOT4COWS_SF8_WITH_HEADER_MS, places=3)
        # The published article timed the 32 bytes alone.
        bare = dataclasses.replace(s, lorawan_overhead_bytes=0)
        self.assertAlmostEqual(airtime_ms(bare.to_sim_config(), 8),
                               IOT4COWS_SF8_PUBLISHED_MS, places=3)

    def test_bor_keeps_the_bare_frame_its_airtime_needs(self):
        for name in ("bor2016_sn1", "bor2016_sn3"):
            s = study_mod.load_study(name)
            self.assertEqual(s.lorawan_overhead_bytes, 0, name)
            self.assertEqual(s.frame_bytes(), 20, name)
        sn1 = study_mod.load_study("bor2016_sn1")
        self.assertAlmostEqual(airtime_ms(sn1.to_sim_config(), 12),
                               BOR_SN1_PUBLISHED_MS, places=2)


class TestTheCeilingReadsTheApplicationPayload(unittest.TestCase):
    """RP002-1.0.5 Table 24 gives N, the application payload, for each US915
    data rate: 53 bytes at DR1 (SF9) and 11 at DR0 (SF10). The frame on air is
    13 bytes longer and must not be the number compared."""

    def payload_errors(self, sf, payload):
        s = helpers.study(payload_bytes=payload, scenarios=(f"SF{sf}",))
        errors, _, _ = study_mod.validate(s)
        return [e for e in errors if e.startswith("payload_bytes")]

    def test_the_largest_legal_payload_passes_with_its_header(self):
        self.assertEqual(self.payload_errors(9, 53), [])
        self.assertEqual(self.payload_errors(10, 11), [])

    def test_one_byte_more_is_refused(self):
        self.assertEqual(len(self.payload_errors(9, 54)), 1)
        self.assertEqual(len(self.payload_errors(10, 12)), 1)


class TestABadValueIsRefused(unittest.TestCase):

    def test_each_bad_value(self):
        for bad in (-1, 1.5, True, "13", None):
            s = helpers.study(lorawan_overhead_bytes=bad)
            with self.assertRaisesRegex(ValueError, "lorawan_overhead_bytes", msg=repr(bad)):
                s.to_sim_config()
            errors, _, info = study_mod.validate(s)
            self.assertTrue(any("lorawan_overhead_bytes must be a whole number"
                                in e for e in errors), (bad, errors))
            self.assertFalse(any(i.startswith("Frame on air") for i in info), bad)

    def test_zero_and_up_are_accepted(self):
        for good in (0, 13, 28):
            errors, _, _ = study_mod.validate(helpers.study(lorawan_overhead_bytes=good))
            self.assertFalse(any("lorawan_overhead_bytes" in e for e in errors), good)


class TestTheChecksStateTheFrame(unittest.TestCase):

    def info(self, **over):
        return [i for i in study_mod.validate(helpers.study(**over))[2]
                if i.startswith("Frame on air")]

    def test_with_the_header(self):
        self.assertEqual(self.info(payload_bytes=14), [
            "Frame on air: 14 B of payload + 13 B of LoRaWAN header = 27 B, "
            "the length the airtime is computed for"])

    def test_a_bare_frame(self):
        self.assertEqual(self.info(payload_bytes=20, lorawan_overhead_bytes=0), [
            "Frame on air: 20 B, the payload alone "
            "(lorawan_overhead_bytes = 0, a bare LoRa frame)"])


class TestTheWebPage(TempRoot):

    def test_the_field_reaches_study_py_and_comes_back(self):
        for value in (0, 13):
            out = self.create(name=f"hdr{value}", lorawan_overhead_bytes=value)
            self.assertEqual(out["errors"], [])
            self.assertIn(f"    lorawan_overhead_bytes={value},", out["study_py"])
            self.assertEqual(study_mod.load_study(f"hdr{value}").lorawan_overhead_bytes,
                             value)

    def test_written_right_after_the_payload(self):
        order = [f for f, _ in study_mod.STUDY_FIELD_ORDER]
        self.assertEqual(order[order.index("payload_bytes") + 1], "lorawan_overhead_bytes")

    def test_the_page_offers_the_studys_default_and_sends_it(self):
        with open(PAGE, encoding="utf-8") as f:
            html = f.read()
        default = {f.name: f.default for f in dataclasses.fields(study_mod.Study)}
        d = default["lorawan_overhead_bytes"]
        field = re.search(r'<input id="f_hdr"[^>]*value="(\d+)"', html)
        self.assertIsNotNone(field)
        self.assertEqual(int(field.group(1)), d)
        # in the advanced experiment block, so a changed value is listed on its bar
        block = html[html.index('id="adv_exp"'):html.index('id="adv_rx"')]
        self.assertIn('id="f_hdr"', block)
        self.assertIn("lorawan_overhead_bytes:Math.round(num('f_hdr',%d))" % d, html)
        self.assertIn("lorawan_overhead_bytes:['f_hdr',", html)


if __name__ == "__main__":
    unittest.main()
