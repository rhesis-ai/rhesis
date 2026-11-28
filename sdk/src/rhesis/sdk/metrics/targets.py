"""What a metric judges in a trace: its target.

A target picks units from the trace: each turn, the conversation, the whole run, or each span
of one kind (each tool call, each retrieval, ...). Every unit is itself a trace, the selected
span and everything under it. The metric runs once per unit, and the verdicts of several units
combine into one. ``TARGETS`` is the one list of choices; validation, the MCP tools and the
docs read it.

    judge.evaluate(trace=trace, target={"on": "tool_call", "name": "issue_refund"})
"""

import inspect
import json
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rhesis.sdk.entities.trace import (
    _REPORTED,
    _SPAN_SOURCE,
    TRACE_SOURCE_ATTRIBUTE,
    Span,
    Trace,
    _documents,
)
from rhesis.sdk.metrics.arguments import judged_input_output, judging_unit
from rhesis.sdk.metrics.base import MetricResult, ThresholdOperator
from rhesis.sdk.metrics.conditions import (
    ATTRIBUTE_PREFIX,
    CHOICE_OPS,
    SPECIAL_FIELDS,
    Condition,
    ConditionOp,
    SpecialField,
    span_status,
)
from rhesis.sdk.metrics.constants import THRESHOLD_OPERATOR_MAP
from rhesis.sdk.metrics.expectations import Expectations
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.constants import ConversationContext

#: At most this many spans are judged per metric; the rest are counted, not judged.
MAX_JUDGED_SPANS = 25
#: Spans one metric judges at the same time, so a judge doesn't send 25 model calls at once.
MAX_CONCURRENT_SPANS = 5
#: Latest traces ``Target.preview`` tries a target on unless told otherwise.
PREVIEW_TRACES = 50


class JudgedParam(StrEnum):
    """Parameters of a metric's ``evaluate`` that say what it judges."""

    INPUT = "input"
    OUTPUT = "output"
    TRACE = "trace"
    EXPECTATIONS = "expectations"


#: A metric reading either of these judges one unit's input and output.
READS_INPUT_OUTPUT = frozenset({JudgedParam.INPUT, JudgedParam.OUTPUT})


class ExpectationName(StrEnum):
    """Fields of ``Expectations`` a target decides about."""

    RESPONSE = "response"
    TOOL_CALLS = "tool_calls"
    TOOL_CALLS_PER_TURN = "tool_calls_per_turn"


class ResultKey(StrEnum):
    """Keys of a target result's details, and of each judged span's row in them."""

    IS_SUCCESSFUL = "is_successful"
    NOT_APPLICABLE = "not_applicable"
    INCONCLUSIVE = "inconclusive"
    REASON = "reason"
    TARGET = "target"
    MATCHED = "matched"
    PASSED = "passed"
    SPANS = "spans"
    SPAN_ID = "span_id"
    NAME = "name"
    SCORE = "score"


#: Keys of a span event as stored on a span.
EVENT_NAME_KEY = "name"
EVENT_ATTRIBUTES_KEY = "attributes"


class TargetKind(str, Enum):
    TURN = "turn"
    CONVERSATION = "conversation"
    RUN = "run"
    TOOL_CALL = "tool_call"
    RETRIEVAL = "retrieval"
    MODEL_CALL = "model_call"
    AGENT = "agent"
    GUARDRAIL = "guardrail"
    SPAN = "span"
    """Each span its conditions pick: the presets are short forms of it."""


class Aggregation(str, Enum):
    """How the verdicts of several spans make the metric's verdict."""

    ALL = "all"
    """Every span passes. The score is the worst span's."""
    ANY = "any"
    """At least one span passes. The score is the best span's."""
    SHARE = "share"
    """At least ``min_share`` of the spans pass. The score is the share that passed."""


@dataclass(frozen=True)
class TargetPreset:
    label: str
    description: str
    span_kind: Optional[str] = None
    """The spans judged one by one; None for a target judged once."""
    noun: Tuple[str, str] = ("", "")
    """Singular and plural, for reasons ("2 of 3 tool calls passed")."""
    hint: str = "Send traces from the endpoint."
    """How an endpoint that reports none of these spans can report them."""


NAME_KEYS = (AIAttributes.TOOL_NAME, AIAttributes.AGENT_NAME, AIAttributes.MODEL_NAME)
"""The attributes holding a span's name, ahead of its span name."""

TARGETS: Dict[TargetKind, TargetPreset] = {
    TargetKind.TURN: TargetPreset(
        "Each turn",
        "Each exchange: the test's one response, or every turn of a conversation.",
        noun=("turn", "turns"),
    ),
    TargetKind.CONVERSATION: TargetPreset(
        "The conversation", "The whole conversation, judged once."
    ),
    TargetKind.RUN: TargetPreset(
        "The whole run", "The whole trace, judged once, for metrics that read the trace."
    ),
    TargetKind.TOOL_CALL: TargetPreset(
        "Each tool call",
        "Every tool call: its arguments as input, its result as output.",
        span_kind=AIAttributes.OPERATION_TOOL_INVOKE,
        noun=("tool call", "tool calls"),
        hint="If the endpoint makes them, map tool_calls in its response or send traces.",
    ),
    TargetKind.RETRIEVAL: TargetPreset(
        "Each retrieval",
        "Every retrieval: its query as input, the documents it found as output.",
        span_kind=AIAttributes.OPERATION_RETRIEVAL,
        noun=("retrieval", "retrievals"),
        hint="If the endpoint retrieves documents, map context in its response or send traces.",
    ),
    TargetKind.MODEL_CALL: TargetPreset(
        "Each model call",
        "Every call to a model: its prompt as input, its completion as output.",
        span_kind=AIAttributes.OPERATION_LLM_INVOKE,
        noun=("model call", "model calls"),
    ),
    TargetKind.AGENT: TargetPreset(
        "Each agent",
        "Every agent run: its task as input, its final answer as output.",
        span_kind=AIAttributes.OPERATION_AGENT_INVOKE,
        noun=("agent run", "agent runs"),
    ),
    TargetKind.GUARDRAIL: TargetPreset(
        "Each guardrail check",
        "Every guardrail check: what it checked as input, its decision as output.",
        span_kind=AIAttributes.OPERATION_GUARDRAIL,
        noun=("guardrail check", "guardrail checks"),
    ),
}
"""The presets, the targets offered as choices. ``span`` is not one: it is what they are
short forms of, and it is written with conditions (``Target.spans``)."""

