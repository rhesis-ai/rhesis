"""Rules: metrics with no model and no user code.

A rule reads one thing from the unit its target picks and compares it: a field of the trace
with a fixed value (``FieldRule``), or the output with the test's expected response
(``ResponseRule``). ``ToolCallTrajectory`` is the rule for expected tool calls.

When the thing it reads wasn't recorded, a rule is not applicable: never a pass or a fail.
"""

import json
import math
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from rhesis.sdk.entities.trace import Span, Trace
from rhesis.sdk.metrics.arguments import evaluation_arguments
from rhesis.sdk.metrics.base import (
    BaseMetric,
    MetricConfig,
    MetricResult,
    MetricType,
    ScoreType,
)
from rhesis.sdk.metrics.expectations import ExpectationsLike

#: Fields a ``FieldRule`` reads, besides ``attributes.<key>``.
FIELDS = (
    "duration_ms",
    "status",
    "error_count",
    "span_count",
    "tokens.input",
    "tokens.output",
    "tokens.total",
    "cost_usd",
    "input",
    "output",
    "length.input",
    "length.output",
)
ATTRIBUTE_PREFIX = "attributes."
NUMERIC_OPS = ("<", "<=", ">", ">=")
OPS = (*NUMERIC_OPS, "==", "!=", "in", "not_in", "contains", "matches", "exists", "is_json")
#: Operators that take no value.
VALUELESS_OPS = ("exists", "is_json")
RESPONSE_MATCHES = ("exact", "contains", "matches", "similar")
SIMILARITIES = ("edit_distance", "rouge_l")

#: Above this many characters, edit distance compares words, to stay fast.
_CHARACTER_EDIT_LIMIT = 2000
#: The most characters of a text kept in a result's details.
_DETAIL_TEXT_LIMIT = 500

_TOKENS_INPUT = "ai.llm.tokens.input"
_TOKENS_OUTPUT = "ai.llm.tokens.output"
_TOKENS_TOTAL = "ai.llm.tokens.total"
_CONVERSATION_INPUT = "rhesis.conversation.input"
_CONVERSATION_OUTPUT = "rhesis.conversation.output"


def rule_not_applicable(reason: str) -> MetricResult:
    """The result of a rule whose data wasn't recorded: neither a pass nor a fail."""
    return MetricResult(
        score=None,
        details={"is_successful": None, "not_applicable": True, "reason": reason},
    )


def rule_result(passed: bool, reason: str, measured: Any, expected: Any) -> MetricResult:
    return MetricResult(
        score=1.0 if passed else 0.0,
        details={
            "is_successful": passed,
            "reason": reason,
            "measured": _for_details(measured),
            "expected": _for_details(expected),
        },
    )


class TraceRule(BaseMetric):
    """A metric with no model and no user code: it reads the trace and compares."""

    REQUIRES_MODEL = False

    def _rule_config(
        self,
        name: str,
        description: Optional[str],
        target: Optional[Union[str, Dict[str, Any]]],
        id: Optional[str],
    ) -> MetricConfig:
        return MetricConfig(
            class_name=self.__class__.__name__,
            backend="rhesis",
            name=name,
            description=description,
            score_type=ScoreType.NUMERIC,
            min_score=0.0,
            max_score=1.0,
            threshold=1.0,
            threshold_operator=">=",
            metric_type=MetricType.RULE,
            target=target,
            id=id,
        )

    def set_model(self, model: Any) -> Any:
        """No model is used, so none is built."""
        return None


