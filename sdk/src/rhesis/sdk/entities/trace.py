from __future__ import annotations

import os
from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    Literal,
    NoReturn,
    Optional,
    Sequence,
    Union,
)

from pydantic import BaseModel, Field, PrivateAttr, model_validator

from rhesis.sdk.clients import APIClient, Endpoints, Methods
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity, handle_http_errors
from rhesis.sdk.entities.project import Project
from rhesis.sdk.entities.test import Test
from rhesis.sdk.entities.test_result import TestResult
from rhesis.sdk.entities.test_run import TestRun
from rhesis.sdk.errors import RhesisAPIError

if TYPE_CHECKING:
    from rhesis.sdk.entities.annotation import Annotation, Verdict
    from rhesis.sdk.entities.endpoint import Endpoint
    from rhesis.sdk.entities.file import File

ENDPOINT = Endpoints.TELEMETRY_TRACES

# One page of the list route, whose own maximum is 1000. Paging continues past
# this, so a filter matching more traces than one page is read whole.
_PAGE_SIZE = 100

# The list route returns ids flat; the detail route returns the same relations as
# nested objects and no ids at all. Normalising on the way in means
# ``trace.test_run_id`` is populated whichever call produced the trace, rather
# than being None on exactly the half of cases a caller did not anticipate.
_NESTED_IDS = {
    "endpoint_id": "endpoint",
    "test_run_id": "test_run",
    "test_result_id": "test_result",
    "test_id": "test",
    "project_id": "project",
}

_NOT_WRITABLE = (
    "Traces are produced by instrumentation, not written through the API. "
    "Instrument your application with rhesis.sdk.telemetry to record one. "
    "What you can do to an existing trace is annotate it: "
    "trace.annotate('fail', 'The retrieval step returned nothing.')"
)