#: ``on: "span"``, which no preset stands for.
SPAN_TARGET = TargetPreset(
    "Custom spans",
    "Every span that meets the target's conditions: its input and output as its kind "
    "reads them, unless the target says what to read.",
    noun=("span", "spans"),
)

#: Expectations about the whole test, which no single span or turn is held to.
WHOLE_TEST_EXPECTATIONS = (ExpectationName.RESPONSE, ExpectationName.TOOL_CALLS)

#: Targets judged once per matching unit rather than once in all.
PER_UNIT = frozenset(kind for kind, preset in TARGETS.items() if preset.span_kind) | {
    TargetKind.TURN,
    TargetKind.SPAN,
}
#: Targets that judge spans one by one: every per-unit target but the turn.
PER_SPAN = PER_UNIT - {TargetKind.TURN}


#: The key that says what a target judges: ``{"on": "tool_call"}``.
ON = "on"


class Refinement(StrEnum):
    """The fields that narrow which units a per-unit target judges, or what it reads."""

    NAME = "name"
    WITHIN = "within"
    WHERE = "where"
    READ = "read"


REFINEMENTS = tuple(Refinement)


class Reader(StrEnum):
    """What ``read`` may name besides an attribute key or an event: the span's own input or
    output, or the turn's."""

    INPUT = "input"
    OUTPUT = "output"
    CONVERSATION_INPUT = "conversation.input"
    CONVERSATION_OUTPUT = "conversation.output"


READERS = tuple(Reader)
#: Each reader in words. The turn's input and output come from the root span of the turn the
#: unit belongs to, however deep it sits.
READER_LABELS = {
    Reader.INPUT: "Its own input",
    Reader.OUTPUT: "Its own output",
    Reader.CONVERSATION_INPUT: "The turn's input",
    Reader.CONVERSATION_OUTPUT: "The turn's output",
}
#: ``read`` naming an event's value: ``event:ai.retrieval.query``.
EVENT_READER = "event:"


_CONVERSATION_INPUT = ConversationContext.SpanAttributes.CONVERSATION_INPUT
_CONVERSATION_OUTPUT = ConversationContext.SpanAttributes.CONVERSATION_OUTPUT


def preset_of(kind: TargetKind) -> TargetPreset:
    return TARGETS.get(kind, SPAN_TARGET)


class UnsupportedTarget(ValueError):
    """A target this SDK can't read: unknown, or written by a newer Rhesis version.
    ``reason`` says what is wrong without the advice to upgrade."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(
            f"{reason}. If the metric was made with a newer Rhesis version, this metric's "
            "target needs a newer rhesis-sdk: upgrade it."
        )


def _check_supported(value: Dict[str, Any]) -> None:
    """Refuse a target in a shape this SDK doesn't know, saying so instead of failing
    validation: a metric made with a newer Rhesis version can carry one."""
    kinds = [kind.value for kind in TargetKind]
    on = value.get(ON)
    if on not in kinds:
        raise UnsupportedTarget(f"'{on}' is not a target; valid targets: {', '.join(kinds)}")
    unknown = sorted(set(value) - set(Target.model_fields))
    if unknown:
        raise UnsupportedTarget(f"A target has no {', '.join(unknown)}")


class Read(BaseModel):
    """What a per-unit target hands the metric as ``input`` and ``output``: an attribute key,
    one of ``READERS``, or ``event:<name>``. Either left out keeps the kind's own."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input: Optional[str] = Field(default=None, min_length=1)
    output: Optional[str] = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _either(self) -> "Read":
        if self.input is None and self.output is None:
            raise ValueError("read names an input, an output or both")
        for reader in (self.input, self.output):
            if reader is not None and reader.startswith(EVENT_READER):
                if len(reader) == len(EVENT_READER):
                    raise ValueError("event: needs an event name, such as event:ai.retrieval.query")
        return self

    @classmethod
    def coerce(cls, value: Any) -> Optional["Read"]:
        if value is None or isinstance(value, Read):
            return value
        if isinstance(value, (tuple, list)):
            if len(value) != 2:
                raise ValueError("read is (input, output); use None for one left as it is")
            return cls(input=value[0], output=value[1])
        return cls.model_validate(value)


def span_kind_value(value: Any) -> Any:
    """A kind written as a target name (``tool_call``) as the span kind it stands for."""
    if isinstance(value, list):
        return [span_kind_value(item) for item in value]
    try:
        preset = TARGETS.get(TargetKind(value))
    except ValueError:
        return value
    return preset.span_kind if preset is not None and preset.span_kind else value


#: Operators whose value is a kind, which may be written as a target name (``tool_call``).
#: A pattern or a substring stays as written.
_KIND_VALUE_OPS = (ConditionOp.EQ, ConditionOp.NE, ConditionOp.IN, ConditionOp.NOT_IN)