class FieldRule(TraceRule):
    """Pass when a field of the unit compares as stated with a fixed value.

    ``FieldRule(field="duration_ms", op="<=", value=5000)`` passes when the unit took 5
    seconds or less. See ``FIELDS`` and ``OPS``; ``attributes.<key>`` reads any attribute of
    the unit's root span. ``span_count`` counts the unit's spans, optionally only those of
    ``span_kind`` and named ``span_name``.
    """

    def __init__(
        self,
        field: str,
        op: str,
        value: Any = None,
        negate: bool = False,
        span_kind: Optional[str] = None,
        span_name: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        target: Optional[Union[str, Dict[str, Any]]] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ):
        settings = {"field": field, "op": op, "negate": negate}
        if op not in VALUELESS_OPS:
            settings["value"] = value
        if span_kind is not None:
            settings["span_kind"] = span_kind
        if span_name is not None:
            settings["span_name"] = span_name
        self.validate_config(settings)
        self.field = field
        self.op = op
        self.value = value
        self.negate = negate
        self.span_kind = _span_kind(span_kind)
        self.span_name = span_name
        super().__init__(self._rule_config(name or self.statement, description, target, id))

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        unknown = set(config) - {"field", "op", "value", "negate", "span_kind", "span_name"}
        if unknown:
            raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")
        field, op = config.get("field"), config.get("op")
        if field not in FIELDS and not (
            isinstance(field, str)
            and field.startswith(ATTRIBUTE_PREFIX)
            and len(field) > len(ATTRIBUTE_PREFIX)
        ):
            raise ValueError(
                f"field must be one of {', '.join(FIELDS)}, or attributes.<key>; got {field!r}"
            )
        if op not in OPS:
            raise ValueError(f"op must be one of {', '.join(OPS)}; got {op!r}")
        value = config.get("value")
        if op in VALUELESS_OPS:
            if value is not None:
                raise ValueError(f"'{op}' takes no value")
        elif "value" not in config or value is None:
            raise ValueError(f"'{op}' needs a value")
        if op in NUMERIC_OPS and _number(value) is None:
            raise ValueError(f"'{op}' compares with a number; got {value!r}")
        if op in ("in", "not_in") and not isinstance(value, list):
            raise ValueError(f"'{op}' takes a list of values")
        if op == "matches":
            if not isinstance(value, str):
                raise ValueError("'matches' takes a regular expression")
            try:
                re.compile(value)
            except re.error as e:
                raise ValueError(f"Invalid regular expression: {e}") from e
        if not isinstance(config.get("negate", False), bool):
            raise ValueError("negate must be true or false")
        if field != "span_count" and (
            config.get("span_kind") is not None or config.get("span_name") is not None
        ):
            raise ValueError("span_kind and span_name only narrow span_count")
        if config.get("span_kind") is not None:
            _span_kind(config["span_kind"])
        return config

    @property
    def statement(self) -> str:
        """The rule in one line, such as ``duration_ms <= 5000``."""
        return _statement(
            self.field, self.op, self.value, self.negate, self.span_kind, self.span_name
        )

    @evaluation_arguments
    def evaluate(
        self,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        trace: Optional[Trace] = None,
    ) -> MetricResult:
        measured, missing = self._read(input, output, trace)
        if missing is not None and self.op != "exists":
            return rule_not_applicable(missing)
        passed, failure = _compare(self.op, measured, self.value, self.field)
        if self.negate:
            passed = not passed
        verdict = "passes" if passed else "fails"
        reason = f"{_label(self.field)} is {_shown(measured)}, so `{self.statement}` {verdict}."
        if failure and not self.negate:
            reason = f"{failure} `{self.statement}` fails."
        return rule_result(passed, reason, measured, self.value)

    def _read(self, input: Any, output: Any, trace: Optional[Trace]) -> Tuple[Any, Optional[str]]:
        """The field's value, and why it is missing (None when it was read)."""
        roots = list(trace.root_spans) if trace is not None else []
        spans = trace.spans() if roots else []
        field = self.field
        if field == "duration_ms":
            value = _duration(roots)
            return value, None if value is not None else (
                "No timing was recorded here. Reported spans and traces built from a bare "
                "response have none; send traces to judge timing."
            )
        if field == "status":
            return ("error" if any(_status(span) == "error" for span in roots) else "ok"), None
        if field == "error_count":
            return sum(1 for span in spans if _status(span) == "error"), None
        if field == "span_count":
            return sum(1 for span in spans if self._counted(span)), None
        if field.startswith("tokens."):
            value = _tokens(spans, field.split(".", 1)[1])
            return value, None if value is not None else (
                "No model call here reported token counts. Map usage in the endpoint's "
                "response, or send traces."
            )
        if field == "cost_usd":
            costs = [span.cost_usd for span in spans if span.cost_usd is not None]
            return (sum(costs), None) if costs else (None, "No cost was recorded here.")
        if field.startswith(ATTRIBUTE_PREFIX):
            key = field[len(ATTRIBUTE_PREFIX) :]
            value = next((s.attributes[key] for s in roots if key in s.attributes), None)
            return value, None if value is not None else f"The attribute `{key}` isn't set."
        which = field.split(".", 1)[1] if field.startswith("length.") else field
        text = _turn_value(trace, which, input if which == "input" else output)
        if text is None:
            return None, f"No {which} was recorded here."
        if field.startswith("length."):
            return len(_text(text)), None
        return text, None

    def _counted(self, span: Span) -> bool:
        if self.span_kind is not None and span.kind != self.span_kind:
            return False
        return self.span_name is None or self.span_name in _names(span)


