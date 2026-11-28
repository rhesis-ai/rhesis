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
from dataclasses import dataclass
from dataclasses import field as dataclass_field
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

#: Text that reads as a number, here and in the SQL that matches targets in Postgres
#: (``crud/span_target_sql.py``): ASCII digits, an optional fraction and exponent, ASCII
#: whitespace around. Python's ``float()`` also takes ``1_000`` and other scripts' digits,
#: which a Postgres cast refuses, so neither counts. The exponent is capped so the cast can't
#: fail; past it a float is infinite, so not a number anyway.
_DIGITS = "[0-9]+"
_SPACE = "[ \t\n\r\f\v]*"
NUMBER_TEXT = (
    rf"^{_SPACE}[-+]?({_DIGITS}(\.({_DIGITS})?)?|\.{_DIGITS})([eE][-+]?0*[0-9]{{1,4}})?{_SPACE}$"
)
NUMBER_TEXT_LIMIT = 1000
_NUMBER_TEXT = re.compile(NUMBER_TEXT)


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
    """``value`` as a finite float, or None when it isn't one: a bool, text that isn't plain
    ASCII digits (``NUMBER_TEXT``), or a number too large for a float."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            parsed = float(value)
        except OverflowError:
            return None
        return parsed if math.isfinite(parsed) else None
    if isinstance(value, str):
        if len(value) > NUMBER_TEXT_LIMIT or not _NUMBER_TEXT.fullmatch(value):
            return None
        parsed = float(value)
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


#: Operators that compare with one value, never a list.
SINGLE_VALUE_OPS = (ConditionOp.EQ, ConditionOp.NE, ConditionOp.CONTAINS)


def check_value(
    op: Any, value: Any, ops: Tuple[ConditionOp, ...] = OPS, strict: bool = True
) -> None:
    """Raise ``ValueError`` when ``op`` is unknown or ``value`` doesn't fit it. ``strict``
    adds the checks a rule saved before them may fail: a pattern Postgres reads differently,
    an empty list, a list where one value is compared. A stored rule is built without them,
    so it still runs."""
    op = known_op(op, ops)
    if op in VALUELESS_OPS:
        if value is not None:
            raise ValueError(f"'{op}' takes no value")
        return
    if value is None:
        raise ValueError(f"'{op}' needs a value")
    if op in NUMERIC_OPS and number(value) is None:
        raise ValueError(f"'{op}' compares with a number; got {value!r}")
    if op in (ConditionOp.IN, ConditionOp.NOT_IN):
        if not isinstance(value, list):
            raise ValueError(f"'{op}' takes a list of values")
        if strict and not value:
            raise ValueError(f"'{op}' takes a list of at least one value")
    if strict and op in SINGLE_VALUE_OPS and isinstance(value, list):
        raise ValueError(f"'{op}' compares with one value; use 'in' for a list")
    if op is ConditionOp.MATCHES:
        if not isinstance(value, str):
            raise ValueError(f"'{op}' takes a regular expression")
        if len(value) > PATTERN_LIMIT:
            raise ValueError(f"The regular expression is longer than {PATTERN_LIMIT} characters")
        try:
            re.compile(value)
        except re.error as e:
            raise ValueError(f"Invalid regular expression: {e}") from e
        if strict:
            check_portable_pattern(value)
            check_backtracking(value)


# What each construct that Python and Postgres read differently is, and what to write instead.
_ESCAPES = {
    "b": (
        "\\b (a word boundary in Python, a backspace in Postgres)",
        "(^|[^A-Za-z0-9_]) or ([^A-Za-z0-9_]|$)",
    ),
    "B": ("\\B (not a word boundary)", None),
    "A": ("\\A (start of text)", "^"),
    "Z": ("\\Z (end of text)", "$"),
    "z": ("\\z (end of text)", "$"),
    "G": ("\\G", None),
    "N": ("\\N{...} (a character by name)", "the character itself"),
    # Python's classes are Unicode; Postgres's follow the database locale. On Postgres 16 with
    # en_US.utf8, \d is ASCII only, \w takes letters such as é, and \s takes U+2003 but not
    # U+00A0. Python's re.ASCII agrees for \d only, so spell the characters out.
    "d": ("\\d (which digits count differs)", "[0-9]"),
    "D": ("\\D (which digits count differs)", "[^0-9]"),
    "w": ("\\w (which letters count differs)", "[A-Za-z0-9_]"),
    "W": ("\\W (which letters count differs)", "[^A-Za-z0-9_]"),
    "s": ("\\s (which spaces count differs)", "[ \\t\\n\\r\\f\\v]"),
    "S": ("\\S (which spaces count differs)", "[^ \\t\\n\\r\\f\\v]"),
}
#: Escapes that mean the same inside a character class and out.
_CLASS_ESCAPES = ("N", "d", "D", "w", "W", "s", "S")
#: Postgres refuses a repeat count above this.
MAX_REPEAT = 255
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
#: ``{m}``, ``{m,}``, ``{m,n}`` and ``{,n}``: in Python a quantifier; ``{,n}`` is plain text to
#: Postgres.
_BRACES = re.compile(r"\{(\d*)(,(\d*))?\}")
#: Inside a class, Postgres reads these as a POSIX class, a collating element or an
#: equivalence class; Python reads the characters.
_CLASS_SPECIALS = {
    "[:": ("a POSIX class such as [[:alpha:]]", "the characters, such as [A-Za-z]"),
    "[.": ("a collating element such as [[.a.]]", "the character itself"),
    "[=": ("an equivalence class such as [[=e=]]", "the characters, such as [eé]"),
}
_GROUPS = (
    ("(?P<", "a named group (?P<name>...)", "a plain group (...)"),
    ("(?P=", "a named backreference (?P=name)", None),
    ("(?<=", "a lookbehind (?<=...)", None),
    ("(?<!", "a negative lookbehind (?<!...)", None),
    ("(?<", "a named group (?<name>...)", "a plain group (...)"),
    ("(?>", "an atomic group (?>...)", "a plain group (...)"),
    ("(?#", "a comment (?#...)", None),
    ("(?(", "a conditional group (?(1)...|...)", None),
)
_INLINE_FLAGS = re.compile(r"\(\?[aiLmsux-]+[:)]")


def _refuse(construct: str, instead: Optional[str]) -> None:
    hint = f"; write {instead} instead" if instead else ""
    raise ValueError(
        f"The regular expression uses {construct}, which doesn't work the same everywhere "
        f"Rhesis matches patterns{hint}"
    )


def _check_escape(pattern: str, i: int, in_class: bool) -> None:
    escaped = pattern[i + 1]
    if escaped in _ESCAPES and (not in_class or escaped in _CLASS_ESCAPES):
        _refuse(*_ESCAPES[escaped])
    # Python reads two hex digits after \x; Postgres reads every hex digit there is.
    if escaped == "x" and pattern[i + 4 : i + 5] in _HEX_DIGITS and i + 4 < len(pattern):
        _refuse(
            "\\x followed by another hex digit (Postgres reads them all as one code)",
            "the character itself",
        )


def _check_braces(pattern: str, i: int) -> Optional[int]:
    """Check the braces opening at ``i``; where they end when they are a quantifier."""
    braces = _BRACES.match(pattern, i)
    if not braces:
        return None
    lower, upper = braces.group(1), braces.group(3)
    if lower == "" and upper:
        _refuse(f"the quantifier {braces.group()}", f"{{0,{upper}}}")
    if any(int(n) > MAX_REPEAT for n in (lower, upper) if n):
        _refuse(f"the repeat count {braces.group()}", f"a count of at most {MAX_REPEAT}")
    if not lower:
        return None
    end = braces.end()
    if pattern[end : end + 1] == "+":
        _refuse("a possessive quantifier such as a{2}+", "a plain quantifier")
    return end


def _check_group(pattern: str, i: int) -> None:
    for prefix, construct, instead in _GROUPS:
        if pattern.startswith(prefix, i):
            _refuse(construct, instead)
    if _INLINE_FLAGS.match(pattern, i):
        _refuse("inline flags such as (?i)", "the letters both ways, such as [Rr]efund")


def check_portable_pattern(pattern: str) -> None:
    """Refuse a pattern that Python and Postgres would read differently, naming the construct
    and what to write instead where there is a portable form."""
    in_class = False
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\" and i + 1 < len(pattern):
            _check_escape(pattern, i, in_class)
            i += 2
            continue
        if in_class:
            special = _CLASS_SPECIALS.get(pattern[i : i + 2])
            if special:
                _refuse(*special)
            in_class = char != "]"
            i += 1
            continue
        if char == "{":
            end = _check_braces(pattern, i)
            if end is not None:
                i = end
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
            _check_group(pattern, i)
        if char in "*+?" and pattern[i + 1 : i + 2] == "+":
            _refuse("a possessive quantifier such as a++", "a plain quantifier such as a+")
        i += 1


@dataclass
class _Group:
    """What the scan of ``check_backtracking`` knows about an open group."""

    repeats: bool = False
    """Its body repeats something."""
    firsts: List[Optional[str]] = dataclass_field(default_factory=lambda: [None])
    """The first character of each alternative, None when it isn't one literal character."""
    started: bool = False
    """The current alternative has its first atom."""