def _normalised_where(where: Any) -> Any:
    """``where`` as a list of conditions. The older form, attribute values by key (a list
    means any of its values), is read as ``==`` and ``in``."""
    if where is None or where == {}:
        # The older form allowed an empty dict: it narrowed nothing.
        return None
    if not isinstance(where, (dict, list, tuple)):
        raise ValueError(
            f"where is a list of conditions, or attribute values by key; got {type(where).__name__}"
        )
    if isinstance(where, dict):
        # The keys are attribute keys; one named like a special field reads the attribute.
        where = [
            Condition(
                field=f"{ATTRIBUTE_PREFIX}{key}" if key in SPECIAL_FIELDS else key,
                op=ConditionOp.IN if isinstance(value, list) else ConditionOp.EQ,
                value=value,
            )
            for key, value in where.items()
        ]
    conditions = []
    for item in where:
        condition = Condition.coerce(item)
        if condition.field == SpecialField.KIND and condition.op in _KIND_VALUE_OPS:
            condition = condition.model_copy(update={"value": span_kind_value(condition.value)})
        conditions.append(condition)
    return conditions


class Target(BaseModel):
    """What a metric judges.

    ``on`` picks the kind of unit. ``name`` and ``within`` narrow a preset's spans; ``where``
    holds conditions every unit's root span must meet; ``read`` says what a unit hands the
    metric. ``on: "span"`` judges every span its conditions pick:

        Target.spans(kind="tool_call", where=[("ai.tool.name", "in", ["a", "b"])])
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    on: TargetKind
    name: Optional[str] = Field(default=None, min_length=1)
    """Only spans with this name: the tool, the agent, the model, or the span's name."""
    within: Optional[str] = Field(default=None, min_length=1)
    """Only spans inside the agent with this name."""
    where: Optional[List[Condition]] = None
    """Conditions the unit's root span must meet, all of them."""
    read: Optional[Read] = None
    aggregate: Aggregation = Aggregation.ALL
    min_share: Optional[float] = Field(default=None, gt=0, le=1)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if Refinement.WHERE in data:
                data[Refinement.WHERE] = _normalised_where(data[Refinement.WHERE])
            if Refinement.READ in data:
                data[Refinement.READ] = Read.coerce(data[Refinement.READ])
        return data

    @model_validator(mode="after")
    def _check(self) -> "Target":
        if self.on is not TargetKind.SPAN and self.where is not None and not self.where:
            raise ValueError("where needs at least one condition; leave it out to keep every unit")
        if self.on is TargetKind.SPAN:
            if self.name is not None:
                raise ValueError(
                    "name doesn't narrow a span target; add a condition on name instead"
                )
            if not self.where:
                raise ValueError(
                    "A span target needs conditions; to judge the whole trace, use 'run'"
                )
        elif self.on not in PER_SPAN:
            narrowed = [
                f for f in (Refinement.NAME, Refinement.WITHIN) if getattr(self, f) is not None
            ]
            if narrowed:
                raise ValueError(
                    f"{' and '.join(narrowed)} only narrow a per-span target, not '{self.on.value}'"
                )
        if self.on not in PER_UNIT:
            for field in (Refinement.WHERE, Refinement.READ):
                if getattr(self, field) is not None:
                    raise ValueError(
                        f"{field} is for a target with several units, and '{self.on.value}' has one"
                    )
        if self.on not in PER_UNIT and self.aggregate is not Aggregation.ALL:
            raise ValueError(f"aggregate combines several verdicts, and '{self.on.value}' has one")
        if (self.aggregate is Aggregation.SHARE) != (self.min_share is not None):
            raise ValueError("min_share goes with aggregate 'share', and only with it")
        return self

    @classmethod
    def coerce(cls, value: Union["Target", TargetKind, str, Dict[str, Any], None]) -> "Target":
        if isinstance(value, Target) or value is None:
            return value
        if isinstance(value, (str, TargetKind)):
            _check_supported({ON: getattr(value, "value", value)})
            return cls(on=value)
        if isinstance(value, dict):
            _check_supported(value)
        return cls.model_validate(value)

    @classmethod
    def spans(
        cls,
        kind: Optional[Union[str, Sequence[str]]] = None,
        name: Optional[Union[str, Sequence[str]]] = None,
        where: Sequence[Any] = (),
        within: Optional[str] = None,
        read: Any = None,
        aggregate: Union[Aggregation, str] = Aggregation.ALL,
        min_share: Optional[float] = None,
    ) -> "Target":
        """A span target from its parts. ``kind`` is a span kind (``tool.invoke``) or a
        preset's name (``tool_call``), and ``name`` the tool, agent or model name; a list of
        either means any of them. ``where`` items are ``Condition`` objects or
        ``(field, op, value)`` tuples; ``read`` is ``(input, output)`` or a dict."""
        conditions: List[Any] = []
        for field, value in ((SpecialField.KIND, kind), (SpecialField.NAME, name)):
            if value is None:
                continue
            many = not isinstance(value, str)
            op = ConditionOp.IN if many else ConditionOp.EQ
            conditions.append(Condition(field=field, op=op, value=list(value) if many else value))
        conditions.extend(where)
        return cls(
            on=TargetKind.SPAN,
            where=conditions or None,
            within=within,
            read=read,
            aggregate=aggregate,
            min_share=min_share,
        )

    @property
    def preset(self) -> TargetPreset:
        return preset_of(self.on)

    def to_config(self) -> Dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True, exclude_defaults=True)

    @property
    def is_bare(self) -> bool:
        """Whether the target is only its kind, with no refinement or pass rule."""
        return self.to_config() == Target.model_construct(on=self.on).to_config()

    def expand(self) -> "Target":
        """This target written as a span target, when it judges spans: a preset becomes its
        kind and name as conditions. Matching uses this form, so a preset and the span target
        it stands for pick the same spans. Turns, the conversation and the run stay as they
        are."""
        if self.on not in PER_SPAN or self.on is TargetKind.SPAN:
            return self
        conditions = [
            Condition(field=SpecialField.KIND, op=ConditionOp.EQ, value=self.preset.span_kind)
        ]
        if self.name is not None:
            conditions.append(
                Condition(field=SpecialField.NAME, op=ConditionOp.EQ, value=self.name)
            )
        conditions.extend(self.where or ())
        return Target(
            on=TargetKind.SPAN,
            where=conditions,
            within=self.within,
            read=self.read,
            aggregate=self.aggregate,
            min_share=self.min_share,
        )

    def describe(self, short: bool = False) -> str:
        """What the target picks, in words: "each tool call named `issue_refund` inside
        `billing_agent`". ``short`` lists only the first condition beyond kind, name and
        agent, and counts the rest."""
        return _phrase(self, plural=False, short=short)

    def select(self, trace: Trace) -> List["Unit"]:
        """The units this target picks from ``trace``, as the platform judges them."""
        return matching_units(trace, self)

    def preview(self, project: Any, traces: int = PREVIEW_TRACES) -> Dict[str, Any]:
        """What this target picks in ``project``'s latest ``traces`` traces, matched on the
        platform as evaluation matches it: how many traces and units match, and samples.
        ``project`` is a ``Project`` or its id."""
        from rhesis.sdk.clients import APIClient, Endpoints, Methods

        project_id = getattr(project, "id", project)
        if not project_id:
            raise ValueError("preview needs a project with an id; pull or push it first")
        body = {"project_id": str(project_id), "target": self.to_config(), "traces": traces}
        return APIClient().send_request(
            endpoint=Endpoints.METRIC_TARGET_PREVIEW, method=Methods.POST, data=body
        )


