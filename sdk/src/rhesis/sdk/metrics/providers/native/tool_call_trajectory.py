"""Compare the tools an endpoint called with the tools the test expected. No model involved."""

from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Union

from rhesis.sdk.entities.trace import Trace
from rhesis.sdk.metrics.arguments import evaluation_arguments
from rhesis.sdk.metrics.base import (
    BaseMetric,
    MetricConfig,
    MetricResult,
    MetricScope,
    MetricType,
    ScoreType,
)
from rhesis.sdk.metrics.expectations import ExpectationsLike, ExpectedToolCall


class TrajectoryMatch(str, Enum):
    """How the called tools must line up with the expected ones."""

    EXACT = "exact"
    """The same calls in the same order, and nothing else."""
    IN_ORDER = "in_order"
    """The expected calls in order; other calls may come between them."""
    ANY_ORDER = "any_order"
    """The same calls in any order, and nothing else."""
    SUBSET = "subset"
    """Every call made was expected; expected calls may be missing."""
    SUPERSET = "superset"
    """Every expected call was made; other calls are allowed."""


class ArgumentMatch(str, Enum):
    """How a called tool's arguments must match the expected ones."""

    EXACT = "exact"
    """The arguments equal the expected ones."""
    PARTIAL = "partial"
    """The expected keys have the expected values; other keys are ignored."""
    IGNORE = "ignore"
    """Only the tool's name is compared."""


class ToolCallTrajectory(BaseMetric):
    """Pass when the trace's tool calls match the test's expected tool calls.

    The actual calls are ``trace.tool_calls``; the expected ones are
    ``expectations.tool_calls``. A test without expected tool calls can't be judged by
    this metric, and ``evaluate`` refuses it.
    """

    REQUIRED_EXPECTATIONS = ("tool_calls",)
    REQUIRES_MODEL = False

    def __init__(
        self,
        match: Union[TrajectoryMatch, str] = TrajectoryMatch.IN_ORDER,
        arguments: Union[ArgumentMatch, str] = ArgumentMatch.PARTIAL,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metric_scope: Optional[List[Union[str, MetricScope]]] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ):
        self.match = TrajectoryMatch(match)
        self.arguments = ArgumentMatch(arguments)
        super().__init__(
            MetricConfig(
                class_name=self.__class__.__name__,
                backend="rhesis",
                name=name or "Tool Call Trajectory",
                description=description,
                score_type=ScoreType.NUMERIC,
                min_score=0.0,
                max_score=1.0,
                threshold=1.0,
                threshold_operator=">=",
                metric_type=MetricType.CUSTOM_CODE,
                metric_scope=metric_scope or [MetricScope.SINGLE_TURN, MetricScope.MULTI_TURN],
                id=id,
            )
        )

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        unknown = set(config) - {"match", "arguments"}
        if unknown:
            raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")
        if "match" in config:
            TrajectoryMatch(config["match"])
        if "arguments" in config:
            ArgumentMatch(config["arguments"])
        return config

    def set_model(self, model: Any) -> Any:
        """No model is used, so none is built."""
        return None

    @evaluation_arguments
    def evaluate(
        self, trace: Optional[Trace] = None, expectations: ExpectationsLike = None
    ) -> MetricResult:
        expected = expectations.tool_calls if expectations is not None else None
        if expected is None:
            raise ValueError(
                "The test has no expected tool calls; pass expectations={'tool_calls': [...]}."
            )
        return compare_trajectories(
            expected, trace.tool_calls if trace else [], self.match, self.arguments
        )


def compare_trajectories(
    expected: Sequence[ExpectedToolCall],
    actual: Sequence[Dict[str, Any]],
    match: TrajectoryMatch = TrajectoryMatch.IN_ORDER,
    arguments: ArgumentMatch = ArgumentMatch.PARTIAL,
) -> MetricResult:
    """The verdict, precision and recall of ``actual`` calls against ``expected`` ones."""

    def same(e: ExpectedToolCall, a: Dict[str, Any]) -> bool:
        return e.name == a.get("name") and _arguments_match(e, a.get("arguments"), arguments)

    pairs = _matching(expected, actual, same)
    if not expected:
        # An empty list expects no calls, whatever the mode.
        passed = not actual
    elif match is TrajectoryMatch.EXACT:
        passed = len(expected) == len(actual) and all(map(same, expected, actual))
    elif match is TrajectoryMatch.IN_ORDER:
        passed = _first_missing_in_order(expected, actual, same) is None
    elif match is TrajectoryMatch.ANY_ORDER:
        passed = pairs == len(expected) == len(actual)
    elif match is TrajectoryMatch.SUBSET:
        passed = pairs == len(actual)
    else:
        passed = pairs == len(expected)

    reason = (
        f"The tool calls match ({match.value.replace('_', ' ')})."
        if passed
        else _difference(expected, actual, match, same)
    )
    return MetricResult(
        score=1.0 if passed else 0.0,
        details={
            "is_successful": passed,
            "reason": reason,
            "precision": pairs / len(actual) if actual else 1.0,
            "recall": pairs / len(expected) if expected else 1.0,
            "expected_tool_calls": [call.name for call in expected],
            "actual_tool_calls": [call.get("name") for call in actual],
        },
    )


