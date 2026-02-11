from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union


class ExecutionMode(str, Enum):
    """
    Execution mode for test set runs.

    Aligns with backend ``ExecutionMode``:
    - PARALLEL: Tests dispatched concurrently (default)
    - SEQUENTIAL: Tests run one at a time
    """

    __test__ = False  # Prevent pytest collection

    PARALLEL = "Parallel"
    SEQUENTIAL = "Sequential"

    @classmethod
    def from_string(cls, value: Union[str, "ExecutionMode"]) -> "ExecutionMode":
        """Normalize a string or enum to ExecutionMode.

        Accepts lowercase or capitalized forms: "parallel", "sequential",
        "Parallel", "Sequential", or an ExecutionMode enum value.
        """
        if isinstance(value, ExecutionMode):
            return value
        normalized = str(value).strip().lower()
        if normalized == "parallel":
            return cls.PARALLEL
        if normalized == "sequential":
            return cls.SEQUENTIAL
        raise ValueError(
            f"Invalid execution mode: {value!r}. "
            "Use 'parallel', 'sequential', or ExecutionMode.PARALLEL / ExecutionMode.SEQUENTIAL"
        )


class TestType(str, Enum):
    """
    Enum for test types.

    These values align with the backend TypeLookup table:
    - SINGLE_TURN: Traditional single request-response tests
    - MULTI_TURN: Agentic multi-turn conversation tests using Penelope
    """

    __test__ = False  # Prevent pytest collection

    SINGLE_TURN = "Single-Turn"
    MULTI_TURN = "Multi-Turn"


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
