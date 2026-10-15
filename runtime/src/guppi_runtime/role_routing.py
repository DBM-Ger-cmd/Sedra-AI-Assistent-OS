"""Moved to guppi_runtime.models.role_routing (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.models.role_routing."""
import sys

from .models import role_routing as _module

sys.modules[__name__] = _module
