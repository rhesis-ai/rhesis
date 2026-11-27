"""Comparing a value with a fixed one, shared by rules and targets.

A rule compares one field of a unit with a value (``FieldRule``); a target keeps the spans
whose fields meet its conditions (``Condition``). Both use the operators and the comparison
here, so "200" equals 200 and a regular expression means the same in both.

Patterns for ``matches`` must mean the same in Python and in Postgres, where the platform
filters spans by a target: ``check_portable_pattern`` refuses the constructs that don't.
"""

import json
import math
import re
from enum import StrEnum
from typing import Any, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ConditionOp(StrEnum):
    """How a value is compared. Stored and sent as its plain text, such as ``"not_in"``."""

    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    MATCHES = "matches"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    IS_JSON = "is_json"


class SpecialField(StrEnum):
    """Fields a condition reads besides span attributes. ``name`` is the tool, agent or model
    name, else the span's name, as a target's ``name`` reads it."""

    KIND = "kind"
    NAME = "name"
    SPAN_NAME = "span_name"
    DURATION_MS = "duration_ms"
    STATUS = "status"


class SpanStatus(StrEnum):
    """A span's status as conditions and rules read it."""

    OK = "ok"
    ERROR = "error"


#: OpenTelemetry writes status codes as ``STATUS_CODE_ERROR``; some exporters drop the prefix.
_STATUS_CODE_PREFIX = "status_code_"


def span_status(status_code: Optional[str]) -> SpanStatus:
    """A span's status from its recorded status code: only an error code is an error."""
    code = (status_code or "").lower().removeprefix(_STATUS_CODE_PREFIX)
    return SpanStatus.ERROR if code == SpanStatus.ERROR else SpanStatus.OK


NUMERIC_OPS = (ConditionOp.LT, ConditionOp.LE, ConditionOp.GT, ConditionOp.GE)
#: The operators a rule takes.
OPS = tuple(op for op in ConditionOp if op is not ConditionOp.NOT_EXISTS)
#: Operators that take no value.
VALUELESS_OPS = (ConditionOp.EXISTS, ConditionOp.NOT_EXISTS, ConditionOp.IS_JSON)
#: The operators a target's condition takes: a rule's, without ``is_json``, plus
#: ``not_exists``.
CONDITION_OPS = tuple(op for op in ConditionOp if op is not ConditionOp.IS_JSON)
#: Operators a missing value meets: "channel is not internal" keeps spans with no channel.
MET_WHEN_MISSING = (ConditionOp.NE, ConditionOp.NOT_IN, ConditionOp.NOT_EXISTS)
#: Operators that pick by value, which a description reads as "named ..." or a kind's noun.
CHOICE_OPS = (ConditionOp.EQ, ConditionOp.IN)

#: A regular expression is searched in at most this many characters, and may be at most
#: ``PATTERN_LIMIT`` long: the standard library has no time limit for a slow pattern.
REGEX_TEXT_LIMIT = 100_000
PATTERN_LIMIT = 1000

SPECIAL_FIELDS = {
    SpecialField.KIND: "Kind",
    SpecialField.NAME: "Name",
    SpecialField.SPAN_NAME: "Span name",
    SpecialField.DURATION_MS: "Duration (ms)",
    SpecialField.STATUS: "Status",
}
#: Reads an attribute whose key is also a special field's name: ``attributes.status``.
ATTRIBUTE_PREFIX = "attributes."

Scalar = (str, int, float, bool)


