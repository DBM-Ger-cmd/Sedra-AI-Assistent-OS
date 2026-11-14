"""Data Transfer Objects.

Data structures for crossing layer boundaries.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class MODULE_NAMEDTO:
    """Example DTO for MODULE_NAME."""
    id: Optional[str] = None
    name: str = ""
    description: str = ""