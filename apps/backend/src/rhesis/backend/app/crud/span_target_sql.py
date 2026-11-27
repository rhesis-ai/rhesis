"""A metric target as SQL: the WHERE clause that keeps exactly the spans it picks.

The spans list appends it to its own clauses, so paging, sorting, counts and facets work as
they do for any other filter. It is the SDK's ``Target.select`` in SQL, and
tests/backend/crud/test_span_target_sql.py holds the two together on the same traces:

- A span target (and a preset, through ``Target.expand``) keeps each span meeting every
  condition and ``within``. A span the response only reported is left out where a recorded
  span of its kind matched in the same trace, as the SDK counts a call once.
- ``turn`` keeps each turn's root span, ``run`` each trace's first root, and ``conversation``
  the first root of each trace the platform judges as a conversation (``Trace.is_conversation``).
  Roots are read from ``trace.is_root``, which ingest keeps.

A condition reads a value as ``conditions.field_value`` does, and compares it as
``conditions.compare`` does: text and numbers compare as the same value, a span without the
value meets only ``!=``, ``not_in`` and ``not_exists``, and text that isn't a finite number
(``"1e999"``) is not a number, rather than an error.

Imports the SDK, so it is imported only once a target is given (a core install has none).
"""

import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, List, Optional, Sequence