# ---------------------------------------------------------------------------
# The target in words
# ---------------------------------------------------------------------------


_OP_WORDS = {
    ConditionOp.EQ: "is",
    ConditionOp.NE: "is not",
    ConditionOp.LT: "is under",
    ConditionOp.LE: "is at most",
    ConditionOp.GT: "is over",
    ConditionOp.GE: "is at least",
    ConditionOp.CONTAINS: "contains",
    ConditionOp.MATCHES: "matches",
}


def _code(value: Any) -> str:
    return f"`{value if isinstance(value, str) else json.dumps(value, default=str)}`"


def _either(values: Sequence[Any], joiner: str = "or") -> str:
    shown = [_code(value) for value in values]
    if len(shown) == 1:
        return shown[0]
    return f"{', '.join(shown[:-1])} {joiner} {shown[-1]}"


def _condition_words(condition: Condition) -> str:
    field = _code(condition.field)
    op, value = condition.op, condition.value
    if op is ConditionOp.EXISTS:
        return f"{field} is set"
    if op is ConditionOp.NOT_EXISTS:
        return f"{field} is not set"
    if op is ConditionOp.IN:
        return f"{field} is {_either(value)}"
    if op is ConditionOp.NOT_IN:
        return (
            f"{field} is neither {_either(value, 'nor')}"
            if len(value) > 1
            else (f"{field} is not {_code(value[0])}")
        )
    return f"{field} {_OP_WORDS[op]} {_code(value)}"


# The name attribute a kind's own spans carry, read as "named …" in a description.
_OWN_NAME_KEY = {
    AIAttributes.OPERATION_TOOL_INVOKE: AIAttributes.TOOL_NAME,
    AIAttributes.OPERATION_AGENT_INVOKE: AIAttributes.AGENT_NAME,
    AIAttributes.OPERATION_LLM_INVOKE: AIAttributes.MODEL_NAME,
}


def _kind_noun(kinds: Sequence[Any], plural: bool) -> Optional[str]:
    """The noun for spans of these kinds ("tool call"), when they are all one preset's."""
    nouns = {
        preset.noun[1 if plural else 0]
        for preset in TARGETS.values()
        if preset.span_kind is not None and preset.span_kind in kinds
    }
    known = all(any(p.span_kind == kind for p in TARGETS.values()) for kind in kinds)
    return nouns.pop() if known and len(nouns) == 1 else None


def _phrase(target: Target, plural: bool, short: bool, each: bool = True) -> str:
    if target.on is TargetKind.CONVERSATION:
        return "the conversation"
    if target.on is TargetKind.RUN:
        return "the whole run"
    expanded = target.expand()
    kinds = None
    if target.on is TargetKind.TURN:
        noun, rest = ("turns" if plural else "turn"), list(expanded.where or ())
    else:
        rest = list(expanded.where or ())
        kinds = _taken(rest, SpecialField.KIND)
        noun = _kind_noun(kinds, plural) if kinds is not None else None
        if noun is None:
            if kinds is not None:
                rest.insert(
                    0, Condition(field=SpecialField.KIND, op=ConditionOp.IN, value=list(kinds))
                )
            noun = "spans" if plural else "span"
    parts = [noun if plural or not each else f"each {noun}"]
    names = _taken(rest, SpecialField.NAME)
    own_key = _OWN_NAME_KEY.get(kinds[0]) if kinds and len(kinds) == 1 else None
    if names is None and own_key is not None:
        names = _taken(rest, own_key)
    if names is not None:
        parts.append(f"named {_either(names)}")
    if expanded.within:
        parts.append(f"inside {_code(expanded.within)}")
    phrase = " ".join(parts)
    if not rest:
        return phrase
    shown, hidden = (rest[:1], len(rest) - 1) if short else (rest, 0)
    joiner = ", where " if len(parts) > 1 else " where "
    phrase += joiner + " and ".join(_condition_words(c) for c in shown)
    if hidden:
        phrase += f", and {hidden} more condition{'s' if hidden > 1 else ''}"
    return phrase


def _taken(conditions: List[Condition], field: str) -> Optional[List[Any]]:
    """The values of the first ``==`` or ``in`` condition on ``field``, taken out of
    ``conditions``; None when there is none."""
    for index, condition in enumerate(conditions):
        if condition.field == field and condition.op in CHOICE_OPS:
            del conditions[index]
            value = condition.value
            return list(value) if isinstance(value, list) else [value]
    return None


