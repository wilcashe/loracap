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

__version__ = "1.0.0"

from .core import SimConfig, run_batch, run_single_sim          # noqa: F401
from .study import Study, load_study, list_studies, validate    # noqa: F401
from .study import node_counts_logspace                         # noqa: F401
