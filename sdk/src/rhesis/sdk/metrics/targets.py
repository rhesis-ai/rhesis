"""What a metric judges in a trace: its target.

A metric judges a turn, the conversation or the whole run once, or runs once per span of one
kind (each tool call, each retrieval, ...) and combines those verdicts into one. ``TARGETS``
is the one list of choices; validation, the MCP tools and the docs read it.

    judge.evaluate(trace=trace, target={"on": "tool_call", "name": "issue_refund"})
"""

import inspect
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rhesis.sdk.entities.trace import (
    _CONVERSATION_INPUT,
    _CONVERSATION_OUTPUT,
    _REPORTED,
    _SPAN_SOURCE,
    TRACE_SOURCE_ATTRIBUTE,
    Span,
    Trace,
    _documents,
    _recorded,
)
from rhesis.sdk.metrics.arguments import judged_input_output
from rhesis.sdk.metrics.base import MetricResult
from rhesis.sdk.metrics.constants import THRESHOLD_OPERATOR_MAP
from rhesis.sdk.metrics.expectations import Expectations

#: At most this many spans are judged per metric; the rest are counted, not judged.
MAX_JUDGED_SPANS = 25
#: Spans one metric judges at the same time, so a judge doesn't send 25 model calls at once.
MAX_CONCURRENT_SPANS = 5


class TargetKind(str, Enum):
    TURN = "turn"
    CONVERSATION = "conversation"
    RUN = "run"
    TOOL_CALL = "tool_call"
    RETRIEVAL = "retrieval"
    MODEL_CALL = "model_call"
    AGENT = "agent"
    GUARDRAIL = "guardrail"


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
        span_kind="tool.invoke",
        noun=("tool call", "tool calls"),
        hint="If the endpoint makes them, map tool_calls in its response or send traces.",
    ),
    TargetKind.RETRIEVAL: TargetPreset(
        "Each retrieval",
        "Every retrieval: its query as input, the documents it found as output.",
        span_kind="retrieval",
        noun=("retrieval", "retrievals"),
        hint="If the endpoint retrieves documents, map context in its response or send traces.",
    ),
    TargetKind.MODEL_CALL: TargetPreset(
        "Each model call",
        "Every call to a model: its prompt as input, its completion as output.",
        span_kind="llm.invoke",
        noun=("model call", "model calls"),
    ),
    TargetKind.AGENT: TargetPreset(
        "Each agent",
        "Every agent run: its task as input, its final answer as output.",
        span_kind="agent.invoke",
        noun=("agent run", "agent runs"),
    ),
    TargetKind.GUARDRAIL: TargetPreset(
        "Each guardrail check",
        "Every guardrail check: what it checked as input, its decision as output.",
        span_kind="guardrail",
        noun=("guardrail check", "guardrail checks"),
    ),
}

#: Expectations about the whole test, which no single span or turn is held to.
WHOLE_TEST_EXPECTATIONS = ("response", "tool_calls")

#: Targets judged once per matching unit rather than once in all.
PER_UNIT = frozenset(kind for kind, preset in TARGETS.items() if preset.span_kind) | {
    TargetKind.TURN
}


