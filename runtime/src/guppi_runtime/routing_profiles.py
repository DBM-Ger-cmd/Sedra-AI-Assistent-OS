"""Moved to guppi_runtime.models.routing_profiles (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.models.routing_profiles."""
import sys

from .models import routing_profiles as _module

sys.modules[__name__] = _module
