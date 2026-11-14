"""Repository Interfaces (Ports).

Abstract interfaces for data persistence. Implementations go in infrastructure/persistence.
"""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")

class Repository(ABC, Generic[T]):
    """Base repository interface."""

    @abstractmethod
    def save(self, entity: T) -> T:
        """Save entity."""

    @abstractmethod
    def find_by_id(self, id: str) -> T | None:
        """Find entity by ID."""

    @abstractmethod
    def delete(self, id: str) -> bool:
        """Delete entity by ID."""

# Example specific repository:
# class {{module_name}}Repository(Repository[{{module_name}}Entity]):
#     pass