# ---------------------------------------------------------------------------
# Which targets a metric can take
# ---------------------------------------------------------------------------


def _named(method: Any) -> frozenset:
    if method is None:
        return frozenset()
    parameters = inspect.signature(method).parameters.values()
    variadic = (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    return frozenset(p.name for p in parameters if p.kind not in variadic) - {"self"}


def _declared(metric: Any, method: str = "evaluate") -> frozenset:
    """What the metric's ``evaluate`` (or ``a_evaluate``) reads. An ``a_evaluate`` that only
    passes its arguments on reads what ``evaluate`` does."""
    named = _named(getattr(metric, method, None))
    return named or _named(getattr(metric, "evaluate", None))


def _conversational(metric: Any) -> bool:
    from rhesis.sdk.metrics.conversational.base import ConversationalMetricBase

    cls = metric if inspect.isclass(metric) else type(metric)
    return issubclass(cls, ConversationalMetricBase)


def targets_for(
    declared: Sequence[str], conversational: bool = False, compares: Sequence[str] = ()
) -> List[TargetKind]:
    """The targets a metric can take, from the parameters its ``evaluate`` declares.

    A metric reading ``input`` or ``output`` judges a turn or any span. One reading ``trace``
    can take every target, since every unit is a trace: a span and what's under it, a turn,
    the conversation or the whole run. A conversational metric judges conversations.
    ``compares`` lists the expectations the metric compares with: one that describes the
    whole test (``response``, ``tool_calls``) can't be held against a span. A turn is held
    to its own expected tool calls (``unit_expectations``). A conversation has no expected
    response, so a metric comparing with one can't judge it.
    """
    if conversational:
        return [TargetKind.CONVERSATION, TargetKind.RUN]
    declared = set(declared)
    kinds: List[TargetKind] = []
    if declared & READS_INPUT_OUTPUT:
        kinds += [kind for kind in TargetKind if kind in PER_UNIT]
    if JudgedParam.TRACE in declared:
        kinds += [TargetKind.CONVERSATION, TargetKind.RUN]
        if TargetKind.TURN not in kinds:
            kinds.insert(0, TargetKind.TURN)
        kinds += [kind for kind in TargetKind if kind in PER_UNIT and kind not in kinds]
    if set(compares) & set(WHOLE_TEST_EXPECTATIONS):
        kinds = [kind for kind in kinds if kind not in PER_SPAN]
    if ExpectationName.RESPONSE in compares:
        kinds = [kind for kind in kinds if kind is not TargetKind.CONVERSATION]
    return kinds


def _compares(metric: Any) -> List[str]:
    compares = list(getattr(metric, "REQUIRED_EXPECTATIONS", ()))
    # An instance's setting, or a class that always compares with one (DeepEval's recall).
    if getattr(metric, "requires_ground_truth", False) is True:
        compares.append(ExpectationName.RESPONSE)
    return compares


def supported_targets(metric: Any, compares: Sequence[str] = ()) -> List[TargetKind]:
    """The targets a metric (class or instance) can take; see ``targets_for``. ``compares``
    adds expectations its settings compare with, such as a required reference answer."""
    compared = [*_compares(metric), *compares]
    return targets_for(_declared(metric), _conversational(metric), compared)


def default_target(metric: Any) -> Optional[TargetKind]:
    """The target a metric takes when none is chosen, or None when it must be chosen."""
    if _conversational(metric):
        return TargetKind.CONVERSATION
    declared = _declared(metric)
    if declared & READS_INPUT_OUTPUT:
        return TargetKind.TURN
    if JudgedParam.TRACE in declared:
        return TargetKind.RUN
    return None


def check_target(
    metric: Any,
    target: Union[Target, Dict[str, Any], str],
    supported: Optional[Sequence[TargetKind]] = None,
) -> Target:
    """``target`` as a Target, or a ValueError naming the targets the metric can take.

    ``supported`` replaces what is read from ``metric``, for a metric known only by the
    parameters it declares (an SDK metric served through the connector)."""
    target = Target.coerce(target)
    if supported is None:
        supported = supported_targets(metric)
    if supported and target.on not in supported:
        choices = ", ".join(f"{preset_of(k).label} ({k.value})" for k in supported)
        raise ValueError(f"This metric can't judge '{target.on.value}'. Choices: {choices}.")
    return target


# ---------------------------------------------------------------------------
# What a target matches in a trace
# ---------------------------------------------------------------------------


@dataclass
class Unit:
    """One thing a target judges, as a trace: the selected span and everything under it.

    ``input`` and ``output`` are read from its root span. A unit of the whole trace (the
    conversation, the run) has no ``span``, and its input and output are read from the trace
    only when a metric asks for them."""

    span: Optional[Span]
    input: Optional[str]
    output: Optional[str]
    trace: Trace
    name: Optional[str]
    turn: Optional[int] = None
    """For a turn: its place in the conversation, 0 for the first."""
    turns: Optional[int] = None
    """For a turn: how many turns the conversation has."""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value, default=str)


def _name(span: Span) -> Optional[str]:
    attributes = span.attributes
    for key in NAME_KEYS:
        value = attributes.get(key)
        if isinstance(value, str) and value:
            return value
    return span.span_name


def _walk(spans: Sequence[Span], agents: Tuple[str, ...] = ()):
    """Each span with the names of the agents it runs inside, depth first."""
    for span in spans:
        yield span, agents
        is_agent = span.kind == AIAttributes.OPERATION_AGENT_INVOKE
        inner = agents + (_name(span) or "",) if is_agent else agents
        yield from _walk(span.children, inner)


def _turn_input(root: Span) -> Any:
    return root.attributes.get(_CONVERSATION_INPUT) or root.input


def _reported(span: Span) -> bool:
    return span.attributes.get(_SPAN_SOURCE) == _REPORTED