def _as_timestamp(value: Optional[Union[str, datetime]]) -> Optional[str]:
    """A time filter as the route wants it, accepting a datetime or an ISO string."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class Span(BaseModel):
    """One span within a trace: a single operation, with its children.

    ``id`` is the span's row id and ``span_id`` its OpenTelemetry hex id. Only
    the row id addresses a span in the platform, which is what annotating one
    takes.
    """

    id: Optional[str] = None
    span_id: Optional[str] = None
    span_name: Optional[str] = None
    span_kind: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status_code: Optional[str] = None
    status_message: Optional[str] = None
    model_name: Optional[str] = None
    # None when this span was not priced, zero when it was and the model is
    # free. See the note on Trace.total_cost_usd.
    cost_usd: Optional[float] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    events: List[Dict[str, Any]] = Field(default_factory=list)
    trace_metrics: Optional[Dict[str, Any]] = None
    execution: Optional[str] = None
    verdict: Optional[str] = None
    # Read-only projections of the annotations on this span, embedded by the
    # backend so a caller can see the verdict without a second request.
    last_annotation: Optional[Dict[str, Any]] = None
    matches_annotation: Optional[bool] = None
    annotation_summary: Optional[Dict[str, Any]] = None
    children: List["Span"] = Field(default_factory=list)

    def _row_id(self) -> str:
        if not self.id:
            raise ValueError(
                f"Span {self.span_name or self.span_id} carries no row id, so there is "
                "nothing to annotate. Spans read from a trace detail always carry one."
            )
        return self.id

    def get_annotations(self) -> List["Annotation"]:
        """Every annotation on this span."""
        from rhesis.sdk.entities.annotation import Annotations

        return Annotations.for_trace(self._row_id())

    def get_files(self) -> List["File"]:
        """Files attached to this span, such as an audio or image input."""
        from rhesis.sdk.entities.file import File

        return [File.model_validate(row) for row in Spans.get_files(self._row_id())]

    def annotate(
        self,
        verdict: Union["Verdict", str],
        comment: Optional[str] = None,
        *,
        metric: Optional[str] = None,
        turn: Optional[Union[int, str]] = None,
    ) -> "Annotation":
        """Record a human verdict on this span.

        The narrow judgement: "this LLM call is where it went wrong", as opposed
        to ``Trace.annotate``, which judges the trace as a whole.

            trace.span("ai.llm.invoke").annotate("fail", "Ignored the retrieved context.")
        """
        from rhesis.sdk.entities.annotation import AnnotatableEntity, Annotations

        return Annotations.create(
            AnnotatableEntity.TRACE,
            self._row_id(),
            verdict,
            comment,
            metric=metric,
            turn=turn,
        )


class Trace(BaseEntity):
    """One trace: what an instrumented application did to serve a request.

    A trace has two ids and they are not interchangeable. ``trace_id`` is the
    OpenTelemetry hex id, which reads a trace back. ``db_id`` is the root span's
    row id, which is what annotations and platform links take. The SDK resolves
    the second from the first, so a caller never has to know which one a call
    wants.

    Traces are read-mostly: the only write is ingestion, from
    ``rhesis.sdk.telemetry``. ``push()`` and ``delete()`` therefore raise.
    """

    endpoint: ClassVar[Endpoints] = ENDPOINT

    trace_id: Optional[str] = None
    project_id: Optional[str] = None
    environment: Optional[str] = None
    conversation_id: Optional[str] = None
    conversation_input: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    span_count: Optional[int] = None
    error_count: Optional[int] = None
    root_operation: Optional[str] = None
    status_code: Optional[str] = None
    has_errors: Optional[bool] = None

    total_tokens: Optional[int] = None
    total_input_tokens: Optional[int] = None
    total_output_tokens: Optional[int] = None
    # None means nothing in the trace was priced -- no price is held for the
    # model, or the span reported no model name. Zero is reserved for a model
    # that really is free, so the two never share a figure. Summing these
    # treating None as zero under-reports and reads as a complete total.
    total_cost_usd: Optional[float] = None
    total_cost_eur: Optional[float] = None
    total_input_cost_usd: Optional[float] = None
    total_output_cost_usd: Optional[float] = None
    models: List[str] = Field(default_factory=list)
    providers: List[str] = Field(default_factory=list)

    trace_metrics_status: Optional[str] = None
    execution: Optional[str] = None
    verdict: Optional[str] = None

    # Read-only projections of the annotations on this trace.
    has_annotations: Optional[bool] = None
    last_annotation: Optional[Dict[str, Any]] = None
    matches_annotation: Optional[bool] = None
    annotation_summary: Optional[Dict[str, Any]] = None
    tags_count: Optional[int] = None
    comments_count: Optional[int] = None

    # What produced the trace. The list route gives the ids, the detail route the
    # objects; the ids are filled in from either. There is deliberately no
    # ``endpoint`` field: that name is the API route pointer on every entity, so
    # the endpoint is reachable as ``endpoint_id`` / ``endpoint_name`` and through
    # ``get_endpoint()``.
    endpoint_id: Optional[str] = None
    endpoint_name: Optional[str] = None
    test_run_id: Optional[str] = None
    test_result_id: Optional[str] = None
    test_id: Optional[str] = None
    project: Optional[Project] = None
    test_run: Optional[TestRun] = None
    test_result: Optional[TestResult] = None
    test: Optional[Test] = None

    # Detail only. Empty on a trace that came from a listing, which is why
    # anything reading them goes through _ensure_detail() first.
    root_spans: List[Span] = Field(default_factory=list)

    # Set once the detail route has answered, so a trace that genuinely has no
    # spans is not fetched again on every call that reads them.
    _detail_loaded: bool = PrivateAttr(default=False)

    @model_validator(mode="before")
    @classmethod
    def _flatten_relations(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        for flat, nested in _NESTED_IDS.items():
            nested_value = data.get(nested)
            if data.get(flat) is None and isinstance(nested_value, dict):
                data[flat] = nested_value.get("id")
        endpoint = data.get("endpoint")
        if data.get("endpoint_name") is None and isinstance(endpoint, dict):
            data["endpoint_name"] = endpoint.get("name")
        # The detail route describes the root operation and its status per span
        # rather than at the top level, where a listing puts them.
        roots = data.get("root_spans")
        root = roots[0] if isinstance(roots, list) and roots else None
        if isinstance(root, dict):
            for field, key in (("root_operation", "span_name"), ("status_code", "status_code")):
                if data.get(field) is None:
                    data[field] = root.get(key)
        # From the root span's status, the way the list route defines it, and
        # deliberately NOT from error_count. error_count counts every failing
        # span, so deriving from it would make has_errors mean one thing on a
        # listed trace and another on the same object once the detail loaded --
        # flipping False to True under a caller who only asked for the spans.
        # A failing span inside an OK trace is what error_count is for.
        if data.get("has_errors") is None and data.get("status_code") is not None:
            data["has_errors"] = data["status_code"] == "ERROR"
        return data

    def _resolve_project_id(self) -> str:
        """The project the detail route needs, which no other entity has to name."""
        project_id = self.project_id or os.getenv("RHESIS_PROJECT_ID")
        if not project_id:
            raise ValueError(
                f"Reading trace {self.trace_id} needs a project id, which this trace "
                "does not carry. Pass project_id to Traces.pull(), or set "
                "RHESIS_PROJECT_ID."
            )
        return project_id

    @handle_http_errors
    def _fetch_detail(self) -> Dict[str, Any]:
        if not self.trace_id:
            raise ValueError("Trace has no trace_id, so there is nothing to read.")
        client = APIClient()
        return client.send_request(
            endpoint=self.endpoint,
            method=Methods.GET,
            url_params=self.trace_id,
            params={"project_id": self._resolve_project_id()},
        )

    def _ensure_detail(self) -> None:
        """Fill in the span tree, which a listing does not carry."""
        if self.root_spans or self._detail_loaded:
            return
        self._merge(self._fetch_detail())

    def _merge(self, payload: Dict[str, Any]) -> None:
        fresh = Trace.model_validate(payload)
        # Apply exactly the fields the response carried, the ones the validator
        # derives included, and leave the rest alone: a listing carries fields
        # the detail route does not, and re-reading must not blank them.
        # Judging by the value instead (skipping None and []) would let a
        # re-pull keep a span tree the server no longer reports.
        for name in fresh.model_fields_set:
            setattr(self, name, getattr(fresh, name))
        self._detail_loaded = True

    def pull(self) -> "Trace":
        """Re-read this trace, including its full span tree."""
        self._detail_loaded = False
        self._merge(self._fetch_detail())
        return self

    @property
    def db_id(self) -> str:
        """The row id of this trace's root span, which is what addresses a trace.

        Annotations, comments, tasks and the platform's own trace URL all take
        this, not the OpenTelemetry ``trace_id``. A trace that came from a
        listing does not carry it, so reading this fetches the detail once.
        """
        self._ensure_detail()
        root = self.root_spans[0] if self.root_spans else None
        if root is None or not root.id:
            raise ValueError(
                f"Trace {self.trace_id} has no root span row id, so there is nothing "
                "to annotate or link to."
            )
        return root.id

    def spans(self, *, name: Optional[str] = None) -> List[Span]:
        """Every span in the trace, depth first, roots included.

        The API returns a tree because that is the shape of a trace, but "find
        the LLM call" is the question people actually have. Pass ``name`` to keep
        only the spans with that operation name.

        This fetches the detail once if the trace came from a listing, and that
        response is the large one: each span carries its attributes and events,
        which hold up to 8000 characters of prompt and completion apiece and up
        to 10000 of conversation input and output on the root. Check
        ``span_count`` before walking the spans of many traces in a loop.
        """
        self._ensure_detail()
        found: List[Span] = []
        stack: List[Span] = list(reversed(self.root_spans))
        while stack:
            span = stack.pop()
            if name is None or span.span_name == name:
                found.append(span)
            stack.extend(reversed(span.children))
        return found

    def span(self, name: str) -> Optional[Span]:
        """The first span with this operation name, depth first, or None."""
        matches = self.spans(name=name)
        return matches[0] if matches else None

    def get_endpoint(self) -> Optional["Endpoint"]:
        """The endpoint this trace ran against, or None if it ran against none."""
        from rhesis.sdk.entities.endpoint import Endpoints as EndpointCollection

        if not self.endpoint_id:
            return None
        return EndpointCollection.pull(id=self.endpoint_id)

    def get_annotations(self) -> List["Annotation"]:
        """Every annotation on this trace, including those on its spans."""
        from rhesis.sdk.entities.annotation import Annotations

        return Annotations.for_trace(self.db_id)

    def annotate(
        self,
        verdict: Union["Verdict", str],
        comment: Optional[str] = None,
        *,
        metric: Optional[str] = None,
        turn: Optional[Union[int, str]] = None,
    ) -> "Annotation":
        """Record a human verdict on this trace, overriding the automated one.

        ``verdict`` is named rather than looked up: ``"pass"`` or ``"fail"``.
        Target one trace metric by name or one turn by label to judge just that
        part; name neither to judge the trace as a whole. Use
        ``trace.span(...).annotate(...)`` to judge one span.

            trace.annotate("fail", "Answered from the wrong document.")
            trace.annotate("pass", "Fine once you read the tool call.", metric="Groundedness")
        """
        from rhesis.sdk.entities.annotation import AnnotatableEntity, Annotations

        return Annotations.create(
            AnnotatableEntity.TRACE,
            self.db_id,
            verdict,
            comment,
            metric=metric,
            turn=turn,
        )

    def push(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NotImplementedError(_NOT_WRITABLE)

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NotImplementedError(_NOT_WRITABLE)


class Traces(BaseCollection):
    endpoint = ENDPOINT
    entity_class = Trace

    @classmethod
    def _paged(
        cls,
        params: Dict[str, Any],
        limit: Optional[int] = None,
        *,
        endpoint: Optional[Endpoints] = None,
        url_params: Optional[str] = None,
    ) -> List[Trace]:
        """Read pages until ``limit`` traces are collected, or the results run out.

        ``limit`` is the most traces to return in total, not the page size the
        route calls by that name. Omit it to read everything the filters match.

        A row the model cannot read raises rather than being skipped. Dropping
        it would hand back a list that is quietly short, which is the same
        failure as stopping at the first page, and the caller would have no way
        to tell. Every field is optional, so this means the route changed shape.
        """
        client = APIClient()
        found: List[Trace] = []
        offset = 0
        while limit is None or len(found) < limit:
            page_size = _PAGE_SIZE if limit is None else min(_PAGE_SIZE, limit - len(found))
            response = (
                client.send_request(
                    endpoint=endpoint or cls.endpoint,
                    method=Methods.GET,
                    url_params=url_params,
                    params={**params, "offset": offset, "limit": page_size},
                )
                or {}
            )
            page = response.get("traces") or []
            found.extend(Trace.model_validate(item) for item in page)
            # A short page is the last one. Without this an empty page would
            # leave the offset where it was and the walk would never end.
            if len(page) < page_size:
                break
            offset += len(page)
            total = response.get("total")
            if isinstance(total, int) and offset >= total:
                break
        return found

    @classmethod
    def query(
        cls,
        *,
        # Scope
        project_id: Optional[str] = None,
        endpoint_id: Optional[str] = None,
        environment: Optional[str] = None,
        # Provenance
        test_run_id: Optional[str] = None,
        test_result_id: Optional[str] = None,
        test_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        trace_source: Optional[Literal["all", "test", "operation"]] = None,
        trace_type: Optional[Literal["all", "Single-Turn", "Multi-Turn"]] = None,
        # What happened
        search: Optional[str] = None,
        span_name: Optional[str] = None,
        status_code: Optional[str] = None,
        trace_metrics_status: Optional[Literal["Pass", "Fail", "Error", "Inconclusive"]] = None,
        provider: Optional[Union[str, Sequence[str]]] = None,
        # When and how long
        start_time_after: Optional[Union[str, datetime]] = None,
        start_time_before: Optional[Union[str, datetime]] = None,
        duration_min_ms: Optional[float] = None,
        duration_max_ms: Optional[float] = None,
        # Shape of the answer
        root_spans_only: Optional[bool] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[Literal["asc", "desc"]] = None,
        limit: Optional[int] = None,
    ) -> List[Trace]:
        """Traces matching the given filters, newest first.

        Every filter the route supports, named, so a wrong one fails at the call
        rather than being ignored server-side. Only the arguments actually passed
        are sent, which leaves the route's own defaults in charge: one entry per
        trace (``root_spans_only``), sorted by start time descending.

            Traces.query(test_run_id=run.id)
            Traces.query(status_code="ERROR", start_time_after="2026-09-01")
            Traces.query(endpoint_id=endpoint.id, duration_min_ms=5000, limit=20)

        A note on scope: with no ``project_id`` and no project on the API token,
        the route returns only traces that belong to no project. Pass
        ``project_id`` if you get an empty list you did not expect.

        ``provider`` matches a trace where any priced call used one of the named
        providers. ``limit`` is the most traces to return in total; omitting it
        reads every page, so on a busy project pass one or filter first.

        These rows carry no spans, which keeps them small. Reading the spans is
        what costs: see ``Trace.spans()``.
        """
        if isinstance(provider, str):
            provider = [provider]
        filters: Dict[str, Any] = {
            "project_id": project_id,
            "endpoint_id": endpoint_id,
            "environment": environment,
            "test_run_id": test_run_id,
            "test_result_id": test_result_id,
            "test_id": test_id,
            "conversation_id": conversation_id,
            "trace_source": trace_source,
            "trace_type": trace_type,
            "search": search,
            "span_name": span_name,
            "status_code": status_code,
            "trace_metrics_status": trace_metrics_status,
            "provider": list(provider) if provider is not None else None,
            "start_time_after": _as_timestamp(start_time_after),
            "start_time_before": _as_timestamp(start_time_before),
            "duration_min_ms": duration_min_ms,
            "duration_max_ms": duration_max_ms,
            "root_spans_only": root_spans_only,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
        # `is not None`, not truthiness: root_spans_only=False and
        # duration_min_ms=0 are real filters, and dropping them as falsy would
        # quietly widen the query instead of failing.
        return cls._paged({k: v for k, v in filters.items() if v is not None}, limit)

    @classmethod
    def all(cls, filter: Optional[str] = None) -> List[Trace]:
        """Every trace in scope, newest first.

        The list route takes named filters rather than OData, so ``filter`` is
        refused instead of being sent and ignored.
        """
        if filter is not None:
            raise ValueError(
                "Traces have no OData filter. Use Traces.query() with named filters, "
                "for example Traces.query(test_run_id=...) or "
                "Traces.query(status_code='ERROR')."
            )
        return cls.query()

    @classmethod
    def first(cls) -> Optional[Trace]:
        """The most recent trace in scope, or None if there are none."""
        found = cls.query(limit=1)
        return found[0] if found else None

    @classmethod
    def pull(cls, trace_id: str, project_id: Optional[str] = None) -> Trace:
        """One trace with its full span tree, by its OpenTelemetry ``trace_id``.

        Unlike every other entity, the route needs the project: pass
        ``project_id`` or set ``RHESIS_PROJECT_ID``. Traces have no names, so
        there is nothing to look one up by.
        """
        trace = Trace(trace_id=trace_id, project_id=project_id)
        trace._merge(trace._fetch_detail())
        return trace

    @classmethod
    def exists(cls, trace_id: str, project_id: Optional[str] = None) -> bool:
        """Whether a trace has been ingested under this ``trace_id``."""
        from rhesis.sdk.clients import HTTPStatus

        try:
            cls.pull(trace_id, project_id=project_id)
            return True
        except RhesisAPIError as error:
            if error.status_code == HTTPStatus.NOT_FOUND:
                return False
            raise

    @classmethod
    def for_test_run(cls, test_run_id: str, limit: Optional[int] = None) -> List[Trace]:
        """The traces one test run produced.

        Uses the run's own route rather than a filtered list, because that one
        resolves the project from the run. Filtering the list by ``test_run_id``
        needs the caller to be scoped to the right project first, and returns an
        empty list rather than an error when they are not.
        """
        return cls._paged(
            {},
            limit,
            endpoint=Endpoints.TEST_RUNS,
            url_params=f"{test_run_id}/traces",
        )

    @classmethod
    def for_test_result(cls, test_result_id: str, limit: Optional[int] = None) -> List[Trace]:
        """The traces one test result produced."""
        return cls.query(test_result_id=test_result_id, limit=limit)

    @classmethod
    @handle_http_errors
    def providers(cls, project_id: Optional[str] = None) -> List[str]:
        """The LLM providers that appear in this scope's traces.

        The values ``query(provider=...)`` matches on, so filtering never has to
        guess at a name. A trace whose provider neither it nor its model name
        identifies is reported as ``"unknown"``, which is itself filterable.
        """
        client = APIClient()
        return (
            client.send_request(
                endpoint=Endpoints.TELEMETRY_PROVIDERS,
                method=Methods.GET,
                params={"project_id": project_id} if project_id else None,
            )
            or []
        )

    @classmethod
    def for_endpoint(cls, endpoint_id: str, limit: Optional[int] = None) -> List[Trace]:
        """Traces recorded against one endpoint."""
        return cls.query(endpoint_id=endpoint_id, limit=limit)

    @classmethod
    def for_conversation(cls, conversation_id: str, limit: Optional[int] = None) -> List[Trace]:
        """Every turn of one multi-turn conversation, as its own trace."""
        return cls.query(conversation_id=conversation_id, limit=limit)

    @classmethod
    def with_errors(cls, limit: Optional[int] = None, **filters: Any) -> List[Trace]:
        """Traces whose root span failed, the starting point for "what broke"."""
        return cls.query(status_code="ERROR", limit=limit, **filters)

    @classmethod
    def slower_than(
        cls, duration_ms: float, limit: Optional[int] = None, **filters: Any
    ) -> List[Trace]:
        """Traces that took longer than ``duration_ms``, slowest first."""
        return cls.query(
            duration_min_ms=duration_ms,
            sort_by="duration_ms",
            sort_order="desc",
            limit=limit,
            **filters,
        )


class Spans(BaseCollection):
    """Spans addressed on their own, by row id.

    This is the way back from a row id to the thing it names. An annotation on a
    trace records the span's row id (``annotation.context.trace_db_id``), and so
    do comments, tasks and the platform's trace URLs, none of which carry the
    OpenTelemetry ``trace_id`` that reads a trace back.

        span_id = annotation.context.trace_db_id
        trace = Spans.trace_for(span_id)

    Spans otherwise come from the trace that holds them, via ``Trace.spans()``.
    """

    endpoint = Endpoints.TELEMETRY_SPANS
    entity_class = Span

    @classmethod
    @handle_http_errors
    def lookup(cls, span_db_id: str) -> Dict[str, Any]:
        """Resolve a span row id to its ``trace_id``, ``project_id`` and ``span_id``.

        The one call that crosses from a row id to the ids the trace routes take.
        Searches the caller's other projects too, so a span in a project other
        than the active one still resolves.
        """
        client = APIClient()
        return client.send_request(
            endpoint=cls.endpoint,
            method=Methods.GET,
            url_params=f"{span_db_id}/lookup",
        )

    @classmethod
    def trace_for(cls, span_db_id: str) -> Trace:
        """The whole trace a span belongs to, given the span's row id."""
        resolved = cls.lookup(span_db_id)
        return Traces.pull(resolved["trace_id"], project_id=resolved.get("project_id"))

    @classmethod
    def pull(cls, span_db_id: str) -> Span:
        """One span by its row id, with its children.

        There is no route that returns a span on its own, so this resolves the
        span's trace and picks it out of the tree.
        """
        trace = cls.trace_for(span_db_id)
        for span in trace.spans():
            if span.id == span_db_id:
                return span
        raise ValueError(
            f"Span {span_db_id} resolved to trace {trace.trace_id}, but is not in that "
            "trace's span tree."
        )

    @classmethod
    @handle_http_errors
    def get_files(cls, span_db_id: str) -> List[Dict[str, Any]]:
        """Files attached to a span, as raw records. ``Span.get_files()`` types them."""
        client = APIClient()
        return (
            client.send_request(
                endpoint=cls.endpoint,
                method=Methods.GET,
                url_params=f"{span_db_id}/files",
            )
            or []
        )

    @classmethod
    def exists(cls, span_db_id: str) -> bool:
        """Whether a span row id resolves to a span the caller can read."""
        from rhesis.sdk.clients import HTTPStatus

        try:
            cls.lookup(span_db_id)
            return True
        except RhesisAPIError as error:
            if error.status_code == HTTPStatus.NOT_FOUND:
                return False
            raise

    @classmethod
    def all(cls, filter: Optional[str] = None) -> NoReturn:
        raise NotImplementedError(
            "Spans cannot be listed on their own. Read them from the trace that "
            "holds them: Traces.pull(trace_id, project_id).spans(). To list every "
            "span as its own row instead of one row per trace, use "
            "Traces.query(root_spans_only=False)."
        )

    @classmethod
    def first(cls) -> NoReturn:
        raise NotImplementedError(
            "Spans cannot be listed on their own, so there is no first one. See "
            "Spans.all() for what to use instead."
        )
