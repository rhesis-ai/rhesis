from dataclasses import dataclass
from typing import Optional


@dataclass
class Document:
    """Document structure for document processing."""

    name: str
    description: str
    path: Optional[str] = None
    content: Optional[str] = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("Document name is required")
        if not self.description:
            raise ValueError("Document description is required")
        if not self.path and not self.content:
            raise ValueError("Either 'path' or 'content' must be provided")
