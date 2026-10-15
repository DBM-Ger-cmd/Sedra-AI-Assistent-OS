"""Moved to guppi_runtime.models.gpu_preflight (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.models.gpu_preflight."""
import sys

from .models import gpu_preflight as _module

sys.modules[__name__] = _module