class Target(BaseModel):
    """What a metric judges. ``name`` and ``within`` narrow a per-span target."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    on: TargetKind
    name: Optional[str] = Field(default=None, min_length=1)
    """Only spans with this name: the tool, the agent, the model, or the span's name."""
    within: Optional[str] = Field(default=None, min_length=1)
    """Only spans inside the agent with this name."""
    aggregate: Aggregation = Aggregation.ALL
    min_share: Optional[float] = Field(default=None, gt=0, le=1)

    @model_validator(mode="after")
    def _check(self) -> "Target":
        if self.on not in PER_UNIT or self.on is TargetKind.TURN:
            narrowed = [f for f in ("name", "within") if getattr(self, f) is not None]
            if narrowed:
                raise ValueError(
                    f"{' and '.join(narrowed)} only narrow a per-span target, not '{self.on.value}'"
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
            return cls(on=value)
        return cls.model_validate(value)

    @property
    def preset(self) -> TargetPreset:
        return TARGETS[self.on]

    def to_config(self) -> Dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True, exclude_defaults=True)


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

    A metric reading ``input`` or ``output`` judges a turn or any span; one reading ``trace``
    judges a turn's trace, the conversation or the whole run. A conversational metric judges
    conversations. ``compares`` lists the expectations the metric compares with: one that
    describes the whole test (``response``, ``tool_calls``) can't be held against a span, and
    expected tool calls can't be held against one turn of a conversation either. A
    conversation has no expected response, so a metric comparing with one can't judge it.
    """
    if conversational:
        return [TargetKind.CONVERSATION, TargetKind.RUN]
    declared = set(declared)
    kinds: List[TargetKind] = []
    if declared & {"input", "output"}:
        kinds += [kind for kind in TargetKind if kind in PER_UNIT]
    if "trace" in declared:
        kinds += [TargetKind.CONVERSATION, TargetKind.RUN]
        if TargetKind.TURN not in kinds:
            kinds.insert(0, TargetKind.TURN)
    if set(compares) & set(WHOLE_TEST_EXPECTATIONS):
        kinds = [kind for kind in kinds if not TARGETS[kind].span_kind]
    if "tool_calls" in compares:
        kinds = [kind for kind in kinds if kind is not TargetKind.TURN]
    if "response" in compares:
        kinds = [kind for kind in kinds if kind is not TargetKind.CONVERSATION]
    return kinds


def _compares(metric: Any) -> List[str]:
    compares = list(getattr(metric, "REQUIRED_EXPECTATIONS", ()))
    # An instance's setting, or a class that always compares with one (DeepEval's recall).
    if getattr(metric, "requires_ground_truth", False) is True:
        compares.append("response")
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
    if declared & {"input", "output"}:
        return TargetKind.TURN
    if "trace" in declared:
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
        choices = ", ".join(f"{TARGETS[k].label} ({k.value})" for k in supported)
        raise ValueError(f"This metric can't judge '{target.on.value}'. Choices: {choices}.")
    return target


# ---------------------------------------------------------------------------
# What a target matches in a trace
# ---------------------------------------------------------------------------


@dataclass
class Unit:
    """One thing a per-unit target judges: a span, as the input and output a metric reads."""

    span: Span
    input: str
    output: str
    trace: Trace
    name: Optional[str]


def _text(value: Any) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value, default=str)


def _name(span: Span) -> Optional[str]:
    attributes = span.attributes
    for key in ("ai.tool.name", "ai.agent.name", "ai.model.name"):
        value = attributes.get(key)
        if isinstance(value, str) and value:
            return value
    return span.span_name


def _walk(spans: Sequence[Span], agents: Tuple[str, ...] = ()):
    """Each span with the names of the agents it runs inside, depth first."""
    for span in spans:
        yield span, agents
        inner = agents + (_name(span) or "",) if span.kind == "agent.invoke" else agents
        yield from _walk(span.children, inner)


def _turn_input(root: Span) -> Any:
    return root.attributes.get(_CONVERSATION_INPUT) or root.input


def _reported(span: Span) -> bool:
    return span.attributes.get(_SPAN_SOURCE) == _REPORTED


def _turn_trace(trace: Trace, root: Span) -> Trace:
    # One turn of a conversation, judged as a turn and not as a conversation.
    attributes = {k: v for k, v in root.attributes.items() if k != TRACE_SOURCE_ATTRIBUTE}
    turn = Trace(
        trace_id=trace.trace_id,
        conversation_id=trace.conversation_id,
        root_spans=[root.model_copy(update={"attributes": attributes})],
    )
    turn._detail_loaded = True
    return turn


def _turns(trace: Trace) -> List[Unit]:
    units = []
    for root in trace._turn_roots():
        user = _turn_input(root)
        reply = root.attributes.get(_CONVERSATION_OUTPUT) or root.output
        units.append(Unit(root, _text(user), _text(reply), _turn_trace(trace, root), None))
    return units


def _spans(trace: Trace, target: Target) -> List[Unit]:
    kind = target.preset.span_kind
    found = [
        (span, root)
        for root in trace.root_spans
        for span, agents in _walk([root])
        if span.kind == kind
        and (target.name is None or _name(span) == target.name)
        and (target.within is None or target.within in agents)
    ]
    # A call the endpoint both recorded and reported counts once.
    kept = {id(span) for span in _recorded([span for span, _ in found], kind)}
    units = []
    for span, root in found:
        if id(span) not in kept:
            continue
        input, output = span.input, span.output
        if kind == "retrieval":
            output = "\n\n".join(_documents(output))
            if input in (None, "") and _reported(span):
                # A response reports the documents, not the query: it is the turn's input.
                input = _turn_input(root)
        units.append(Unit(span, _text(input), _text(output), trace, _name(span)))
    return units


def matching_units(trace: Trace, target: Target) -> List[Unit]:
    """What a per-unit target judges in ``trace``, in order."""
    if trace.trace_id and not trace.root_spans:
        trace._ensure_detail()
    if target.on is TargetKind.TURN:
        return _turns(trace)
    return _spans(trace, target)


# ---------------------------------------------------------------------------
# Judging each unit, and combining the verdicts
# ---------------------------------------------------------------------------


def _described(target: Target, count: int) -> str:
    singular, plural = target.preset.noun
    noun = singular if count == 1 else plural
    if target.name:
        noun += f" named `{target.name}`"
    if target.within:
        noun += f" inside `{target.within}`"
    return noun


def not_applicable(target: Target) -> MetricResult:
    """The result for a target that matched nothing in the trace."""
    reason = f"No {_described(target, 2)} were recorded. {target.preset.hint}"
    return MetricResult(
        score=None,
        details={
            "is_successful": None,
            "not_applicable": True,
            "reason": reason,
            "target": target.on.value,
            "matched": 0,
        },
    )


def _verdict(result: MetricResult, metric: Any) -> Optional[bool]:
    """The metric's own verdict, else its score against its threshold."""
    if "is_successful" in result.details:
        return result.details["is_successful"]
    score, threshold = _numeric(result.score), _numeric(getattr(metric, "threshold", None))
    if score is None or threshold is None:
        return None
    compare = THRESHOLD_OPERATOR_MAP.get(getattr(metric, "threshold_operator", None) or ">=")
    return compare(score, threshold) if compare else None


