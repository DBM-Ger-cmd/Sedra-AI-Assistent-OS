"""Moved to guppi_runtime.core.registry (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.core.registry."""
import sys

from .core import registry as _module

sys.modules[__name__] = _module
