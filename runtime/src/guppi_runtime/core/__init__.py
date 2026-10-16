"""GUPPI's core (package split 2026-10-12, review 2026-10-11 finding 4): missions and their state machine, the brain, the message bus, the Guard,
permission levels, the audit chain, the step journal, the registry and the shared helpers. The core imports nothing outside this package; it must
never import the DevVM, the agent manager or the coder extensions (tests/test_core_boundary_src.py). Nothing is imported here on purpose: every
submodule is loaded on its own, and the old names (guppi_runtime.util, guppi_runtime.guard, ...) are aliases of these modules."""
