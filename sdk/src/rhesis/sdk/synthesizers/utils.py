"""Utility functions for common synthesizer operations."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

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


def canonical_requirement(value: Any, allowed: Optional[Sequence[str]]) -> Optional[str]:
    """Map a generated requirement onto the requested ones, or None if it is none of them.

    Returns the caller's own spelling. Matching is exact first, then case- and
    whitespace-insensitive, so "compliance" for a requested "Compliance" is corrected
    rather than saved as a second requirement. With nothing requested, the value
    passes through unchanged.
    """
    if not allowed:
        return None if value is None else str(value)
    text = str(value or "").strip()
    if text in allowed:
        return text
    folded = text.casefold()
    for candidate in allowed:
        if folded == candidate.strip().casefold():
            return candidate
    return None


# The limits the platform's MultiTurnTestConfig applies when a multi-turn test is saved.
_MULTI_TURN_TEXT_LIMITS = {
    "goal": 5000,
    "instructions": 10000,
    "restrictions": 10000,
    "scenario": 5000,
}
_TURN_RANGE = (1, 50)


def multi_turn_config_problem(config: Dict[str, Any]) -> Optional[str]:
    """Why the platform would refuse to save this multi-turn test configuration, or None.

    Mirrors ``MultiTurnTestConfig`` in the backend's ``schemas/multi_turn_test_config.py``.
    """
    if not str(config.get("goal") or "").strip():
        return "goal is empty"
    for field, limit in _MULTI_TURN_TEXT_LIMITS.items():
        if len(str(config.get(field) or "").strip()) > limit:
            return f"{field} is longer than {limit} characters"
    turns = {f: config.get(f) for f in ("min_turns", "max_turns") if config.get(f) is not None}
    for field, value in turns.items():
        if not _TURN_RANGE[0] <= value <= _TURN_RANGE[1]:
            return f"{field} must be between {_TURN_RANGE[0]} and {_TURN_RANGE[1]}"
    if len(turns) == 2 and turns["min_turns"] > turns["max_turns"]:
        return "min_turns is above max_turns"
    return None
