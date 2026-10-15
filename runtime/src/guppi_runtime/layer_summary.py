"""Moved to guppi_runtime.devenv.layer_summary (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.devenv.layer_summary."""
import sys

from .devenv import layer_summary as _module

sys.modules[__name__] = _module
