from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TestType(str, Enum):
    """
    Enum for test types.

    These values align with the backend TypeLookup table:
    - SINGLE_TURN: Traditional single request-response tests
    - MULTI_TURN: Agentic multi-turn conversation tests using Penelope
    - IMAGE: Image generation/analysis tests
    """

    __test__ = False  # Prevent pytest from collecting this class as a test

    SINGLE_TURN = "Single-Turn"
    MULTI_TURN = "Multi-Turn"
    IMAGE = "Image"


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
