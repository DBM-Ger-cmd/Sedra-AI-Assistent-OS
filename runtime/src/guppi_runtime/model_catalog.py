"""Moved to guppi_runtime.models.model_catalog (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.models.model_catalog."""
import sys

from .models import model_catalog as _module

sys.modules[__name__] = _module
