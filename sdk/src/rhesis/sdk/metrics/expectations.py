"""What should have happened, which a metric compares the trace with."""

from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, ConfigDict


class Expectations(BaseModel):
    """What a test expects. Every field is optional, and production traces have none.

    A plain string is read as the expected response, so ``expectations="Paris"`` works
    wherever ``Expectations`` does.
    """

    model_config = ConfigDict(frozen=True)

    response: Optional[str] = None
    """The expected answer, the reference a judge or exact-match check compares with."""
    goal: Optional[str] = None
    """What a conversation should achieve."""
    instructions: Optional[str] = None
    """How the test should be carried out, which judges read alongside the goal."""
    restrictions: Optional[str] = None
    """What the endpoint must not do."""
    contract: Optional[Dict[str, Any]] = None
    """The evaluation contract read from the test: the criteria the endpoint must meet."""

    @classmethod
    def coerce(
        cls, value: Union["Expectations", str, Dict[str, Any], None]
    ) -> Optional["Expectations"]:
        """``value`` as Expectations: a string is the expected response, a dict its fields."""
        if value is None or isinstance(value, Expectations):
            return value
        if isinstance(value, str):
            return cls(response=value)
        if isinstance(value, dict):
            return cls.model_validate(value)
        raise TypeError(
            f"expectations must be Expectations, a string or a dict, not {type(value).__name__}"
        )


#: What ``evaluate()`` accepts for ``expectations``: a string is the expected response.
ExpectationsLike = Union[Expectations, str, Dict[str, Any], None]
