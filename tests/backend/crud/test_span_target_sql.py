"""The spans list filtered by a metric target picks exactly what the SDK picks.

``crud/span_target_sql.py`` translates a target into SQL; the SDK's ``Target.select`` walks the
span tree. Both run here on the same stored traces, built as evaluation builds them, and every
target must give the same spans, in list order, for the whole list and a page in the middle.

Each unit is shown by its root span: the span for a per-span target, the turn's root for
``turn``, and the trace's first root for ``run`` and ``conversation``. ``conversation`` keeps the
traces the platform judges as one (``Trace.is_conversation``, which the evaluator checks before a
conversation metric runs); ``Target.select`` alone would give one unit for any trace.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytest
import sqlalchemy as sa
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.constants import ConversationContext
from rhesis.telemetry.schemas import SpanKind, StatusCode

from rhesis.backend.app import models
from rhesis.backend.app.constants import REPORTED_SPAN_SOURCE, AISpanAttributes
from rhesis.backend.app.crud.span_target_sql import postgres_pattern
from rhesis.backend.app.crud.telemetry import create_trace_spans, query_spans, span_facets
from rhesis.backend.app.schemas.telemetry import OTELSpanCreate, SpanFilters
from rhesis.backend.app.services.telemetry.evaluation_trace import stored_trace
from rhesis.sdk.entities.trace import FROM_CONVERSATION, TRACE_SOURCE_ATTRIBUTE, Trace
from rhesis.sdk.metrics.targets import Target, TargetKind

BASE = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)

AGENT = AIAttributes.OPERATION_AGENT_INVOKE
TOOL = AIAttributes.OPERATION_TOOL_INVOKE
LLM = AIAttributes.OPERATION_LLM_INVOKE
RETRIEVAL = AIAttributes.OPERATION_RETRIEVAL
REPORTED = {AISpanAttributes.SPAN_SOURCE: REPORTED_SPAN_SOURCE}
TURN_INPUT = ConversationContext.SpanAttributes.CONVERSATION_INPUT
TURN_OUTPUT = ConversationContext.SpanAttributes.CONVERSATION_OUTPUT
#: Any attribute key works; this one holds multi-line text.
PROMPT = "app.prompt"


def agent(name: str, **extra) -> Dict[str, Any]:
    return {AIAttributes.OPERATION_TYPE: AGENT, AIAttributes.AGENT_NAME: name, **extra}


def tool(name: Any, **extra) -> Dict[str, Any]:
    return {AIAttributes.OPERATION_TYPE: TOOL, AIAttributes.TOOL_NAME: name, **extra}


def llm(model: str, **extra) -> Dict[str, Any]:
    return {AIAttributes.OPERATION_TYPE: LLM, AIAttributes.MODEL_NAME: model, **extra}


def retrieval(**extra) -> Dict[str, Any]:
    return {AIAttributes.OPERATION_TYPE: RETRIEVAL, **extra}


class Seed:
    """Spans for one project, added trace by trace."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.spans: List[OTELSpanCreate] = []
        self.trace_id = ""

    def trace(self) -> None:
        self.trace_id = uuid.uuid4().hex

    def add(
        self,
        name: str,
        parent: Optional[str] = None,
        at: float = 0.0,
        dur: float = 1.0,
        error: bool = False,
        attrs: Optional[Dict[str, Any]] = None,
    ) -> str:
        span_id = uuid.uuid4().hex[:16]
        start = BASE + timedelta(seconds=at)
        self.spans.append(
            OTELSpanCreate(
                trace_id=self.trace_id,
                span_id=span_id,
                parent_span_id=parent,
                project_id=self.project_id,
                environment="development",
                span_name=name,
                span_kind=SpanKind.INTERNAL,
                start_time=start,
                end_time=start + timedelta(seconds=dur),
                status_code=StatusCode.ERROR if error else StatusCode.OK,
                attributes=attrs or {},
            )
        )
        return span_id