def _arguments_match(expected: ExpectedToolCall, actual: Any, mode: ArgumentMatch) -> bool:
    if mode is ArgumentMatch.IGNORE or expected.arguments is None:
        return True
    if mode is ArgumentMatch.PARTIAL and not expected.arguments:
        return True
    actual = {} if actual is None else actual
    if not isinstance(actual, dict):
        return False
    if mode is ArgumentMatch.EXACT:
        return _same_value(actual, expected.arguments)
    return all(
        key in actual and _same_value(actual[key], value)
        for key, value in expected.arguments.items()
    )


def _same_value(actual: Any, expected: Any) -> bool:
    """Equal, without ``True`` matching ``1`` as Python's ``==`` would."""
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _same_value(actual[k], expected[k]) for k in actual
        )
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(map(_same_value, actual, expected))
    return actual == expected


def _matching(expected, actual, same) -> int:
    """The most expected calls that can each be paired with a different actual call."""
    return len(expected) - len(_unpaired(expected, actual, same))


def _unpaired(expected, actual, same) -> List[int]:
    """The expected calls left without a different actual call each, in order.

    Pairs them one at a time, keeping the pairing as large as possible for the calls seen
    so far, so the first index returned is the first call that can't be paired.
    """
    owner: Dict[int, int] = {}

    def assign(i: int, seen: set) -> bool:
        for j, call in enumerate(actual):
            if j in seen or not same(expected[i], call):
                continue
            seen.add(j)
            if j not in owner or assign(owner[j], seen):
                owner[j] = i
                return True
        return False

    return [i for i in range(len(expected)) if not assign(i, set())]


def _first_missing_in_order(expected, actual, same) -> Optional[int]:
    """The index of the first expected call not found after the ones before it."""
    position = 0
    for i, call in enumerate(expected):
        while position < len(actual) and not same(call, actual[position]):
            position += 1
        if position == len(actual):
            return i
        position += 1
    return None


def _difference(expected, actual, match: TrajectoryMatch, same) -> str:
    """The first way ``actual`` differs from ``expected``, in words."""
    if not expected:
        return f"`{actual[0].get('name')}` was called, but the test expects no tool calls."
    if not actual:
        return (
            "No tool calls were recorded. If the endpoint makes them, map tool_calls in its "
            "response or send traces."
        )
    if match is TrajectoryMatch.EXACT:
        for i, (e, a) in enumerate(zip(expected, actual, strict=False)):
            if not same(e, a):
                return f"Call {i + 1} was `{a.get('name')}`, expected {_described(e, actual)}."
        return f"Expected {len(expected)} tool calls, got {len(actual)}."

    missing = _unmatched_expected(expected, actual, same, match)
    if missing is not None:
        call = expected[missing]
        if match is TrajectoryMatch.IN_ORDER and missing > 0:
            previous = expected[missing - 1].name
            return f"Expected `{call.name}` after `{previous}`; {_described(call, actual, '')}."
        return f"Expected {_described(call, actual)}."
    extra = _unmatched_actual(expected, actual, same)
    return f"`{actual[extra].get('name')}` was called but not expected."


def _described(call: ExpectedToolCall, actual, prefix: Optional[str] = None) -> str:
    """Why ``call`` didn't match, after ``prefix`` (the call's name unless given)."""
    lead = f"`{call.name}`; " if prefix is None else prefix
    made = [a for a in actual if a.get("name") == call.name]
    if not made:
        return f"{lead}it was never called"
    if call.arguments and all(isinstance(a.get("arguments"), str) for a in made):
        return f"{lead}its arguments were recorded as text, so they could not be compared"
    return f"{lead}it was called with other arguments or out of order"


def _unmatched_expected(expected, actual, same, match) -> Optional[int]:
    if match is TrajectoryMatch.IN_ORDER:
        return _first_missing_in_order(expected, actual, same)
    if match is TrajectoryMatch.SUBSET:
        return None
    return next(iter(_unpaired(expected, actual, same)), None)


def _unmatched_actual(expected, actual, same) -> int:
    def flipped(a, e):
        return same(e, a)

    return next(iter(_unpaired(actual, expected, flipped)), len(actual) - 1)
