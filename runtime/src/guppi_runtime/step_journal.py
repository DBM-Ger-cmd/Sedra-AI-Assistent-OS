"""Moved to guppi_runtime.core.step_journal (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.core.step_journal."""
import sys

from .core import step_journal as _module

sys.modules[__name__] = _module
