"""Bit-for-bit record of what the engine produces under the LoRaSim receiver
rule.

Every number this repository has published comes out of the collision loop in
`core.run_single_sim`. ROADMAP item 13 restructures that loop to make room for
a second receiver rule, and a restructuring is exactly the kind of change that
can alter a result while every statistical test still passes: a reordered
comparison, a tie broken the other way, a loss counted twice. So the output of
the loop as it stood BEFORE the restructuring is stored here, for a set of
configurations chosen to reach every branch of it, and must come back
identical, not merely close.

The cases cover: the capture threshold at 6 dB and at 0 dB, where ties are
broken; the preamble allowance on and off; the demodulator limit binding;
shadowing and fading together; fixed, adaptive and ADR scenarios; disc and
polygon placement.

`golden_engine.json` was first written by the code before item 13 touched
it. It has been regenerated once since, on purpose, by ROADMAP item 16: the
loop counted a packet dropped for want of a demodulator a second time when a
later same-SF packet collided with it. Only the three `demod_binding` runs
changed, collisions falling by about 200 per run and DER rising by about
0.033, and the other eighteen came back identical. The package SHA-256 of the
code that wrote it is recorded in the file. Regenerate it only when an
engine result is meant to change, and record why here:

    python3 -m tests.test_engine_golden --write
"""
import dataclasses
import json
import os
import random
import sys
import unittest

from loracap.core import run_single_sim
from tests.helpers import config

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "golden_engine.json")

GUAMAL_SENSI = {7: -126.5, 8: -129.0, 9: -131.5, 10: -134.0}
SQUARE_1KM = [[(-500.0, -500.0), (500.0, -500.0), (500.0, 500.0),
               (-500.0, 500.0)]]


def _site(**over):
    base = dict(
        sensitivity_dbm=dict(GUAMAL_SENSI), n_channels=8,
        max_simultaneous_demodulations=8, payload_bytes=32,
        avg_send_interval_ms=15000.0, tx_power_dbm=22.0,
        net_antenna_gain_db=9.0, path_loss_exponent=2.159,
        path_loss_ref_db=130.32, path_loss_ref_distance_m=100.0,
        min_valid_distance_m=30.0, placement="polygon",
        placement_polygons_m=SQUARE_1KM)
    base.update(over)
    return config(**base)


def cases():
    """(name, cfg, n_nodes, sim_time_ms, scenario). Names are stable keys."""
    return [
        # The deployed configuration, eight channels, capture at 6 dB.
        ("site_sf8", _site(), 150, 600_000.0, "SF8"),
        # Two demodulators for eight channels, so the limit binds.
        ("demod_binding", _site(max_simultaneous_demodulations=2),
         150, 600_000.0, "SF8"),
        # One channel, threshold 0 dB: every overlap is resolved by power and
        # ties go one particular way.
        ("single_channel_capture0", _site(n_channels=1,
                                          capture_threshold_db=0.0),
         80, 600_000.0, "SF7"),
        # No preamble allowance, so every overlap is evaluated.
        ("no_preamble", _site(n_channels=1, preamble_capture=False),
         60, 600_000.0, "SF8"),
        # Adaptive assignment with both random terms on.
        ("multi_shadow_fading", _site(shadowing_sigma_db=7.41,
                                      fading_sigma_db=3.0),
         150, 600_000.0, "MULTI"),
        # ADR with the plan's power ladder and shadowing.
        ("adr_shadow", _site(shadowing_sigma_db=4.0,
                             tx_power_offsets_db=tuple(range(0, -21, -2))),
         150, 600_000.0, "ADR"),
        # Disc placement on the Bor configuration, SF12, one channel.
        ("disc_sf12", config(n_channels=1, avg_send_interval_ms=100_000.0,
                             placement="disc"),
         60, 2_000_000.0, "SF12"),
    ]


SEEDS = (1, 99, 2024)


def _key(name, seed):
    return f"{name}@{seed}"


def compute():
    """Every case at every seed, as JSON would store it. Passing the result
    through JSON is what makes the comparison exact: dict keys become strings
    and floats round-trip through their shortest repr, both deterministic."""
    out = {}
    for name, cfg, n, t, scen in cases():
        for seed in SEEDS:
            r = run_single_sim(cfg, n, t, scen, random.Random(seed))
            out[_key(name, seed)] = json.loads(json.dumps(r))
    return out


class TestEngineIsUnchanged(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(GOLDEN) as f:
            cls.golden = json.load(f)["results"]
        cls.now = compute()

    def test_every_case_is_recorded(self):
        self.assertEqual(sorted(self.now), sorted(self.golden))

    def test_output_is_identical(self):
        for key in sorted(self.golden):
            with self.subTest(case=key):
                self.assertEqual(self.now[key], self.golden[key])

    def test_the_cases_actually_reach_the_branches(self):
        """A golden file that never exercised a branch would protect nothing
        there. Each property below must hold in at least one recorded run."""
        runs = list(self.golden.values())
        self.assertTrue(any(r["collided"] > 0 for r in runs))
        self.assertTrue(any(r["lost_capacity"] > 0 for r in runs),
                        "no case makes the demodulator limit bind")
        self.assertTrue(any(r["lost_signal"] > 0 for r in runs),
                        "no case loses a packet to weak signal")
        self.assertTrue(any(r["unreachable_nodes"] > 0 for r in runs),
                        "no case excludes a node")


def _write():
    from loracap.reproduce import code_digest
    payload = {"code_sha256": code_digest(), "results": compute()}
    with open(GOLDEN, "w") as f:
        json.dump(payload, f, indent=1, sort_keys=True)
    print(f"wrote {GOLDEN}: {len(payload['results'])} runs")


if __name__ == "__main__":
    if "--write" in sys.argv:
        _write()
    else:
        unittest.main()