def _repeat_at(pattern: str, i: int) -> Tuple[bool, int]:
    """Whether a quantifier at ``i`` repeats (allows more than one), and where it ends."""
    char = pattern[i : i + 1]
    if char in ("*", "+"):
        end, repeats = i + 1, True
    elif char == "?":
        end, repeats = i + 1, False
    elif char == "{" and (braces := _BRACES.match(pattern, i)) and braces.group(1):
        upper = braces.group(3)
        end = braces.end()
        repeats = braces.group(2) is not None and (not upper or int(upper) > 1)
        repeats = repeats or int(braces.group(1)) > 1
    else:
        return False, i
    if pattern[end : end + 1] == "?":  # a lazy quantifier repeats the same
        end += 1
    return repeats, end


def check_backtracking(pattern: str) -> None:
    """Refuse a repeated group that can match the same text in many ways, which makes
    Python's backtracking matcher take exponential time on text that almost matches: a group
    repeated with ``*``, ``+`` or ``{m,n}`` whose body repeats something (``(a+)+``), or whose
    alternatives can start with the same character (``(a|ab)*``).

    The check reads the pattern, not what it matches, so it refuses some safe patterns too:
    ``([a-z]+\\.)*com`` can only match one way, because each repeat ends at a dot, but it is
    refused like ``(a+)+``. ``(ab)+``, ``(cat|dog)+`` and ``(\\d{3}-)?\\d{4}`` are kept.
    """
    message = (
        "The regular expression repeats a group that itself repeats, such as (a+)+, which can "
        "take exponential time; repeat the inner part only, or match the parts separately"
    )
    stack = [_Group()]
    i = 0
    while i < len(pattern):
        char, group = pattern[i], stack[-1]
        first: Optional[str] = None
        if char == "(":
            stack.append(_Group())
            i += 2 if pattern[i + 1 : i + 2] == "?" else 1
            # Skip a non-capturing or lookaround group's marker: (?: (?= (?!
            if pattern[i - 1 : i] == "?" and pattern[i : i + 1] in (":", "=", "!"):
                i += 1
            continue
        if char == "|":
            group.firsts.append(None)
            group.started = False
            i += 1
            continue
        if char == ")" and len(stack) > 1:
            inner = stack.pop()
            group = stack[-1]
            repeats, end = _repeat_at(pattern, i + 1)
            known = [f for f in inner.firsts if f is not None]
            overlapping = len(inner.firsts) > 1 and (
                len(known) < len(inner.firsts) or len(set(known)) < len(known)
            )
            if repeats and (inner.repeats or overlapping):
                raise ValueError(message)
            group.repeats = group.repeats or inner.repeats or repeats
            group.started = True
            i = end
            continue
        if char == "\\":
            escaped = pattern[i + 1 : i + 2]
            first = escaped if escaped and not escaped.isalnum() else None
            end = i + 2
        elif char == "[":
            end = _class_end(pattern, i)
        elif char == "." or char in "^$":
            end = i + 1
        else:
            first, end = char, i + 1
        if not group.started and char not in "^$":
            group.firsts[-1] = first
            group.started = True
        repeats, end = _repeat_at(pattern, end)
        group.repeats = group.repeats or repeats
        i = end


def _class_end(pattern: str, i: int) -> int:
    """Where the character class opening at ``i`` ends."""
    i += 1
    if pattern[i : i + 1] == "^":
        i += 1
    if pattern[i : i + 1] == "]":
        i += 1
    while i < len(pattern) and pattern[i] != "]":
        i += 2 if pattern[i] == "\\" else 1
    return i + 1


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

    def __init__(self, *args: Any, **data: Any) -> None:
        """``Condition(field, op, value=None)``, or the same by name."""
        if len(args) > 3:
            raise TypeError("Condition takes field, op and value")
        data.update(zip(("field", "op", "value")[: len(args)], args, strict=True))
        super().__init__(**data)

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
            return cls(*value)
        return cls.model_validate(value)

    def met_by(self, measured: Any) -> bool:
        """Whether a span whose field reads ``measured`` meets the condition."""
        if measured is None:
            return self.op in MET_WHEN_MISSING
        return compare(self.op, measured, self.value, self.field)


def conditions(values: Any) -> List[Condition]:
    return [Condition.coerce(value) for value in values]
