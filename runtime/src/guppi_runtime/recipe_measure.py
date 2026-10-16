"""Moved to guppi_runtime.models.recipe_measure (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.models.recipe_measure."""
import sys

from .models import recipe_measure as _module

sys.modules[__name__] = _module
