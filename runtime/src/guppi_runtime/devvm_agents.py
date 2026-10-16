"""Moved to guppi_runtime.devenv.devvm_agents (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.devenv.devvm_agents."""
import sys

from .devenv import devvm_agents as _module

sys.modules[__name__] = _module