def _agents_and_tools(s: Seed) -> None:
    # Triage hands off to billing; numbers arrive as numbers and as text.
    s.trace()
    r = s.add("ai.agent.invoke", at=0, dur=10, attrs=agent("triage", **{"customer.tier": "gold"}))
    s.add("ai.llm.invoke", r, at=0.1, attrs=llm("gpt-4o", **{PROMPT: "refund please"}))
    b = s.add("ai.agent.invoke", r, at=1, dur=5, attrs=agent("billing"))
    s.add(
        "ai.tool.invoke",
        b,
        at=1.1,
        dur=0.2,
        error=True,
        attrs=tool("issue_refund", amount=120, **{"http.status_code": 200}),
    )
    s.add(
        "ai.tool.invoke",
        b,
        at=1.5,
        dur=2,
        attrs=tool("lookup_order", amount="80", retry=True, **{"http.status_code": "200"}),
    )
    s.add("ai.retrieval", b, at=2, attrs=retrieval(**{"ai.retrieval.query": "refund policy"}))
    s.add("ai.llm.invoke", b, at=3, attrs=llm("claude-sonnet"))
    s.add(
        "ai.tool.invoke",
        r,
        at=7,
        attrs=tool("lookup_order", amount=None, **{"customer.tier": "silver"}),
    )


def _reported(s: Seed) -> None:
    # A REST endpoint: everything reported.
    s.trace()
    r = s.add("function.endpoint", at=20, dur=3, attrs={"customer.tier": "bronze"})
    s.add("ai.tool.invoke", r, at=20.1, dur=0, attrs={**REPORTED, **tool("lookup_order")})
    s.add("ai.retrieval", r, at=20.2, dur=0, attrs={**REPORTED, **retrieval()})
    s.add(
        "ai.llm.invoke",
        r,
        at=20.3,
        dur=0,
        attrs={**REPORTED, AIAttributes.OPERATION_TYPE: LLM, AIAttributes.LLM_TOKENS_INPUT: 5},
    )
    # Recorded and reported, same kind: the reported calls drop out where a recorded one matched.
    s.trace()
    r = s.add("function.endpoint", at=30, dur=3)
    s.add("ai.tool.invoke", r, at=30.1, dur=0.1, attrs=tool("lookup_order", amount=99))
    s.add(
        "ai.tool.invoke", r, at=30.2, dur=0, attrs={**REPORTED, **tool("lookup_order", amount=99)}
    )
    s.add("ai.tool.invoke", r, at=30.3, dur=0, attrs={**REPORTED, **tool("issue_refund")})
    s.add("ai.retrieval", r, at=30.4, dur=0, attrs={**REPORTED, **retrieval()})


def _conversations(s: Seed) -> None:
    # Two turns, agents nested through plain spans.
    s.trace()
    r1 = s.add("function.turn", at=40, dur=5, attrs={TURN_INPUT: "hi", "customer.tier": "gold"})
    sup = s.add("ai.agent.invoke", r1, at=40.1, dur=4, attrs=agent("support"))
    step = s.add("function.step", sup, at=40.2, dur=3)
    b = s.add("ai.agent.invoke", step, at=40.3, dur=2, attrs=agent("billing"))
    inner = s.add("function.inner", b, at=40.4, dur=1)
    s.add("ai.tool.invoke", inner, at=40.5, dur=0.3, attrs=tool("issue_refund", amount=300.5))
    s.add(
        "ai.tool.invoke", sup, at=43, dur=0.6, attrs=tool("search_kb", **{"customer.tier": "Gold"})
    )
    r2 = s.add("function.turn", at=50, dur=5, attrs={TURN_OUTPUT: "bye"})
    s2 = s.add("ai.agent.invoke", r2, at=50.1, dur=4, attrs=agent("support"))
    s.add("ai.tool.invoke", s2, at=50.2, dur=1.2, attrs=tool("lookup_order", amount="1e2"))
    # A root without a turn's text, after the turns: neither a turn nor the first root.
    s.add("function.cleanup", at=56, dur=0.5)

    # One turn of a longer conversation, marked as such.
    s.trace()
    r = s.add(
        "function.turn",
        at=60,
        dur=2,
        attrs={TURN_INPUT: "again", TRACE_SOURCE_ATTRIBUTE: FROM_CONVERSATION},
    )
    s.add(
        "ai.llm.invoke",
        r,
        at=60.5,
        attrs=llm("gpt-4o", **{PROMPT: "line one\nrefund policy\n"}),
    )

    # Two roots and no turn text: one turn, the first root; not a conversation.
    s.trace()
    s.add("function.first", at=70, dur=1, attrs={TURN_INPUT: "", "customer.tier": "gold"})
    s.add("function.second", at=71, dur=1, attrs={TURN_OUTPUT: 0})


