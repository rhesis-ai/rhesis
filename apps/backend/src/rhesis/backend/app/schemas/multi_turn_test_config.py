"""
Schema for multi-turn test configuration stored in test.test_configuration JSON field.

This is separate from the TestConfiguration entity - this validates the JSON
stored in the test's test_configuration attribute for multi-turn tests.
"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class MultiTurnTestConfig(BaseModel):
    """
    Configuration for multi-turn tests.

    Stored in test.test_configuration JSONB column when test_type is multi-turn.
    These fields define how Penelope should execute the test.
    """

    goal: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="What the target SHOULD do - success criteria (required)",
    )
    instructions: Optional[str] = Field(
        None,
        max_length=10000,
        description="HOW Penelope should conduct the test - methodology (optional)",
    )
    restrictions: Optional[str] = Field(
        None,
        max_length=10000,
        description="What the target MUST NOT do - forbidden behaviors (optional)",
    )
    scenario: Optional[str] = Field(
        None,
        max_length=5000,
        description="Context and persona for the test (optional)",
    )
    max_turns: Optional[int] = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of conversation turns (default: 10)",
    )

    @field_validator("goal", "instructions", "restrictions", "scenario")
    @classmethod
    def strip_whitespace(cls, v: Optional[str]) -> Optional[str]:
        """Strip leading/trailing whitespace from string fields."""
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None

    model_config = {"extra": "forbid"}  # Don't allow additional fields


def validate_multi_turn_config(config_dict: dict) -> MultiTurnTestConfig:
    """
    Validate a test_configuration dict for multi-turn tests.

    Args:
        config_dict: Dictionary to validate

    Returns:
        Validated MultiTurnTestConfig instance

    Raises:
        ValidationError: If validation fails
    """
    return MultiTurnTestConfig.model_validate(config_dict)