class ResponseRule(TraceRule):
    """Pass when the unit's output matches the test's expected response.

    ``match`` is ``exact``, ``contains``, ``matches`` (the expected response is a regular
    expression) or ``similar``, which needs ``min_similarity`` (0 to 1) and compares by
    ``similarity``: ``rouge_l`` (the default) or ``edit_distance``.
    """

    REQUIRED_EXPECTATIONS = ("response",)

    def __init__(
        self,
        match: str = "exact",
        similarity: Optional[str] = None,
        min_similarity: Optional[float] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        target: Optional[Union[str, Dict[str, Any]]] = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ):
        settings: Dict[str, Any] = {"match": match}
        if similarity is not None:
            settings["similarity"] = similarity
        if min_similarity is not None:
            settings["min_similarity"] = min_similarity
        self.validate_config(settings)
        self.match = match
        self.similarity = similarity or ("rouge_l" if match == "similar" else None)
        self.min_similarity = min_similarity
        default_name = (
            f"Response similar ({self.similarity}, at least {min_similarity})"
            if match == "similar"
            else f"Response {match.replace('_', ' ')}"
        )
        super().__init__(self._rule_config(name or default_name, description, target, id))

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        unknown = set(config) - {"match", "similarity", "min_similarity"}
        if unknown:
            raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")
        match = config.get("match", "exact")
        if match not in RESPONSE_MATCHES:
            raise ValueError(f"match must be one of {', '.join(RESPONSE_MATCHES)}; got {match!r}")
        similarity = config.get("similarity")
        minimum = config.get("min_similarity")
        if match != "similar":
            if similarity is not None or minimum is not None:
                raise ValueError("similarity and min_similarity only go with match 'similar'")
            return config
        if similarity is not None and similarity not in SIMILARITIES:
            raise ValueError(f"similarity must be one of {', '.join(SIMILARITIES)}")
        number = _number(minimum)
        if number is None or not 0 <= number <= 1:
            raise ValueError("'similar' needs min_similarity between 0 and 1")
        return config

    @evaluation_arguments
    def evaluate(
        self, output: Optional[Any] = None, expectations: ExpectationsLike = None
    ) -> MetricResult:
        expected = expectations.response if expectations is not None else None
        if expected is None:
            return rule_not_applicable(
                "The test has no expected response. Add one to compare the output with it."
            )
        if output is None:
            return rule_not_applicable("No output was recorded here.")
        actual, wanted = _text(output), _text(expected)
        if self.match == "exact":
            passed = actual.strip() == wanted.strip()
            reason = (
                "The output equals the expected response."
                if passed
                else ("The output differs from the expected response.")
            )
            return rule_result(passed, reason, actual, wanted)
        if self.match == "contains":
            passed = wanted in actual
            reason = (
                "The output contains the expected response."
                if passed
                else ("The output doesn't contain the expected response.")
            )
            return rule_result(passed, reason, actual, wanted)
        if self.match == "matches":
            try:
                passed = re.search(wanted, actual) is not None
            except re.error as e:
                return rule_not_applicable(
                    f"The expected response is not a valid regular expression: {e}"
                )
            reason = (
                "The output matches the expected pattern."
                if passed
                else ("The output doesn't match the expected pattern.")
            )
            return rule_result(passed, reason, actual, wanted)
        score = (
            edit_similarity(actual, wanted)
            if self.similarity == "edit_distance"
            else rouge_l(actual, wanted)
        )
        minimum = float(self.min_similarity)
        passed = score >= minimum
        reason = (
            f"The output's {self.similarity} similarity to the expected response is "
            f"{score:.2f}; the minimum is {minimum:g}."
        )
        return rule_result(passed, reason, round(score, 4), minimum)