def compare(op: str, measured: Any, value: Any, field: str) -> bool:
    """Whether ``measured`` compares as ``op`` says with ``value``. A numeric comparison with
    something that isn't a number is false; callers that must tell those apart check first."""
    op = ConditionOp(op)
    if op is ConditionOp.EXISTS:
        return measured is not None
    if op is ConditionOp.NOT_EXISTS:
        return measured is None
    if op is ConditionOp.IS_JSON:
        return is_json(measured)
    if op in NUMERIC_OPS:
        left, right = number(measured), number(value)
        if left is None or right is None:
            return False
        return {
            ConditionOp.LT: left < right,
            ConditionOp.LE: left <= right,
            ConditionOp.GT: left > right,
            ConditionOp.GE: left >= right,
        }[op]
    if op is ConditionOp.EQ:
        return same(measured, value, field)
    if op is ConditionOp.NE:
        return not same(measured, value, field)
    if op is ConditionOp.IN:
        return any(same(measured, choice, field) for choice in value)
    if op is ConditionOp.NOT_IN:
        return not any(same(measured, choice, field) for choice in value)
    if op is ConditionOp.CONTAINS:
        return text(value) in text(measured)
    return re.search(value, text(measured)[:REGEX_TEXT_LIMIT]) is not None


def same(measured: Any, value: Any, field: str) -> bool:
    # Attributes can arrive as text: 200 and "200", true and "true" are the same.
    left, right = number(measured), number(value)
    if left is not None and right is not None:
        return left == right
    if field == SpecialField.STATUS:
        return text(measured).lower() == text(value).lower()
    return text(measured) == text(value)


def number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None


def is_json(value: Any) -> bool:
    if isinstance(value, (dict, list)):
        return True
    if not isinstance(value, str):
        return False
    try:
        json.loads(value)
    except ValueError:
        return False
    return True


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str)


def known_op(op: Any, ops: Tuple[ConditionOp, ...] = OPS) -> ConditionOp:
    """``op`` as an operator, or a ``ValueError`` listing the ones ``ops`` allows."""
    if op not in ops:
        raise ValueError(f"op must be one of {', '.join(ops)}; got {op!r}")
    return ConditionOp(op)


class ValueType(StrEnum):
    """What an operator compares with, for an editor to offer the right input."""

    NONE = "none"
    NUMBER = "number"
    LIST = "list"
    TEXT = "text"
    PATTERN = "pattern"


def value_type(op: ConditionOp) -> ValueType:
    """What ``op`` takes as its value; ``check_value`` enforces the same."""
    if op in VALUELESS_OPS:
        return ValueType.NONE
    if op in NUMERIC_OPS:
        return ValueType.NUMBER
    if op in (ConditionOp.IN, ConditionOp.NOT_IN):
        return ValueType.LIST
    if op is ConditionOp.MATCHES:
        return ValueType.PATTERN
    return ValueType.TEXT


def check_value(
    op: Any, value: Any, ops: Tuple[ConditionOp, ...] = OPS, portable: bool = True
) -> None:
    """Raise ``ValueError`` when ``op`` is unknown or ``value`` doesn't fit it. ``portable``
    also refuses a pattern Postgres would read differently; a stored rule is built without
    it, so one saved before the check existed still runs."""
    op = known_op(op, ops)
    if op in VALUELESS_OPS:
        if value is not None:
            raise ValueError(f"'{op}' takes no value")
        return
    if value is None:
        raise ValueError(f"'{op}' needs a value")
    if op in NUMERIC_OPS and number(value) is None:
        raise ValueError(f"'{op}' compares with a number; got {value!r}")
    if op in (ConditionOp.IN, ConditionOp.NOT_IN) and (not isinstance(value, list) or not value):
        raise ValueError(f"'{op}' takes a list of at least one value")
    if op is ConditionOp.MATCHES:
        if not isinstance(value, str):
            raise ValueError(f"'{op}' takes a regular expression")
        if len(value) > PATTERN_LIMIT:
            raise ValueError(f"The regular expression is longer than {PATTERN_LIMIT} characters")
        try:
            re.compile(value)
        except re.error as e:
            raise ValueError(f"Invalid regular expression: {e}") from e
        if portable:
            check_portable_pattern(value)


