"""What should have happened, which a metric compares the trace with."""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExpectedToolCall(BaseModel):
    """A tool call a test expects: the tool's name, and optionally the arguments that matter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    arguments: Optional[Dict[str, Any]] = None
    """Only the keys that matter. None means any arguments."""


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
    tool_calls: Optional[List[ExpectedToolCall]] = None
    """The tools the endpoint should call, in order. An empty list expects no calls; None
    means the test doesn't say. On a conversation with ``tool_calls_per_turn`` and no list of
    its own, the turns' calls in order."""
    tool_calls_per_turn: Optional[List[Optional[List[ExpectedToolCall]]]] = None
    """A conversation's expected tool calls turn by turn: item i is turn i+1's, None where
    the test doesn't say for that turn."""

    @model_validator(mode="before")
    @classmethod
    def _join_turns(cls, data: Any) -> Any:
        # The whole conversation's calls are its turns' calls, unless the test lists its own.
        if not isinstance(data, dict) or data.get("tool_calls") is not None:
            return data
        turns = data.get("tool_calls_per_turn")
        if not turns or all(turn is None for turn in turns):
            return data
        return {**data, "tool_calls": [call for turn in turns if turn for call in turn]}

    def turn_tool_calls(self, turn: int) -> Optional[List[ExpectedToolCall]]:
        """The calls expected in turn ``turn`` (0 for the first), or None when the test
        doesn't say."""
        turns = self.tool_calls_per_turn or []
        return turns[turn] if 0 <= turn < len(turns) else None

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
