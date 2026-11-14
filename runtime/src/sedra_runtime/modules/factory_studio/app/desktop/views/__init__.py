"""Views Package — Factory Studio WinUI 3 Views (XAML + Code-Behind).

Struktur:
- ProjectBrowserView: Baumansicht Projekte/Module
- GraphView: Dependency-Graph (GraphX)
- ExecutionView: Benchmark Runs, Logs, Charts
- StatusDashboardView: Factory Health, Gates
- GatePanelView: Captain-Gate Approve/Reject
"""

from __future__ import annotations

__all__ = [
    "project_browser",
    "graph_view",
    "execution_view",
    "status_dashboard",
    "gate_panel",
]