"""Utility functions for common synthesizer operations."""

from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, Template

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.enums import TestType
from rhesis.sdk.models.base import BaseLLM


def load_prompt_template(prompt_template_file: str) -> "Template":
    """Load prompt template from assets or use custom prompt."""
    templates_path = Path(__file__).parent / "assets"
    environment = Environment(loader=FileSystemLoader(templates_path))
    template = environment.get_template(prompt_template_file)
    return template


def create_test_set_metadata(synthesizer_name: str, batch_size: int, **kwargs) -> Dict[str, Any]:
    """Create standardized metadata for test sets."""
    base_metadata = {
        "synthesizer": synthesizer_name,
        "batch_size": batch_size,
    }
    base_metadata.update(kwargs)
    return base_metadata


def create_test_set(tests: List[Dict], model: BaseLLM, **metadata_kwargs) -> "TestSet":
    """Create and configure a TestSet with metadata."""
    from rhesis.sdk.entities.test_set import TestSet

    metadata = create_test_set_metadata(**metadata_kwargs)
    # Pass the empty string for name, description, and short_description to pass pydantic validation
    test_set = TestSet(
        tests=tests,
        metadata=metadata,
        name="",
        description="",
        short_description="",
        test_set_type=TestType.SINGLE_TURN,
    )
    test_set.set_properties(model)
    return test_set


def stamp_multi_turn(test_set: "TestSet") -> "TestSet":
    """Mark *test_set* as multi-turn: set ``test_set_type`` and suffix the name.

    Callers typically build a TestSet via :func:`create_test_set` (which always
    sets ``test_set_type=SINGLE_TURN``) and then call this afterward once they
    know generation was multi-turn. Shared so the "... (Multi-Turn)" naming
    convention lives in one place instead of being reimplemented per synthesizer.
    """
    test_set.test_set_type = TestType.MULTI_TURN
    if test_set.name:
        test_set.name = f"{test_set.name} (Multi-Turn)"
    return test_set
