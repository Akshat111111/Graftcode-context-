"""
Graftcode Context Library
~~~~~~~~~~~~~~~~~~~~~~~~~

Provides RequestContext and GraftConfig for seamless header propagation
across Python services — no custom middleware required.
"""

from .context import RequestContext, GraftConfig

__all__ = ["RequestContext", "GraftConfig"]
__version__ = "1.0.0"
