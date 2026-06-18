"""
sim/logging_config.py
Structured logging setup for TakeoverBench.

Importing this module once configures Python's logging module with
a consistent format (timestamp, module name, level, message).
Every other module then does::

    import logging
    logger = logging.getLogger(__name__)

and uses logger.info(), logger.warning(), logger.error() etc.
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
