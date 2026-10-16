"""Moved to guppi_runtime.selfdev.candidate_acceptance (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.selfdev.candidate_acceptance."""
import sys

from .selfdev import candidate_acceptance as _module

sys.modules[__name__] = _module