def _subtree(trace: Trace, span: Span) -> Trace:
    """``span`` and everything under it, as a trace of its own. A turn of a conversation is
    judged as a turn, not as a conversation."""
    attributes = {k: v for k, v in span.attributes.items() if k != TRACE_SOURCE_ATTRIBUTE}
    unit = Trace(
        trace_id=trace.trace_id,
        conversation_id=trace.conversation_id,
        root_spans=[span.model_copy(update={"attributes": attributes})],
    )
    unit._detail_loaded = True
    return unit


def field_value(span: Span, field: str) -> Any:
    """What a condition on ``field`` reads from ``span``; None when the span hasn't it. A
    reported span carries no timing or status."""
    if field == SpecialField.KIND:
        return span.kind
    if field == SpecialField.NAME:
        return _name(span)
    if field == SpecialField.SPAN_NAME:
        return span.span_name
    if field == SpecialField.DURATION_MS:
        return None if _reported(span) else span.duration_ms
    if field == SpecialField.STATUS:
        return None if _reported(span) else span_status(span.status_code).value
    if field.startswith(ATTRIBUTE_PREFIX):
        return span.attributes.get(field[len(ATTRIBUTE_PREFIX) :])
    return span.attributes.get(field)


def _meets(span: Span, conditions: Optional[Sequence[Condition]]) -> bool:
    return all(c.met_by(field_value(span, c.field)) for c in conditions or ())


def _event_value(span: Span, name: str) -> Any:
    for event in span.events:
        if isinstance(event, dict) and event.get(EVENT_NAME_KEY) == name:
            attributes = event.get(EVENT_ATTRIBUTES_KEY) or {}
            if len(attributes) == 1:
                return next(iter(attributes.values()))
            return attributes or None
    return None


#: The turn's attribute each conversation reader names.
_TURN_KEYS = {
    Reader.CONVERSATION_INPUT: _CONVERSATION_INPUT,
    Reader.CONVERSATION_OUTPUT: _CONVERSATION_OUTPUT,
}


def _read_value(
    span: Span, reader: Optional[str], default: Any, own: Tuple[Any, Any], turn: Span
) -> Any:
    """What ``reader`` names on ``span``; ``default`` when the target reads nothing else.
    ``own`` is the unit's input and output as its kind reads them. The conversation readers
    read ``turn``, the root span the unit belongs to: its conversation attribute, else its own
    input or output, else the span's attribute."""
    if reader is None:
        return default
    if reader == Reader.INPUT:
        return own[0]
    if reader == Reader.OUTPUT:
        return own[1]
    if reader in _TURN_KEYS:
        reader = Reader(reader)
        key = _TURN_KEYS[reader]
        for value in (
            turn.attributes.get(key),
            turn.input if reader is Reader.CONVERSATION_INPUT else turn.output,
        ):
            if value not in (None, ""):
                return value
        return span.attributes.get(key)
    if reader.startswith(EVENT_READER):
        return _event_value(span, reader[len(EVENT_READER) :])
    return span.attributes.get(reader)


def _unit(
    span: Span,
    root: Span,
    input: Any,
    output: Any,
    target: Target,
    trace: Trace,
    **turn: Any,
) -> Unit:
    """One unit from ``span``; ``root`` is the root span of the turn it belongs to."""
    read = target.read
    if read is not None:
        own = (input, output)
        input = _read_value(span, read.input, input, own, root)
        output = _read_value(span, read.output, output, own, root)
    return Unit(
        span, _text(input), _text(output), _subtree(trace, span), turn.pop(ResultKey.NAME), **turn
    )


def _turns(trace: Trace, target: Target) -> List[Unit]:
    units = []
    roots = trace._turn_roots()
    for turn, root in enumerate(roots):
        if not _meets(root, target.where):
            continue
        user = _turn_input(root)
        reply = root.attributes.get(_CONVERSATION_OUTPUT) or root.output
        units.append(
            _unit(root, root, user, reply, target, trace, name=None, turn=turn, turns=len(roots))
        )
    return units


def _spans(trace: Trace, target: Target) -> List[Unit]:
    # Presets match as the span targets they stand for, so the two can't drift apart.
    target = target.expand()
    found = [
        (span, root)
        for root in trace.root_spans
        for span, agents in _walk([root])
        if (target.within is None or target.within in agents) and _meets(span, target.where)
    ]
    # A call the endpoint both recorded and reported counts once: where a kind was recorded,
    # its reported spans are left out.
    recorded = {span.kind for span, _ in found if not _reported(span)}
    units = []
    for span, root in found:
        if _reported(span) and span.kind in recorded:
            continue
        input, output = span.input, span.output
        if span.kind == AIAttributes.OPERATION_RETRIEVAL:
            output = "\n\n".join(_documents(output))
            if input in (None, "") and _reported(span):
                # A response reports the documents, not the query: it is the turn's input.
                input = _turn_input(root)
        units.append(_unit(span, root, input, output, target, trace, name=_name(span)))
    return units


def matching_units(trace: Trace, target: Target) -> List[Unit]:
    """The units ``target`` picks from ``trace``, in order. The conversation and the run are
    one unit each: the whole trace, which is read from storage only if a metric asks."""
    if target.on not in PER_UNIT:
        return [Unit(None, None, None, trace, None)]
    if trace.trace_id and not trace.root_spans:
        trace._ensure_detail()
    if target.on is TargetKind.TURN:
        return _turns(trace, target)
    return _spans(trace, target)


# ---------------------------------------------------------------------------
# Judging each unit, and combining the verdicts
# ---------------------------------------------------------------------------


def _described(target: Target, count: int) -> str:
    return _phrase(target, plural=count != 1, short=False, each=False)


