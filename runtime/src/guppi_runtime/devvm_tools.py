"""Moved to guppi_runtime.devenv.devvm_tools (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.devenv.devvm_tools."""
import sys

from .devenv import devvm_tools as _module

sys.modules[__name__] = _module
