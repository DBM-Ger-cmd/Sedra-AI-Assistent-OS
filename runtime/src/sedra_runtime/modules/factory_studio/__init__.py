"""Factory Studio Module — Operative Factory-UI innerhalb One Sedra.

Dieses Modul stellt die Backend-API für das Factory Studio bereit:
- ProjectBrowser: Factory-Projekte verwalten
- GraphView: Modul-Dependencies & Build-Order visualisieren
- ExecutionView: Benchmarks, Runs, Logs
- StatusDashboard: Factory Health, Gates, Captain-Entscheidungen
- GatePanel: Approve/Reject direkt in UI

Architektur: 5-Layer (Domain, Application, Infrastructure, AI, App)
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = [
    "domain",
    "application",
    "infrastructure",
    "ai",
    "app",
]