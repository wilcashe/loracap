"""Every lost packet is lost exactly once (design item 16).

A packet dropped for want of a demodulator is a capacity loss. Its RF energy
is still on the air, so it can still be hit by a later packet, but it was
already lost and must not be lost again as a collision. Until item 16 the
same-SF path of the collision loop counted it twice, which lowered DER
wherever the demodulator limit binds.

The regression case is three packets small enough to reason about by hand.
The invariant is checked on heavy synthetic traffic, under both receiver
rules and with rejection between spreading factors on, because the bug lived
in code all of them share.
"""
import copy
import random
import unittest

from tests import helpers  # noqa: F401  (puts the package on sys.path)
from tests.helpers import config

from loracap import presets
from loracap.core import _Packet, airtime_ms, resolve_collisions


def pkt(nid, sf, start, rssi, cfg, channel=0):
    return _Packet(nid, sf, channel, rssi, start, airtime_ms(cfg, sf))


class TestTheRegressionCase(unittest.TestCase):
    """One demodulator. P1 holds it, so P2 and P3 are both dropped for
    capacity. P2 and P3 share SF9 and power, so they also collide. Two
    packets are lost and P1 is received: two losses, not three."""

    def run_case(self, **over):
        cfg = config(max_simultaneous_demodulations=1, **over)
        packets = [pkt(1, 7, 0.0, -100.0, cfg),
                   pkt(2, 9, 1.0, -110.0, cfg),
                   pkt(3, 9, 2.0, -110.0, cfg)]
        return resolve_collisions(cfg, packets)

    def test_lorasim_rule(self):
        out = self.run_case()
        self.assertEqual(out["lost_capacity"], 2)
        self.assertEqual(out["collided_ids"], set())

    def test_lock_rule(self):
        out = self.run_case(receiver_model="lock")
        self.assertEqual(out["lost_capacity"], 2)
        self.assertEqual(out["collided_ids"], set())


def heavy_traffic(cfg, rng, n=6000, horizon_ms=600_000.0):
    """Poisson arrivals on two spreading factors and four channels, dense
    enough that two demodulators are nearly always busy."""
    packets = []
    for i in range(n):
        sf = 7 if rng.random() < 0.6 else 9
        packets.append(_Packet(i, sf, rng.randrange(4),
                               rng.uniform(-125.0, -95.0),
                               rng.uniform(0.0, horizon_ms),
                               airtime_ms(cfg, sf)))
    packets.sort(key=lambda p: p.start)
    return packets


class TestEveryLossIsCountedOnce(unittest.TestCase):

    CONFIGS = {
        "lorasim": {},
        "lock": {"receiver_model": "lock"},
        "lorasim, inter-SF": {
            "inter_sf_rejection_db": presets.inter_sf_rejection("CROCE2020_SX1272")},
        "lock, inter-SF": {
            "receiver_model": "lock",
            "inter_sf_rejection_db": presets.inter_sf_rejection("CROCE2020_SX1272")},
    }

    def test_capacity_losses_and_collisions_are_disjoint(self):
        for label, over in self.CONFIGS.items():
            with self.subTest(config=label):
                cfg = config(n_channels=4, max_simultaneous_demodulations=2,
                             **over)
                packets = heavy_traffic(cfg, random.Random(17))
                judged = copy.deepcopy(packets)
                out = resolve_collisions(cfg, judged)
                dropped = {(p.nodeid, p.start) for p in judged if p.capacity_dropped}
                # The limit must actually bind, or the test proves nothing.
                self.assertGreater(len(dropped), 500)
                self.assertEqual(out["lost_capacity"], len(dropped))
                self.assertEqual(out["collided_ids"] & dropped, set())
                # Every packet the loop marked as collided and that still had
                # a demodulator is a collision loss, and nothing else is.
                marked = {(p.nodeid, p.start) for p in judged
                          if p.collided and not p.capacity_dropped}
                self.assertEqual(out["collided_ids"], marked)


if __name__ == "__main__":
    unittest.main()