def _hint(target: Target) -> str:
    """How an endpoint can report what the target looks for."""
    if target.on is not TargetKind.SPAN:
        return target.preset.hint
    kinds = _taken(list(target.where or ()), SpecialField.KIND) or []
    presets = [p for p in TARGETS.values() if p.span_kind is not None and p.span_kind in kinds]
    return presets[0].hint if len(presets) == 1 else SPAN_TARGET.hint


def not_applicable(target: Target) -> MetricResult:
    """The result for a target that matched nothing in the trace."""
    reason = f"No {_described(target, 2)} were recorded. {_hint(target)}"
    return MetricResult(
        score=None,
        details={
            ResultKey.IS_SUCCESSFUL: None,
            ResultKey.NOT_APPLICABLE: True,
            ResultKey.REASON: reason,
            ResultKey.TARGET: target.on.value,
            ResultKey.MATCHED: 0,
        },
    )


def _verdict(result: MetricResult, metric: Any) -> Optional[bool]:
    """The metric's own verdict, else its score against its threshold."""
    if ResultKey.IS_SUCCESSFUL in result.details:
        return result.details[ResultKey.IS_SUCCESSFUL]
    score, threshold = _numeric(result.score), _numeric(getattr(metric, "threshold", None))
    if score is None or threshold is None:
        return None
    default = ThresholdOperator.GREATER_THAN_OR_EQUAL.value
    compare = THRESHOLD_OPERATOR_MAP.get(getattr(metric, "threshold_operator", None) or default)
    return compare(score, threshold) if compare else None