# What each construct that Python and Postgres read differently is, and what to write instead.
_ESCAPES = {
    "b": ("\\b (a word boundary in Python, a backspace in Postgres)", "(^|\\W) or (\\W|$)"),
    "B": ("\\B (not a word boundary)", None),
    "A": ("\\A (start of text)", "^"),
    "Z": ("\\Z (end of text)", "$"),
    "z": ("\\z (end of text)", "$"),
    "G": ("\\G", None),
}
_GROUPS = (
    ("(?P<", "a named group (?P<name>...)", "a plain group (...)"),
    ("(?P=", "a named backreference (?P=name)", None),
    ("(?<=", "a lookbehind (?<=...)", None),
    ("(?<!", "a negative lookbehind (?<!...)", None),
    ("(?<", "a named group (?<name>...)", "a plain group (...)"),
    ("(?>", "an atomic group (?>...)", "a plain group (...)"),
    ("(?#", "a comment (?#...)", None),
)
_INLINE_FLAGS = re.compile(r"\(\?[aiLmsux-]+[:)]")


def check_portable_pattern(pattern: str) -> None:
    """Refuse a pattern that Python and Postgres would read differently, naming the construct
    and what to write instead where there is a portable form."""

    def refuse(construct: str, instead: Optional[str]) -> None:
        hint = f"; write {instead} instead" if instead else ""
        raise ValueError(
            f"The regular expression uses {construct}, which doesn't work the same everywhere "
            f"Rhesis matches patterns{hint}"
        )

    in_class = False
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\" and i + 1 < len(pattern):
            escaped = pattern[i + 1]
            if not in_class and escaped in _ESCAPES:
                refuse(*_ESCAPES[escaped])
            i += 2
            continue
        if in_class:
            if char == "]":
                in_class = False
            i += 1
            continue
        if char == "[":
            in_class = True
            i += 1
            if pattern[i : i + 1] == "^":
                i += 1
            # A ']' right after '[' or '[^' is a literal, not the end of the class.
            if pattern[i : i + 1] == "]":
                i += 1
            continue
        if char == "(" and pattern[i + 1 : i + 2] == "?":
            for prefix, construct, instead in _GROUPS:
                if pattern.startswith(prefix, i):
                    refuse(construct, instead)
            if _INLINE_FLAGS.match(pattern, i):
                refuse(
                    "inline flags such as (?i)",
                    "the letters both ways, such as [Rr]efund",
                )
        if char in "*+?}" and pattern[i + 1 : i + 2] == "+":
            refuse("a possessive quantifier such as a++", "a plain quantifier such as a+")
        i += 1


class Condition(BaseModel):
    """One condition a span must meet to be picked by a target.

    ``field`` is a special field (``SPECIAL_FIELDS``) or any span attribute key; ``op`` one
    of ``CONDITION_OPS``. A span without the field meets only ``!=``, ``not_in`` and
    ``not_exists``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str
    op: ConditionOp
    value: Any = None

    @field_validator("op", mode="before")
    @classmethod
    def _op(cls, op: Any) -> ConditionOp:
        return known_op(op, CONDITION_OPS)

    @field_validator("field")
    @classmethod
    def _field(cls, field: str) -> str:
        if not field or not field.strip():
            raise ValueError("A condition needs a field")
        return field

    @model_validator(mode="after")
    def _value(self) -> "Condition":
        check_value(self.op, self.value, CONDITION_OPS)
        values = self.value if isinstance(self.value, list) else [self.value]
        if self.value is not None and not all(isinstance(v, Scalar) for v in values):
            raise ValueError(
                f"A condition compares with text, numbers or true/false; got {self.value!r}"
            )
        return self

    @classmethod
    def coerce(cls, value: Any) -> "Condition":
        if isinstance(value, Condition):
            return value
        if isinstance(value, (tuple, list)):
            if len(value) not in (2, 3):
                raise ValueError(f"A condition is (field, op) or (field, op, value); got {value!r}")
            return cls(field=value[0], op=value[1], value=value[2] if len(value) == 3 else None)
        return cls.model_validate(value)

    def met_by(self, measured: Any) -> bool:
        """Whether a span whose field reads ``measured`` meets the condition."""
        if measured is None:
            return self.op in MET_WHEN_MISSING
        return compare(self.op, measured, self.value, self.field)


def conditions(values: Any) -> List[Condition]:
    return [Condition.coerce(value) for value in values]