def _odd_values(s: Seed) -> None:
    # An agent named by its tool attribute, and an orphan whose parent was never stored.
    s.trace()
    w = s.add(
        "ai.agent.invoke",
        at=80,
        dur=2,
        attrs=agent("billing", **{AIAttributes.TOOL_NAME: "router"}),
    )
    s.add("ai.tool.invoke", w, at=80.5, dur=0.4, attrs=tool("lookup_order", amount="1_000"))
    orphan_parent = uuid.uuid4().hex[:16]
    s.add(
        "ai.tool.invoke", orphan_parent, at=81, dur=0.4, attrs=tool("issue_refund", amount=" 150 ")
    )
    # Values that look like numbers but aren't finite ones, a name that isn't text, an empty
    # tool name that falls through to the agent's, and a multi-line value for regexes.
    s.trace()
    r = s.add("function.odd", at=90, dur=1, attrs={"amount": "1e999", "note": "abc\n"})
    s.add("ai.tool.invoke", r, at=90.1, attrs=tool(7, amount="1e-999", flag=True))
    s.add(
        "ai.tool.invoke",
        r,
        at=90.2,
        attrs=tool("", amount="-1e999", **{AIAttributes.AGENT_NAME: "helper"}),
    )
    s.add("function.misc", r, at=90.3, attrs={"amount": "abc", "tags": ["a", "b"]})
    s.add("ai.tool.invoke", r, at=90.4, attrs=tool(" 200 "))


def seed(project_id: str) -> List[OTELSpanCreate]:
    s = Seed(project_id)
    for part in (_agents_and_tools, _reported, _conversations, _odd_values):
        part(s)
    return s.spans


def c(field: str, op: str, value: Any = None) -> Dict[str, Any]:
    condition = {"field": field, "op": op}
    if value is not None:
        condition["value"] = value
    return condition


def span(*conditions, within: Optional[str] = None) -> Dict[str, Any]:
    target: Dict[str, Any] = {"on": TargetKind.SPAN.value, "where": list(conditions)}
    if within:
        target["within"] = within
    return target