def _numeric(score: Any) -> Optional[float]:
    # bool is an int; a score of True is not the number 1 here.
    return float(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else None


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
            "span_id": unit.span.span_id,
            "name": unit.name,
            "score": result.score,
            "is_successful": verdict,
            "reason": result.details.get("reason"),
        }
        for unit, result, verdict in zip(units, results, verdicts, strict=True)
    ]
    decided = [row for row in rows if row["is_successful"] is not None]
    passed = sum(1 for row in decided if row["is_successful"])
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
        "is_successful": is_successful,
        "reason": reason,
        "target": target.on.value,
        "matched": matched,
        "passed": passed,
        "spans": rows,
    }
    if is_successful is None:
        details["inconclusive"] = True
    return MetricResult(score=_score(target, decided, share), details=details)


def _score(target: Target, decided: List[Dict[str, Any]], share: Optional[float]) -> Any:
    """``share``'s share of spans that passed; otherwise the score of the span that decided the
    verdict: the first that failed, else the first that passed ("any" looks for a pass first).
    Read in span order, it works whichever way the metric's scores run, categories included."""
    if target.aggregate is Aggregation.SHARE:
        return share
    looked_for = target.aggregate is Aggregation.ANY
    deciding = next((r for r in decided if r["is_successful"] is looked_for), None)
    deciding = deciding or (decided[0] if decided else None)
    return deciding["score"] if deciding else None


def _reason(target, rows, decided, passed, matched, is_successful) -> str:
    counted = f"{passed} of {len(decided)} {_described(target, len(decided))} passed."
    if not decided:
        counted = f"No verdict for any of the {len(rows)} {_described(target, len(rows))}."
    if matched > len(rows):
        counted += f" Only the first {len(rows)} of {matched} were judged."
    # Name the first failing span only when it cost the metric its pass.
    failed = next((row for row in rows if row["is_successful"] is False), None)
    if is_successful is False and failed and failed.get("reason"):
        label = f"`{failed['name']}`" if failed.get("name") else f"#{rows.index(failed) + 1}"
        counted += f" {label}: {failed['reason']}"
    return counted


def _single_turn(target: Target, units: Sequence[Unit]) -> bool:
    # A single-turn test's one turn gives the metric's own result, as it always has.
    return target.on is TargetKind.TURN and len(units) == 1


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
    target: Target, expectations: Optional[Expectations]
) -> Optional[Expectations]:
    """What one unit is held to. A span answers neither for the test's expected response nor
    its expected tool calls, and a turn not for the calls of the whole conversation; the
    goal, instructions and restrictions still apply."""
    if expectations is None or target.on not in PER_UNIT:
        return expectations
    dropped = ("tool_calls",) if target.on is TargetKind.TURN else WHOLE_TEST_EXPECTATIONS
    return expectations.model_copy(update=dict.fromkeys(dropped))


def unit_arguments(
    declared: Sequence[str], unit: Unit, expectations: Optional[Expectations]
) -> Dict[str, Any]:
    """What a metric declaring ``declared`` receives for one unit."""
    values = {
        "input": unit.input,
        "output": unit.output,
        "trace": unit.trace,
        "expectations": expectations,
    }
    return {name: value for name, value in values.items() if name in declared}


def evaluate_target(
    metric: Any,
    trace: Trace,
    target: Union[Target, Dict[str, Any], str],
    expectations: Any = None,
    verdict: Optional[Verdict] = None,
) -> MetricResult:
    """Evaluate ``metric`` on what ``target`` names in ``trace``.

    A per-unit target runs the metric once per matching span and combines the verdicts; the
    others run it once on the whole trace.
    """
    target = check_target(metric, target)
    expectations = Expectations.coerce(expectations)
    declared = _declared(metric)
    if target.on not in PER_UNIT:
        return metric.evaluate(**_whole(declared, trace, expectations))
    expectations = unit_expectations(target, expectations)
    return judge_units(
        trace,
        target,
        lambda unit: metric.evaluate(**unit_arguments(declared, unit, expectations)),
        verdict or (lambda result: _verdict(result, metric)),
    )


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
    if target.on not in PER_UNIT:
        return await metric.a_evaluate(**_whole(declared, trace, expectations))
    expectations = unit_expectations(target, expectations)

    async def judge(unit: Unit) -> MetricResult:
        return await metric.a_evaluate(**unit_arguments(declared, unit, expectations))

    return await a_judge_units(
        trace, target, judge, verdict or (lambda result: _verdict(result, metric))
    )


def _whole(declared, trace: Trace, expectations: Optional[Expectations]) -> Dict[str, Any]:
    values: Dict[str, Any] = {"trace": trace, "expectations": expectations}
    if "trace" not in declared:
        values["input"], values["output"] = judged_input_output(trace, expectations)
    return {name: value for name, value in values.items() if name in declared}
