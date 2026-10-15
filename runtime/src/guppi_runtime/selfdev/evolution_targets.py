"""Single source of truth for evolution classification (E1/E2/E3).

Kept in code on purpose: these sets protect the core, so they must not be changeable by editing a
config file. Before v1.21 `evolution.py` and `self_development.py` each kept their own, slightly
different copy, so one target could be E2 on one path and E3 on the other. The sets below are the
union of both old copies.
"""
from __future__ import annotations

CORE_TARGETS = frozenset({
    "brain", "mission_state", "message_bus", "guard", "registry", "lifecycle", "updater", "core_contract",
    "policy", "soul_enforcement", "evolution_manager", "control_core",
})
MODULE_TARGETS = frozenset({
    "new_module", "module", "module_logic", "module_interface", "privileged_tool_adapter",
    "worker", "adapter", "connector", "verification_module", "context_module", "tool_adapter",
})


# Positive list: only these are known to be low-risk. `skill` is the default target everywhere in the
# runtime. A new low-risk type must be added here on purpose.
E1_TARGETS = frozenset({"skill", "topic", "documentation"})


def classify_target(target_type) -> str:
    """E3 for core, E2 for modules and adapters, E1 only for the known low-risk list.

    A missing target (None or empty) means the default `skill` (E1), as everywhere else in the runtime.
    Any other name that is not on a list - a typo, a new kind of target, a non-string - is E2, so a
    Captain gate applies. Core wins if a name is in both sets.
    """
    if target_type is None or (isinstance(target_type, str) and not target_type.strip()):
        return "E1"
    if not isinstance(target_type, str):
        return "E2"
    target_type = target_type.strip().lower()
    if target_type in CORE_TARGETS:
        return "E3"
    if target_type in E1_TARGETS:
        return "E1"
    return "E2"
