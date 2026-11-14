"""AI Model Definitions.

Model configurations and provider-specific settings.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class ModelConfig:
    """AI Model configuration."""
    name: str = "MODULE_NAME-model"
    provider: str = "local"  # local, openai, anthropic, etc.
    model_id: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    api_key: Optional[str] = None
    endpoint: Optional[str] = None