from sqlalchemy import (
    Float,
    Numeric,
    Text,
    and_,
    case,
    cast,
    exists,
    false,
    func,
    literal,
    not_,
    or_,
    select,
    true,
    tuple_,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import aliased

from rhesis.backend.app import models
from rhesis.backend.app.constants import REPORTED_SPAN_SOURCE, AISpanAttributes
from rhesis.backend.app.crud.span_sql import (
    same_trace,
    span_is_root_expr,
    span_name_field_expr,
)
from rhesis.backend.app.crud.telemetry import AGENT_PATH_MAX_DEPTH
from rhesis.sdk.entities.trace import FROM_CONVERSATION, TRACE_SOURCE_ATTRIBUTE
from rhesis.sdk.metrics.conditions import (
    ATTRIBUTE_PREFIX,
    MET_WHEN_MISSING,
    NUMBER_TEXT,
    NUMBER_TEXT_LIMIT,
    NUMERIC_OPS,
    REGEX_TEXT_LIMIT,
    Condition,
    ConditionOp,
    SpanStatus,
    SpecialField,
    number,
    text,
)
from rhesis.sdk.metrics.targets import Target, TargetKind
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.constants import ConversationContext

_CONVERSATION_INPUT = ConversationContext.SpanAttributes.CONVERSATION_INPUT
_CONVERSATION_OUTPUT = ConversationContext.SpanAttributes.CONVERSATION_OUTPUT

#: The whitespace ``NUMBER_TEXT`` allows around a number, and all the cast is left to trim:
#: ASCII only, so text the pattern takes is always a numeric Postgres can read.
_NUMBER_SPACE = " \t\n\r\f\v"
#: A float's range: past the largest a number is infinite; below the smallest it is 0.
_FLOAT_MAX = Decimal(repr(sys.float_info.max))
_FLOAT_TINY = Decimal("1e-320")

_JSONB_NUMBER = "number"
_JSONB_STRING = "string"
_JSONB_NULL = "null"
#: JSON values Python reads as false: a turn root needs a conversation input or output that isn't.
_FALSY_JSON = ('""', "0", "false", "[]", "{}", "null")
#: OpenTelemetry's error code, with and without its prefix (``conditions.span_status``).
_ERROR_CODES = (SpanStatus.ERROR.value, f"status_code_{SpanStatus.ERROR.value}")


@dataclass(frozen=True)
class _Field:
    """What a condition reads from a span, as SQL."""

    present: Any
    """True when the span has the value; the other columns are read only then."""
    text: Any
    number: Optional[Any]
    """The value as a finite float, NULL when it isn't one; None for a field never numeric."""
    any_case: bool = False
    """Status compares without regard to case."""


# ---------------------------------------------------------------------------
# Reading a field
# ---------------------------------------------------------------------------


def _as_float(value) -> Any:
    """A numeric as the float Python would read it: NULL past a float's range, 0 below it."""
    size = func.abs(value)
    return case(
        (size > literal(_FLOAT_MAX, Numeric), None),
        (size < literal(_FLOAT_TINY, Numeric), literal(0.0, Float)),
        else_=cast(value, Float),
    )


def _text_number(value) -> Any:
    """Text as a number the way ``conditions.number`` reads it, NULL when it isn't one.

    ``NUMBER_TEXT`` is the SDK's own pattern: ASCII digits, an exponent of at most four
    digits and at most ``NUMBER_TEXT_LIMIT`` characters, so the cast never fails."""
    readable = and_(func.length(value) <= NUMBER_TEXT_LIMIT, value.op("~")(NUMBER_TEXT))
    cleaned = func.btrim(value, _NUMBER_SPACE)
    return case((readable, _as_float(cast(cleaned, Numeric))))


def _number(value: Any) -> Optional[float]:
    """``conditions.number`` of a value the target compares with; an integer too large for a
    float is no number, rather than an ``OverflowError``."""
    try:
        return number(value)
    except (OverflowError, ValueError):
        return None


def _json(trace, key: str) -> Any:
    """The attribute ``key`` as JSONB, NULL when the span hasn't it."""
    return trace.attributes.op("->")(literal(key, Text))


def _json_text(trace, key: str) -> Any:
    return trace.attributes.op("->>", return_type=Text)(literal(key, Text))


def _reported(trace) -> Any:
    source = _json_text(trace, AISpanAttributes.SPAN_SOURCE)
    return func.coalesce(source == REPORTED_SPAN_SOURCE, false())


def _status(trace) -> Any:
    error = func.lower(trace.status_code).in_(_ERROR_CODES)
    return case((error, SpanStatus.ERROR.value), else_=SpanStatus.OK.value)


def _attribute(trace, key: str) -> _Field:
    value = _json(trace, key)
    kind = func.jsonb_typeof(value)
    as_text = _json_text(trace, key)
    number_value = case(
        (kind == _JSONB_NUMBER, _as_float(cast(value, Numeric))),
        (kind == _JSONB_STRING, _text_number(as_text)),
    )
    return _Field(func.coalesce(kind != _JSONB_NULL, false()), as_text, number_value)


def _field(trace, field: str) -> _Field:
    """``targets.field_value`` in SQL. A reported span has no duration or status."""
    if field == SpecialField.KIND:
        return _Field(true(), trace.span_type, _text_number(trace.span_type))
    if field == SpecialField.NAME:
        name = span_name_field_expr(trace)
        return _Field(true(), name, _text_number(name))
    if field == SpecialField.SPAN_NAME:
        return _Field(true(), trace.span_name, _text_number(trace.span_name))
    recorded = not_(_reported(trace))
    if field == SpecialField.DURATION_MS:
        return _Field(recorded, cast(trace.duration_ms, Text), trace.duration_ms)
    if field == SpecialField.STATUS:
        return _Field(recorded, _status(trace), None, any_case=True)
    return _attribute(trace, field.removeprefix(ATTRIBUTE_PREFIX))


# ---------------------------------------------------------------------------
# Comparing it
# ---------------------------------------------------------------------------


def _same_any(field: _Field, values: Sequence[Any]) -> Any:
    """``conditions.same`` with any of ``values``: as numbers when both are, else as text.

    A value that isn't a number compares as text alone, a plain ``IN`` an index can serve.
    Never NULL while the field is present, so it is left bare for the index to match."""
    measured = func.lower(field.text) if field.any_case else field.text

    def as_text(value: Any) -> str:
        return text(value).lower() if field.any_case else text(value)

    words = [as_text(v) for v in values if _number(v) is None]
    clauses = [measured.in_(words)] if words else []
    for value in values:
        wanted = _number(value)
        if wanted is None:
            continue
        if field.number is None:
            clauses.append(measured == as_text(value))
        else:
            clauses.append(
                case(
                    (field.number.isnot(None), field.number == wanted),
                    else_=measured == as_text(value),
                )
            )
    return or_(*clauses)


def _numeric(field: _Field, op: ConditionOp, value: Any) -> Any:
    wanted = _number(value)
    if field.number is None or wanted is None:
        return false()
    compared = {
        ConditionOp.LT: field.number < wanted,
        ConditionOp.LE: field.number <= wanted,
        ConditionOp.GT: field.number > wanted,
        ConditionOp.GE: field.number >= wanted,
    }[op]
    return func.coalesce(compared, false())


def postgres_pattern(pattern: str) -> str:
    """``pattern`` as Postgres reads Python's meaning of it. A portable pattern
    (``conditions.check_portable_pattern``) differs in two places: Python's ``.`` doesn't match
    a newline, and its ``$`` also matches before a final newline."""
    out: List[str] = []
    in_class = False
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\" and i + 1 < len(pattern):
            out.append(pattern[i : i + 2])
            i += 2
            continue
        if in_class:
            in_class = char != "]"
            out.append(char)
            i += 1
            continue
        if char == "[":
            # A ']' right after '[' or '[^' is a literal, not the end of the class.
            start = i + 1 + (pattern[i + 1 : i + 2] == "^")
            end = start + (pattern[start : start + 1] == "]")
            out.append(pattern[i:end])
            in_class, i = True, end
            continue
        out.append({".": r"[^\n]", "$": r"(?=\n?$)"}.get(char, char))
        i += 1
    return "".join(out)


def _compared(field: _Field, condition: Condition) -> Any:
    """``conditions.compare`` for a span that has the value."""
    op, value = condition.op, condition.value
    if op in NUMERIC_OPS:
        return _numeric(field, op, value)
    if op in (ConditionOp.EQ, ConditionOp.NE):
        return _same_any(field, [value])
    if op in (ConditionOp.IN, ConditionOp.NOT_IN):
        return _same_any(field, value)
    if op is ConditionOp.CONTAINS:
        return func.coalesce(func.strpos(field.text, text(value)) > 0, false())
    searched = func.substr(field.text, 1, REGEX_TEXT_LIMIT)
    return func.coalesce(searched.op("~")(postgres_pattern(value)), false())


def condition_clause(trace, condition: Condition) -> Any:
    """``Condition.met_by`` in SQL: a span without the value meets only ``MET_WHEN_MISSING``."""
    field = _field(trace, condition.field)
    if condition.op is ConditionOp.EXISTS:
        return field.present
    if condition.op is ConditionOp.NOT_EXISTS:
        return not_(field.present)
    if condition.op in MET_WHEN_MISSING:
        # The negative operators: the span meets them unless it has the value and it compares.
        return or_(not_(field.present), not_(_compared(field, condition)))
    return and_(field.present, _compared(field, condition))


# ---------------------------------------------------------------------------
# The units of a target
# ---------------------------------------------------------------------------


def _conditions(trace, conditions: Optional[Sequence[Condition]]) -> list:
    return [condition_clause(trace, condition) for condition in conditions or ()]


def _inside_by_walk(trace, agent: str) -> Any:
    """Whether an agent span named ``agent`` is above *trace*, found by walking up its
    parents: for a span whose ``agent_path`` isn't filled yet (``update_agent_paths``)."""
    first = aliased(models.Trace)
    anchor = (
        select(
            first.span_id,
            first.parent_span_id,
            first.span_type,
            span_name_field_expr(first).label("name"),
            literal(1).label("depth"),
        )
        .where(*same_trace(first, trace), first.span_id == trace.parent_span_id)
        .correlate(trace)
    )
    above = anchor.cte("above", recursive=True, nesting=True)
    parent = aliased(models.Trace)
    above = above.union_all(
        select(
            parent.span_id,
            parent.parent_span_id,
            parent.span_type,
            span_name_field_expr(parent),
            above.c.depth + 1,
        ).where(
            *same_trace(parent, trace),
            parent.span_id == above.c.parent_span_id,
            above.c.depth < AGENT_PATH_MAX_DEPTH,
        )
    )
    return exists(
        select(literal(1))
        .select_from(above)
        .where(
            above.c.span_type == AIAttributes.OPERATION_AGENT_INVOKE,
            above.c.name == agent,
        )
    )


def _inside(trace, agent: str) -> Any:
    """``targets._walk``'s agents above the span, read from ``agent_path``; a span stored
    before the column existed walks up instead (``COALESCE`` reads that only for those)."""
    return func.coalesce(trace.agent_path.contains([agent]), _inside_by_walk(trace, agent))


def _picked(trace, target: Target) -> list:
    """The span meets the expanded target's conditions and is inside its agent."""
    clauses = _conditions(trace, target.where)
    if target.within is not None:
        clauses.append(_inside(trace, target.within))
    return clauses


def _span_units(target: Target) -> Any:
    """A span target's units: a reported span drops out where a recorded span of its kind
    matched in the same trace (``targets._spans``)."""
    trace = models.Trace
    target = target.expand()
    twin = aliased(models.Trace)
    recorded_twin = exists().where(
        *same_trace(twin, trace),
        twin.span_type == trace.span_type,
        not_(_reported(twin)),
        *_picked(twin, target),
    )
    return and_(*_picked(trace, target), not_(and_(_reported(trace), recorded_twin)))


def _truthy(value) -> Any:
    falsy = [cast(literal(json), JSONB) for json in _FALSY_JSON]
    return and_(value.isnot(None), value.notin_(falsy))


def _carries_turn(trace) -> Any:
    """A root carrying a conversation input or output is a turn's (``Trace._turn_roots``)."""
    return or_(
        _truthy(_json(trace, _CONVERSATION_INPUT)),
        _truthy(_json(trace, _CONVERSATION_OUTPUT)),
    )


def _turn_roots(trace) -> Any:
    """The trace's other roots that carry a turn, as a subquery's WHERE."""
    other = aliased(models.Trace)
    return other, [*same_trace(other, trace), span_is_root_expr(other), _carries_turn(other)]


def _first_root(trace) -> Any:
    """The trace's first root by start time, which a whole-trace unit shows."""
    earlier = aliased(models.Trace)
    earlier_root = exists().where(
        *same_trace(earlier, trace),
        span_is_root_expr(earlier),
        tuple_(earlier.start_time, earlier.id) < tuple_(trace.start_time, trace.id),
    )
    return and_(span_is_root_expr(trace), not_(earlier_root))


def _turn_units(target: Target) -> Any:
    """Each turn's root, else the first root of a trace without turns, meeting ``where``."""
    trace = models.Trace
    _, any_turn = _turn_roots(trace)
    without_turns = and_(_first_root(trace), not_(exists().where(*any_turn)))
    is_turn = or_(and_(span_is_root_expr(trace), _carries_turn(trace)), without_turns)
    return and_(is_turn, *_conditions(trace, target.where))


def _from_conversation(trace) -> Any:
    source = _json_text(trace, TRACE_SOURCE_ATTRIBUTE)
    return func.coalesce(source == FROM_CONVERSATION, false())


def _conversation_units() -> Any:
    """The first root of each trace ``Trace.is_conversation`` holds a conversation: several
    turns, or a turn marked as built from one."""
    trace = models.Trace
    other, turn = _turn_roots(trace)
    turns = select(func.count()).where(*turn).scalar_subquery()
    marked_turn = exists().where(*turn, _from_conversation(other))
    # Without turns, the first root stands for the one turn.
    marked_root = and_(not_(exists().where(*turn)), _from_conversation(trace))
    return and_(_first_root(trace), or_(turns > 1, marked_turn, marked_root))


def target_clause(target: Target) -> Any:
    """The clause keeping the spans ``target`` picks: the root span of each of its units."""
    if target.on is TargetKind.RUN:
        return _first_root(models.Trace)
    if target.on is TargetKind.CONVERSATION:
        return _conversation_units()
    if target.on is TargetKind.TURN:
        return _turn_units(target)
    return _span_units(target)
