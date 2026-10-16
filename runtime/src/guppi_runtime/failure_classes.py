"""Moved to guppi_runtime.jobs.failure_classes (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.jobs.failure_classes."""
import sys

from .jobs import failure_classes as _module

sys.modules[__name__] = _module
