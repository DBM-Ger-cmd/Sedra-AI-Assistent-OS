"""Moved to guppi_runtime.devenv.conn_check (package split 2026-10-12). This old name stays an alias of the SAME module object, so imports, monkeypatching
and mock.patch targets keep working. New code imports guppi_runtime.devenv.conn_check."""
import sys

from .devenv import conn_check as _module

sys.modules[__name__] = _module