def _numeric(score: Any) -> Optional[float]:
    # bool is an int; a score of True is not the number 1 here.
    return float(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else None


def _is_not_applicable(result: MetricResult) -> bool:
    return bool(result.details.get(ResultKey.NOT_APPLICABLE))


def combine(
    target: Target,
    units: Sequence[Unit],
    results: Sequence[MetricResult],
    verdicts: Sequence[Optional[bool]],
    matched: int,
) -> MetricResult:
    """One result from the results of each judged unit."""
    rows = [
        {
            ResultKey.SPAN_ID: unit.span.span_id,
            ResultKey.NAME: unit.name,
            ResultKey.SCORE: result.score,
            ResultKey.IS_SUCCESSFUL: None if _is_not_applicable(result) else verdict,
            ResultKey.REASON: result.details.get(ResultKey.REASON),
            **({ResultKey.NOT_APPLICABLE: True} if _is_not_applicable(result) else {}),
        }
        for unit, result, verdict in zip(units, results, verdicts, strict=True)
    ]
    if rows and all(row.get(ResultKey.NOT_APPLICABLE) for row in rows):
        # Nothing to judge in any unit (a rule's missing field): not applicable, not a fail.
        return MetricResult(
            score=None,
            details={
                ResultKey.IS_SUCCESSFUL: None,
                ResultKey.NOT_APPLICABLE: True,
                ResultKey.REASON: rows[0][ResultKey.REASON],
                ResultKey.TARGET: target.on.value,
                ResultKey.MATCHED: matched,
                ResultKey.SPANS: rows,
            },
        )
    decided = [row for row in rows if row[ResultKey.IS_SUCCESSFUL] is not None]
    passed = sum(1 for row in decided if row[ResultKey.IS_SUCCESSFUL])
    share: Optional[float] = passed / len(decided) if decided else None

    if not decided:
        is_successful = None
    elif target.aggregate is Aggregation.ALL:
        is_successful = passed == len(decided)
    elif target.aggregate is Aggregation.ANY:
        is_successful = passed > 0
    else:
        is_successful = share >= target.min_share

    reason = _reason(target, rows, decided, passed, matched, is_successful)
    details: Dict[str, Any] = {
        ResultKey.IS_SUCCESSFUL: is_successful,
        ResultKey.REASON: reason,
        ResultKey.TARGET: target.on.value,
        ResultKey.MATCHED: matched,
        ResultKey.PASSED: passed,
        ResultKey.SPANS: rows,
    }
    if is_successful is None:
        details[ResultKey.INCONCLUSIVE] = True
    return MetricResult(score=_score(target, decided, share), details=details)


def _score(target: Target, decided: List[Dict[str, Any]], share: Optional[float]) -> Any:
    """``share``'s share of spans that passed; otherwise the score of the span that decided the
    verdict: the first that failed, else the first that passed ("any" looks for a pass first).
    Read in span order, it works whichever way the metric's scores run, categories included."""
    if target.aggregate is Aggregation.SHARE:
        return share
    looked_for = target.aggregate is Aggregation.ANY
    deciding = next((r for r in decided if r[ResultKey.IS_SUCCESSFUL] is looked_for), None)
    deciding = deciding or (decided[0] if decided else None)
    return deciding[ResultKey.SCORE] if deciding else None


def _reason(target, rows, decided, passed, matched, is_successful) -> str:
    counted = f"{passed} of {len(decided)} {_described(target, len(decided))} passed."
    if not decided:
        counted = f"No verdict for any of the {len(rows)} {_described(target, len(rows))}."
    skipped = sum(1 for row in rows if row.get(ResultKey.NOT_APPLICABLE))
    if skipped:
        counted += f" {skipped} could not be judged: {_first_skipped_reason(rows)}"
    if matched > len(rows):
        counted += f" Only the first {len(rows)} of {matched} were judged."
    # Name the first failing span only when it cost the metric its pass.
    failed = next((row for row in rows if row[ResultKey.IS_SUCCESSFUL] is False), None)
    if is_successful is False and failed and failed.get(ResultKey.REASON):
        label = (
            f"`{failed[ResultKey.NAME]}`"
            if failed.get(ResultKey.NAME)
            else f"#{rows.index(failed) + 1}"
        )
        counted += f" {label}: {failed[ResultKey.REASON]}"
    return counted


def _first_skipped_reason(rows: Sequence[Dict[str, Any]]) -> str:
    row = next(row for row in rows if row.get(ResultKey.NOT_APPLICABLE))
    return row.get(ResultKey.REASON) or "not applicable."


def _single_turn(target: Target, units: Sequence[Unit]) -> bool:
    # A single-turn test's one turn gives the metric's own result, as it always has. One turn
    # left by a filter is still counted, as "1 of 1 turns".
    return target.on is TargetKind.TURN and target.where is None and len(units) == 1


#: How one unit is judged: given its input, output and trace, its result.
JudgeUnit = Callable[[Unit], MetricResult]
AJudgeUnit = Callable[[Unit], Awaitable[MetricResult]]
Verdict = Callable[[MetricResult], Optional[bool]]


def judge_units(trace: Trace, target: Target, judge: JudgeUnit, verdict: Verdict) -> MetricResult:
    """Judge each unit ``target`` matches in ``trace`` with ``judge``, and combine."""
    units = matching_units(trace, target)
    if not units:
        return not_applicable(target)
    if _single_turn(target, units):
        return judge(units[0])
    judged = units[:MAX_JUDGED_SPANS]
    results = [judge(unit) for unit in judged]
    return combine(target, judged, results, [verdict(r) for r in results], len(units))


async def a_judge_units(
    trace: Trace, target: Target, judge: AJudgeUnit, verdict: Verdict
) -> MetricResult:
    import asyncio

    units = matching_units(trace, target)
    if not units:
        return not_applicable(target)
    if _single_turn(target, units):
        return await judge(units[0])
    judged = units[:MAX_JUDGED_SPANS]
    limit = asyncio.Semaphore(MAX_CONCURRENT_SPANS)

    async def bounded(unit: Unit) -> MetricResult:
        async with limit:
            return await judge(unit)

    results = list(await asyncio.gather(*(bounded(unit) for unit in judged)))
    return combine(target, judged, results, [verdict(r) for r in results], len(units))


def unit_expectations(
    target: Target, expectations: Optional[Expectations], unit: Optional[Unit] = None
) -> Optional[Expectations]:
    """What one unit is held to. A span answers neither for the test's expected response nor
    its expected tool calls. A turn answers for its own expected tool calls: its entry in
    ``tool_calls_per_turn``, or the test's list when the test has one turn. The goal,
    instructions and restrictions always apply."""
    if expectations is None or target.on not in PER_UNIT:
        return expectations
    if target.on is not TargetKind.TURN:
        dropped = (*WHOLE_TEST_EXPECTATIONS, ExpectationName.TOOL_CALLS_PER_TURN)
        return expectations.model_copy(update=dict.fromkeys(dropped))
    turn = unit.turn if unit is not None else None
    if expectations.tool_calls_per_turn is not None:
        calls = expectations.turn_tool_calls(turn) if turn is not None else None
    elif unit is not None and unit.turns == 1:
        calls = expectations.tool_calls
    else:
        calls = None
    return expectations.model_copy(
        update={ExpectationName.TOOL_CALLS: calls, ExpectationName.TOOL_CALLS_PER_TURN: None}
    )


def unit_arguments(
    declared: Sequence[str], unit: Unit, expectations: Optional[Expectations]
) -> Dict[str, Any]:
    """What a metric declaring ``declared`` receives for one unit: the unit's trace, and its
    input and output. A unit of the whole trace reads its input and output from the trace
    only for a metric that doesn't take the trace itself (a conversation's transcript)."""
    values: Dict[str, Any] = {
        JudgedParam.TRACE: unit.trace,
        JudgedParam.EXPECTATIONS: expectations,
    }
    if unit.span is not None:
        values[JudgedParam.INPUT], values[JudgedParam.OUTPUT] = unit.input, unit.output
    elif JudgedParam.TRACE not in declared and set(declared) & READS_INPUT_OUTPUT:
        judged = judged_input_output(unit.trace, expectations)
        values[JudgedParam.INPUT], values[JudgedParam.OUTPUT] = judged
    return {name: value for name, value in values.items() if name in declared}


def evaluate_target(
    metric: Any,
    trace: Trace,
    target: Union[Target, Dict[str, Any], str],
    expectations: Any = None,
    verdict: Optional[Verdict] = None,
) -> MetricResult:
    """Evaluate ``metric`` on the units ``target`` picks from ``trace``.

    A per-unit target runs the metric once per unit and combines the verdicts; the
    conversation and the run are one unit, judged once.
    """
    target = check_target(metric, target)
    expectations = Expectations.coerce(expectations)
    declared = _declared(metric)
    token = judging_unit.set(True)
    try:
        if target.on not in PER_UNIT:
            [unit] = matching_units(trace, target)
            return metric.evaluate(**unit_arguments(declared, unit, expectations))
        return judge_units(
            trace,
            target,
            lambda unit: metric.evaluate(
                **unit_arguments(declared, unit, unit_expectations(target, expectations, unit))
            ),
            verdict or (lambda result: _verdict(result, metric)),
        )
    finally:
        judging_unit.reset(token)


async def a_evaluate_target(
    metric: Any,
    trace: Trace,
    target: Union[Target, Dict[str, Any], str],
    expectations: Any = None,
    verdict: Optional[Verdict] = None,
) -> MetricResult:
    """Async ``evaluate_target``; the units are judged concurrently."""
    target = check_target(metric, target)
    expectations = Expectations.coerce(expectations)
    declared = _declared(metric, "a_evaluate")

    async def judge(unit: Unit) -> MetricResult:
        held_to = unit_expectations(target, expectations, unit)
        return await metric.a_evaluate(**unit_arguments(declared, unit, held_to))

    token = judging_unit.set(True)
    try:
        if target.on not in PER_UNIT:
            [unit] = matching_units(trace, target)
            return await metric.a_evaluate(**unit_arguments(declared, unit, expectations))
        return await a_judge_units(
            trace, target, judge, verdict or (lambda result: _verdict(result, metric))
        )
    finally:
        judging_unit.reset(token)
