"""Moved to guppi_runtime.selfdev.project_inspection (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.selfdev.project_inspection."""
import sys

from .selfdev import project_inspection as _module

sys.modules[__name__] = _module