# (id, target, may pick nothing)
TARGETS = [
    ("tool_call", {"on": "tool_call"}, False),
    ("tool_call name", {"on": "tool_call", "name": "issue_refund"}, False),
    ("agent name", {"on": "agent", "name": "billing"}, False),
    ("agent name via tool attr", {"on": "agent", "name": "router"}, False),
    ("model_call name", {"on": "model_call", "name": "gpt-4o"}, False),
    ("model_call", {"on": "model_call"}, False),
    ("retrieval", {"on": "retrieval"}, False),
    ("tool_call within billing", {"on": "tool_call", "within": "billing"}, False),
    ("tool_call within support", {"on": "tool_call", "within": "support"}, False),
    ("tool_call within nobody", {"on": "tool_call", "within": "nobody"}, True),
    ("preset dict where number", {"on": "tool_call", "where": {"http.status_code": 200}}, False),
    (
        "preset dict where list",
        {"on": "tool_call", "where": {"customer.tier": ["gold", "silver"]}},
        False,
    ),
    ("kind and amount >", span(c("kind", "==", TOOL), c("amount", ">", 100)), False),
    ("amount >= text number", span(c("amount", ">=", 80)), False),
    ("amount == 1000 underscores", span(c("amount", "==", 1000)), False),
    ("amount == 100 from 1e2", span(c("amount", "==", 100)), False),
    ("amount < 0 never -inf", span(c("amount", "<", 0)), True),
    ("amount > 1e300 never inf", span(c("amount", ">", 1e300)), True),
    ("amount == 0 from 1e-999", span(c("amount", "==", 0)), False),
    ("amount == text 1e999", span(c("amount", "==", "1e999")), False),
    ("amount != 99", {"on": "tool_call", "where": [c("amount", "!=", 99)]}, False),
    ("amount not_in", {"on": "tool_call", "where": [c("amount", "not_in", [99, "80"])]}, False),
    ("amount < 1000 missing fails", {"on": "tool_call", "where": [c("amount", "<", 1000)]}, False),
    ("amount not_exists", {"on": "tool_call", "where": [c("amount", "not_exists")]}, False),
    ("amount exists", span(c("amount", "exists")), False),
    ("retry not_exists", {"on": "tool_call", "where": [c("retry", "not_exists")]}, False),
    ("retry exists", span(c("retry", "exists")), False),
    ("flag == true", span(c("flag", "==", True)), False),
    ("flag == text true", span(c("flag", "==", "true")), False),
    ("tier in", span(c("customer.tier", "in", ["gold", "silver"])), False),
    ("tier not_in", span(c("customer.tier", "not_in", ["gold"])), False),
    ("attributes. prefix !=", span(c("attributes.customer.tier", "!=", "gold")), False),
    ("http status text == 200", span(c("http.status_code", "==", "200")), False),
    ("tags contains", span(c("tags", "contains", '"b"')), False),
    ("name contains", span(c("name", "contains", "refund")), False),
    ("name matches", span(c("name", "matches", "^look.*order$")), False),
    ("name == 7 not text", span(c("name", "==", 7)), True),
    ("tool name attribute == 7", span(c(AIAttributes.TOOL_NAME, "==", 7)), False),
    ("name == helper fallthrough", span(c("name", "==", "helper")), False),
    ("name == 200 span name", span(c("name", "==", 200)), False),
    ("span_name in", span(c("span_name", "in", ["function.turn", "function.odd"])), False),
    ("name == 200.0 text number", span(c("name", "==", 200.0)), False),
    ("span_name matches", span(c("span_name", "matches", "^function\\.(first|second)$")), False),
    ("prompt matches alternation", span(c(PROMPT, "matches", "ref(und|use)")), False),
    ("prompt dot no newline", span(c(PROMPT, "matches", "one.refund")), True),
    ("prompt dollar before newline", span(c(PROMPT, "matches", "policy$")), False),
    ("note dollar before newline", span(c("note", "matches", "^abc$")), False),
    ("note class takes newline", span(c("note", "matches", "abc[^x]")), False),
    ("status == ERROR any case", span(c("status", "==", "ERROR")), False),
    ("status != ok", span(c("status", "!=", "ok")), False),
    (
        "status != error reported pass",
        {"on": "tool_call", "where": [c("status", "!=", "error")]},
        False,
    ),
    ("duration < 500", span(c("duration_ms", "<", 500)), False),
    ("duration >= 1000", span(c("duration_ms", ">=", 1000)), False),
    (
        "duration not_in 200",
        {"on": "tool_call", "where": [c("duration_ms", "not_in", [200])]},
        False,
    ),
    ("duration == 200", span(c("duration_ms", "==", 200)), False),
    ("within billing llm", span(c("kind", "==", LLM), within="billing"), False),
    ("kind in", span(c("kind", "in", [TOOL, RETRIEVAL])), False),
    ("kind preset name", span(c("kind", "==", "tool_call")), False),
    ("kind and name agent", span(c("kind", "==", AGENT), c("name", "==", "billing")), False),
    (
        "preset within and name cond",
        {"on": "tool_call", "within": "support", "where": [c("name", "==", "lookup_order")]},
        False,
    ),
    (
        "reported only kind",
        span(c("kind", "==", RETRIEVAL), c("customer.tier", "not_exists")),
        False,
    ),
    ("turn", {"on": "turn"}, False),
    ("turn where", {"on": "turn", "where": [c("customer.tier", "==", "gold")]}, False),
    ("turn where kind", {"on": "turn", "where": [c("kind", "==", AGENT)]}, False),
    ("conversation", {"on": "conversation"}, False),
    ("run", {"on": "run"}, False),
]


def _ordered(picked: Dict[str, datetime]) -> List[str]:
    """Span ids in the list's default order: newest first, then by id."""
    return sorted(picked, key=lambda i: (picked[i], uuid.UUID(i)), reverse=True)


