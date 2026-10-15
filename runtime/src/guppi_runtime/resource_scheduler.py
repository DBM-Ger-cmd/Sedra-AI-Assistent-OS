"""Moved to guppi_runtime.jobs.resource_scheduler (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.jobs.resource_scheduler."""
import sys

from .jobs import resource_scheduler as _module

sys.modules[__name__] = _module