def edit_similarity(a: str, b: str) -> float:
    """1 minus the edit distance over the longer length: 1 for equal texts, 0 for unrelated.
    Long texts compare words rather than characters."""
    if len(a) > _CHARACTER_EDIT_LIMIT or len(b) > _CHARACTER_EDIT_LIMIT:
        left: Sequence[str] = a.split()
        right: Sequence[str] = b.split()
    else:
        left, right = a, b
    longest = max(len(left), len(right))
    if longest == 0:
        return 1.0
    return 1.0 - _levenshtein(left, right) / longest


def rouge_l(a: str, b: str) -> float:
    """ROUGE-L: the F-measure of the longest common subsequence of lowercase words,
    punctuation left out."""
    left, right = re.findall(r"\w+", a.lower()), re.findall(r"\w+", b.lower())
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    common = _lcs(left, right)
    if common == 0:
        return 0.0
    precision, recall = common / len(left), common / len(right)
    return 2 * precision * recall / (precision + recall)


def _levenshtein(a: Sequence[str], b: Sequence[str]) -> int:
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def _lcs(a: Sequence[str], b: Sequence[str]) -> int:
    previous = [0] * (len(b) + 1)
    for x in a:
        current = [0]
        for j, y in enumerate(b, 1):
            current.append(previous[j - 1] + 1 if x == y else max(previous[j], current[j - 1]))
        previous = current
    return previous[-1]


def _span_kind(kind: Optional[str]) -> Optional[str]:
    """A span kind (``tool.invoke``) from itself or a target's name (``tool_call``)."""
    if kind is None:
        return None
    from rhesis.sdk.metrics.targets import TARGETS, TargetKind

    try:
        preset = TARGETS[TargetKind(kind)]
    except ValueError:
        return kind
    if preset.span_kind is None:
        raise ValueError(f"span_kind '{kind}' is not a kind of span")
    return preset.span_kind


def _duration(roots: List[Span]) -> Optional[float]:
    if not roots:
        return None
    if len(roots) == 1:
        return roots[0].duration_ms
    # Several turns: from the first one's start to the last one's end, if all were timed.
    if any(span.duration_ms is None or not span.start_time or not span.end_time for span in roots):
        return None
    start = min(span.start_time for span in roots)
    end = max(span.end_time for span in roots)
    return (end - start).total_seconds() * 1000


def _status(span: Span) -> str:
    code = (span.status_code or "").lower().removeprefix("status_code_")
    return "error" if code == "error" else "ok"


