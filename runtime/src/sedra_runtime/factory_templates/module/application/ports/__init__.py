"""Port Interfaces (Application Ports).

Interfaces that the application layer expects from infrastructure.
"""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")

class RepositoryPort(ABC, Generic[T]):
    """Port for repository access."""

    @abstractmethod
    def save(self, entity: T) -> T:
        """Save entity."""

    @abstractmethod
    def find_by_id(self, id: str) -> T | None:
        """Find entity by ID."""

# Example:
# class MODULE_NAMERepositoryPort(RepositoryPort[MODULE_NAMEEntity]):
#     pass