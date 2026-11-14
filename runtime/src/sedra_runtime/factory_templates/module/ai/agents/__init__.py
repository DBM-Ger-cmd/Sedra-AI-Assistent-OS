"""Agent Definitions.

Agent configurations and orchestration logic.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class AgentConfig:
    """Agent configuration."""
    name: str = "MODULE_NAME-agent"
    model: str = "MODULE_NAME-model"
    system_prompt: str = "You are a specialized agent for MODULE_NAME."
    tools: list[str] = None
    max_iterations: int = 10

    def __post_init__(self):
        if self.tools is None:
            self.tools = []