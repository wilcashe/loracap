"""
LoRaCAP
=======

A field-calibrated LoRaWAN uplink capacity simulator.

The engine (`core`) knows nothing about any particular deployment. A `Study`
declares one site and one radio configuration, and the rest of the package
runs it, analyses it and plots it.

Typical use is through the command line, `python3 run.py ...`, rather than by
importing this package directly.
"""

import os as _os


def _read_version() -> str:
    """The version lives in loracap/VERSION, a text file, not here (design
    item 46). The code digest that every saved result records reads only the
    package's .py files, so raising the version no longer changes the digest
    and no longer forces every experiment to be run again. Commit 925adaa
    reported 2.2.0 for code that was not 2.2.0's for that reason."""
    path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "VERSION")
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


__version__ = _read_version()

from .core import SimConfig, run_batch, run_single_sim          # noqa: F401
from .study import Study, load_study, list_studies, validate    # noqa: F401
from .study import node_counts_logspace                         # noqa: F401
