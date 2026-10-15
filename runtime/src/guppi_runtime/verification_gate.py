"""Moved to guppi_runtime.jobs.verification_gate (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.jobs.verification_gate."""
import sys

from .jobs import verification_gate as _module

sys.modules[__name__] = _module
