"""Moved to guppi_runtime.jobs.job_worker (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.jobs.job_worker."""
import sys

from .jobs import job_worker as _module

sys.modules[__name__] = _module
