"""Configuration — Factory Studio Konfiguration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FactoryStudioConfig:
    """Hauptkonfiguration für Factory Studio Module."""
    
    # Server-Verbindungen
    factory_registry_url: str = "http://127.0.0.1:57932"
    evidence_store_url: str = "http://127.0.0.1:57932"
    gate_server_url: str = "http://127.0.0.1:57932"
    
    # Timeouts
    http_timeout: float = 30.0
    build_timeout: float = 300.0
    benchmark_timeout: float = 600.0
    
    # Persistenz
    persistence_type: str = "memory"  # memory, sqlite, postgresql
    sqlite_path: str = "local_config/factory_studio.db"
    
    # UI-Einstellungen
    auto_refresh_interval: int = 5000  # ms
    max_graph_nodes: int = 500
    default_benchmark_iterations: int = 3
    
    # Feature-Flags
    enable_benchmarks: bool = True
    enable_gates: bool = True
    enable_graph_view: bool = True
    enable_notifications: bool = True
    
    # Benachrichtigungen
    notification_type: str = "console"  # none, console, toast
    
    # Entwicklung
    debug_mode: bool = False
    mock_external_services: bool = True  # Für Tests ohne Server
    
    @classmethod
    def from_env(cls) -> "FactoryStudioConfig":
        """Lädt Konfiguration aus Umgebungsvariablen."""
        import os
        return cls(
            factory_registry_url=os.getenv("FACTORY_REGISTRY_URL", "http://127.0.0.1:57932"),
            evidence_store_url=os.getenv("EVIDENCE_STORE_URL", "http://127.0.0.1:57932"),
            gate_server_url=os.getenv("GATE_SERVER_URL", "http://127.0.0.1:57932"),
            http_timeout=float(os.getenv("FACTORY_HTTP_TIMEOUT", "30.0")),
            persistence_type=os.getenv("FACTORY_PERSISTENCE", "memory"),
            sqlite_path=os.getenv("FACTORY_SQLITE_PATH", "local_config/factory_studio.db"),
            debug_mode=os.getenv("FACTORY_DEBUG", "false").lower() == "true",
            mock_external_services=os.getenv("FACTORY_MOCK_SERVICES", "true").lower() == "true",
        )
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "factory_registry_url": self.factory_registry_url,
            "evidence_store_url": self.evidence_store_url,
            "gate_server_url": self.gate_server_url,
            "http_timeout": self.http_timeout,
            "build_timeout": self.build_timeout,
            "benchmark_timeout": self.benchmark_timeout,
            "persistence_type": self.persistence_type,
            "sqlite_path": self.sqlite_path,
            "auto_refresh_interval": self.auto_refresh_interval,
            "max_graph_nodes": self.max_graph_nodes,
            "default_benchmark_iterations": self.default_benchmark_iterations,
            "enable_benchmarks": self.enable_benchmarks,
            "enable_gates": self.enable_gates,
            "enable_graph_view": self.enable_graph_view,
            "enable_notifications": self.enable_notifications,
            "notification_type": self.notification_type,
            "debug_mode": self.debug_mode,
            "mock_external_services": self.mock_external_services,
        }


# Default-Instanz
DEFAULT_CONFIG = FactoryStudioConfig()


def get_config() -> FactoryStudioConfig:
    """Liefert die aktive Konfiguration (Environment über Defaults)."""
    return FactoryStudioConfig.from_env()