def _stored_traces(db, project_id: str) -> List[Trace]:
    rows = (
        db.query(models.Trace)
        .filter(models.Trace.project_id == project_id)
        .order_by(models.Trace.start_time.asc())
        .all()
    )
    by_trace: Dict[str, list] = {}
    for row in rows:
        by_trace.setdefault(row.trace_id, []).append(row)
    return [
        stored_trace(trace_id, project_id, trace_rows) for trace_id, trace_rows in by_trace.items()
    ]


def sdk_picks(db, project_id: str, target: Target) -> List[str]:
    """The root span of each unit the SDK picks, in list order."""
    picked: Dict[str, datetime] = {}
    for trace in _stored_traces(db, project_id):
        if target.on is TargetKind.CONVERSATION and not trace.is_conversation:
            continue
        for unit in target.select(trace):
            root = unit.span or trace.root_spans[0]
            picked[root.id] = root.start_time
    return _ordered(picked)


def sql_picks(db, org_id: str, project_id: str, target: Target, limit=1000, offset=0):
    rows, total = query_spans(
        db, org_id, project_id, SpanFilters(target=target), limit=limit, offset=offset
    )
    return [str(row.id) for row in rows], total


@pytest.fixture
def seeded(test_db, db_project, test_org_id):
    project_id = str(db_project.id)
    create_trace_spans(test_db, seed(project_id), organization_id=test_org_id)
    return project_id


@pytest.mark.integration
@pytest.mark.parametrize("target_id, value, may_be_empty", TARGETS, ids=[t[0] for t in TARGETS])
def test_the_list_picks_what_the_sdk_picks(
    test_db, test_org_id, seeded, target_id, value, may_be_empty
):
    target = Target.coerce(value)
    truth = sdk_picks(test_db, seeded, target)
    everything = test_db.query(models.Trace).filter(models.Trace.project_id == seeded).count()
    assert may_be_empty or truth, f"{target_id} picks nothing"
    assert len(truth) < everything, f"{target_id} picks every span"

    picked, total = sql_picks(test_db, test_org_id, seeded, target)
    assert picked == truth
    assert total == len(truth)

    page, page_total = sql_picks(test_db, test_org_id, seeded, target, limit=2, offset=1)
    assert page == truth[1:3]
    assert page_total == len(truth) or not page


@pytest.mark.integration
@pytest.mark.parametrize("on", [TargetKind.TURN, TargetKind.RUN, TargetKind.CONVERSATION])
def test_spans_not_backfilled_look_their_parent_up(test_db, test_org_id, seeded, on):
    """Spans stored before ``is_root`` existed hold NULL until the backfill reaches them."""
    target = Target.coerce({"on": on.value})
    test_db.execute(
        sa.update(models.Trace).where(models.Trace.project_id == seeded).values(is_root=None)
    )

    picked, _ = sql_picks(test_db, test_org_id, seeded, target)

    assert picked == sdk_picks(test_db, seeded, target)


@pytest.mark.integration
def test_facets_count_the_picked_spans(test_db, test_org_id, seeded):
    target = Target.coerce({"on": "tool_call", "within": "billing"})
    facets = span_facets(test_db, test_org_id, seeded, SpanFilters(target=target))
    assert sum(row.count for row in facets.span_types) == len(sdk_picks(test_db, seeded, target))


@pytest.mark.integration
def test_target_applies_with_the_tool_filter(test_db, test_org_id, seeded):
    target = Target.coerce({"on": "tool_call", "within": "billing"})
    filters = SpanFilters(target=target, tools=["lookup_order"])
    rows, total = query_spans(test_db, test_org_id, seeded, filters)
    assert total == 1
    assert {row.span_name for row in rows} == {"ai.tool.invoke"}


@pytest.mark.parametrize(
    "pattern, expected",
    [
        ("a.b", "a[^\\n]b"),
        ("^abc$", "^abc(?=\\n?$)"),
        ("[.$]x", "[.$]x"),
        ("[].]x.", "[].]x[^\\n]"),
        ("\\.\\$", "\\.\\$"),
    ],
)
def test_postgres_pattern(pattern, expected):
    assert postgres_pattern(pattern) == expected
