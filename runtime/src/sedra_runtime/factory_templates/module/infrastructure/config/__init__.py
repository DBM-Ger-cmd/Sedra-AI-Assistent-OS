"""Infrastructure Configuration.

Configuration classes for infrastructure components.
"""
from dataclasses import dataclass
from pathlib import Path

@dataclass
class InfrastructureConfig:
    """Infrastructure configuration."""
    database_path: Path = Path("./data/module.db")
    api_timeout_seconds: int = 30
    retry_attempts: int = 3