def _tokens(spans: Iterable[Span], which: str) -> Optional[int]:
    # Only model calls: a span around them may repeat their counts.
    total, found = 0, False
    for span in spans:
        if span.kind != "llm.invoke":
            continue
        counts = {
            "input": _number(span.attributes.get(_TOKENS_INPUT)),
            "output": _number(span.attributes.get(_TOKENS_OUTPUT)),
        }
        reported_total = _number(span.attributes.get(_TOKENS_TOTAL))
        if which == "total":
            value = reported_total
            if value is None and (counts["input"] is not None or counts["output"] is not None):
                value = (counts["input"] or 0) + (counts["output"] or 0)
        else:
            value = counts[which]
        if value is not None:
            total, found = total + int(value), True
    return total if found else None


def _turn_value(trace: Optional[Trace], which: str, given: Any) -> Any:
    """The unit's input or output. A unit of several turns reads its first turn's input and
    its last turn's output; otherwise the value handed to the rule."""
    if trace is not None and len(trace.root_spans) > 1:
        turns = trace._turn_roots()
        if len(turns) > 1:
            span = turns[0] if which == "input" else turns[-1]
            key = _CONVERSATION_INPUT if which == "input" else _CONVERSATION_OUTPUT
            value = span.attributes.get(key)
            return value if value is not None else getattr(span, which)
    return given


def _names(span: Span) -> List[str]:
    candidates = [
        span.tool_name,
        span.attributes.get("ai.agent.name"),
        span.model_name,
        span.attributes.get("ai.model.name"),
        span.span_name,
    ]
    return [name for name in candidates if isinstance(name, str) and name]


def _compare(op: str, measured: Any, value: Any, field: str) -> Tuple[bool, Optional[str]]:
    """Whether ``measured`` compares as ``op`` says with ``value``, and why not when it can't
    be compared at all."""
    if op == "exists":
        return measured is not None, None
    if op == "is_json":
        return _is_json(measured), None
    if op in NUMERIC_OPS:
        left, right = _number(measured), _number(value)
        if left is None:
            return False, f"{_label(field)} is {_shown(measured)}, not a number, so"
        return {
            "<": left < right,
            "<=": left <= right,
            ">": left > right,
            ">=": left >= right,
        }[op], None
    if op == "==":
        return _same(measured, value, field), None
    if op == "!=":
        return not _same(measured, value, field), None
    if op == "in":
        return any(_same(measured, choice, field) for choice in value), None
    if op == "not_in":
        return not any(_same(measured, choice, field) for choice in value), None
    if op == "contains":
        return _text(value) in _text(measured), None
    return re.search(value, _text(measured)) is not None, None


def _same(measured: Any, value: Any, field: str) -> bool:
    # Attributes can arrive as text: 200 and "200", true and "true" are the same.
    left, right = _number(measured), _number(value)
    if left is not None and right is not None:
        return left == right
    if field == "status":
        return _text(measured).lower() == _text(value).lower()
    return _text(measured) == _text(value)


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def _is_json(value: Any) -> bool:
    if isinstance(value, (dict, list)):
        return True
    if not isinstance(value, str):
        return False
    try:
        json.loads(value)
    except ValueError:
        return False
    return True


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str)


def _label(field: str) -> str:
    return f"`{field}`"


def _shown(value: Any) -> str:
    number = _number(value) if not isinstance(value, str) else None
    if number is not None:
        return f"{number:,.0f}" if number.is_integer() else f"{number:,.4g}"
    text = _text(value)
    return repr(text if len(text) <= 80 else text[:77] + "...")


def _statement(
    field: str,
    op: str,
    value: Any,
    negate: bool,
    span_kind: Optional[str],
    span_name: Optional[str],
) -> str:
    subject = field
    if field == "span_count" and (span_kind or span_name):
        subject = f"span_count({', '.join(p for p in (span_kind, span_name) if p)})"
    rule = f"{subject} {op}" if op in VALUELESS_OPS else f"{subject} {op} {_text(value)}"
    return f"not {rule}" if negate else rule


def _for_details(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _DETAIL_TEXT_LIMIT:
        return value[: _DETAIL_TEXT_LIMIT - 3] + "..."
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_for_details(item) for item in value]
    return _for_details(_text(value))
