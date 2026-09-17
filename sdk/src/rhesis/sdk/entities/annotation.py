from __future__ import annotations

from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel

from rhesis.sdk.clients import APIClient, Endpoints, Methods
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity, handle_http_errors
from rhesis.sdk.entities.status import Status

ENDPOINT = Endpoints.ANNOTATIONS

# One page of the entity-scoped route. Paging continues past this, so a parent
# with more annotations than the page size is read whole rather than truncated.
_PAGE_SIZE = 100


class AnnotatableEntity(str, Enum):
    """What an annotation can be attached to.

    A ``str`` enum so the plain strings keep working: ``entity_type="TestResult"``
    and ``entity_type=AnnotatableEntity.TEST_RESULT`` are the same value.
    """

    TEST_RESULT = "TestResult"
    TRACE = "Trace"
    TEST = "Test"

    # Without this, str() and f-strings render "AnnotatableEntity.TEST_RESULT"
    # rather than the value, which would put that in a URL and a request body.
    __str__ = str.__str__


class Verdict(str, Enum):
    """The verdicts a caller can name instead of resolving a status id."""

    PASS = "pass"
    FAIL = "fail"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

    __str__ = str.__str__


# Each verdict is a status row, and which one depends on the entity type it is
# filed under: Pass/Fail are the ones every organization already has for results,
# while metric tuning has its own pair. Resolving on the name alone would break the
# day a second entity type gets a status called "Fail".
_VERDICT_STATUS = {
    Verdict.PASS: ("Pass", "TestResult"),
    Verdict.FAIL: ("Fail", "TestResult"),
    Verdict.ACCEPTED: ("Accepted", "Annotation"),
    Verdict.REJECTED: ("Rejected", "Annotation"),
}

# Verdict -> status id, filled on first use. Statuses are per organization and
# seeded once, so this saves a lookup per annotation in a loop.
_verdict_cache: Dict[Verdict, str] = {}


def resolve_verdict(verdict: str) -> str:
    """The status id for a named verdict, e.g. ``"fail"``.

    Cached per process. Raises ``ValueError`` for an unknown name, listing the
    ones that exist, and for a verdict the organization has no status row for.
    """
    try:
        key = Verdict(str(verdict).strip().lower())
    except ValueError:
        known = ", ".join(v.value for v in Verdict)
        raise ValueError(f"Unknown verdict {verdict!r}. Expected one of: {known}") from None

    if key in _verdict_cache:
        return _verdict_cache[key]

    name, entity_type = _VERDICT_STATUS[key]
    response = APIClient().send_request(
        endpoint=Endpoints.STATUSES,
        method=Methods.GET,
        params={"entity_type": entity_type, "$filter": f"name eq '{name}'"},
    )
    for row in response or []:
        if str(row.get("name", "")).strip().lower() == name.lower():
            _verdict_cache[key] = row["id"]
            return row["id"]

    raise ValueError(
        f"No '{name}' status exists for entity type '{entity_type}' in this organization."
    )


class AnnotationUser(BaseModel):
    """Who wrote or resolved an annotation."""

    id: Optional[str] = None
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None


class AnnotationContext(BaseModel):
    """Where the annotated entity sits, so a caller can link back to it.

    `trace_db_id` is the span's row id and `trace_id` the OTEL hex; only the
    former addresses a trace page.
    """

    project_id: Optional[str] = None
    test_run_id: Optional[str] = None
    test_run_name: Optional[str] = None
    test_set_id: Optional[str] = None
    test_result_id: Optional[str] = None
    requirement_id: Optional[str] = None
    requirement_name: Optional[str] = None
    trace_id: Optional[str] = None
    trace_db_id: Optional[str] = None
    span_name: Optional[str] = None


class Annotation(BaseEntity):
    """A human judgement on a test result, a trace or a test.

    Annotations are their own entity, linked to a parent by
    ``(entity_type, entity_id)``. A Pass/Fail verdict on a TestResult or Trace
    overrides that parent's automated outcome, so creating one is a write
    against the parent as much as against the annotation.

    ``target_type`` / ``target_reference`` say what within the parent is being
    judged: the entity itself, one ``metric`` by name, or one ``turn``. Leave
    them unset for an entity-level judgement and the backend fills in the right
    entity-level target for the parent type.
    """

    endpoint: ClassVar[Endpoints] = ENDPOINT
    _push_required_fields: ClassVar[tuple[str, ...]] = ("entity_type", "entity_id", "status_id")
    # Server-owned or absent from the write schemas; dropped before a push so
    # the body says only what a caller may actually set.
    _read_only_fields: ClassVar[tuple[str, ...]] = (
        "status",
        "user_id",
        "user",
        "resolved_at",
        "resolved_by_id",
        "resolved_by",
        "created_at",
        "updated_at",
        "context",
    )
    # Fixed at creation: an annotation cannot be re-parented.
    _create_only_fields: ClassVar[tuple[str, ...]] = ("entity_type", "entity_id")

    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    target_type: Optional[str] = None
    target_reference: Optional[str] = None
    status_id: Optional[str] = None
    status: Optional[Status] = None
    comments: Optional[str] = None
    resolved: Optional[bool] = None
    attributes: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    user: Optional[AnnotationUser] = None
    resolved_at: Optional[str] = None
    resolved_by_id: Optional[str] = None
    resolved_by: Optional[AnnotationUser] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # Populated by the list and entity routes, absent on a plain get.
    context: Optional[AnnotationContext] = None
    id: Optional[str] = None

    @handle_http_errors
    def push(self) -> Optional[Dict[str, Any]]:
        """Save the annotation.

        Responses carry the target flat as ``target_type`` / ``target_reference``,
        but the write endpoints take it nested under ``target``. Sending the flat
        pair would be accepted and silently ignored, leaving an annotation
        targeted at the whole entity rather than the metric or turn it named, so
        the remap happens here rather than at each call site.

        The parent and the verdict are required to create, not to update, so
        ``Annotation(id=..., resolved=True).push()`` resolves one by id without
        hydrating the rest of it first.
        """
        data = self.model_dump(mode="json", exclude_none=True)
        if self.id is None:
            self._validate_push_requirements()

        target_type = data.pop("target_type", None)
        data.pop("target_reference", None)
        if target_type is not None:
            data["target"] = {"type": target_type, "reference": self.target_reference}

        for field in self._read_only_fields:
            data.pop(field, None)

        entity_id = data.pop("id", None)
        data.pop("nano_id", None)

        if entity_id is not None:
            for field in self._create_only_fields:
                data.pop(field, None)
            response = self._update(entity_id, data)
        else:
            response = self._create(data)
            self.id = response["id"]

        return response

    def resolve(self) -> "Annotation":
        """Close this annotation, the disagreement having been handled."""
        return self._set_resolved(True)

    def reopen(self) -> "Annotation":
        """Reopen this annotation, it needing attention again."""
        return self._set_resolved(False)

    def _set_resolved(self, resolved: bool) -> "Annotation":
        if not self.id:
            raise ValueError("Annotation must have an id to resolve or reopen")
        # Sent as its own update rather than by pushing the whole object, so this
        # cannot carry along an edit the caller made to a field by accident.
        Annotation(id=self.id, resolved=resolved).push()
        self.resolved = resolved
        return self


class Annotations(BaseCollection):
    endpoint = ENDPOINT
    entity_class = Annotation

    @classmethod
    def _paged(cls, url_params: Optional[str], params: Dict[str, Any]) -> List[Annotation]:
        """Read every page, since a silent first-page truncation is worse than a second call."""
        client = APIClient()
        found: List[Annotation] = []
        skip = 0
        while True:
            response = client.send_request(
                endpoint=cls.endpoint,
                method=Methods.GET,
                url_params=url_params,
                params={**params, "skip": skip, "limit": _PAGE_SIZE},
            )
            page = response or []
            found.extend(Annotation.model_validate(item) for item in page)
            if len(page) < _PAGE_SIZE:
                return found
            skip += _PAGE_SIZE

    @classmethod
    def create(
        cls,
        entity_type: str,
        entity_id: str,
        verdict: str,
        comment: Optional[str] = None,
        *,
        metric: Optional[str] = None,
        turn: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Annotation:
        """Record a judgement, naming the verdict rather than resolving a status id.

        The generic form of ``TestResult.annotate`` and ``Test.annotate``, for a
        parent with no entity class of its own -- a trace, addressed by its span
        row id (``context.trace_db_id``, not the OTEL hex).

        ``metric`` and ``turn`` are mutually exclusive: an annotation judges one
        thing. Naming neither judges the parent as a whole.
        """
        if metric and turn:
            raise ValueError("An annotation targets a metric or a turn, not both")

        target_type = "metric" if metric else "turn" if turn else None
        annotation = Annotation(
            entity_type=str(entity_type),
            entity_id=str(entity_id),
            status_id=resolve_verdict(verdict),
            comments=comment,
            target_type=target_type,
            target_reference=metric or turn,
            attributes=attributes,
        )
        annotation.push()
        return annotation

    @classmethod
    def for_trace(cls, trace_db_id: str) -> List[Annotation]:
        """Every annotation on one trace.

        ``trace_db_id`` is the span's row id, which is what addresses a trace --
        the OTEL hex ``trace_id`` does not.
        """
        return cls.for_entity(AnnotatableEntity.TRACE, trace_db_id)

    @classmethod
    def for_entity(cls, entity_type: str, entity_id: str) -> List[Annotation]:
        """Every annotation on one parent.

        Uses the entity-scoped route rather than a filter over the whole list,
        which is what the UI panels read.
        """
        return cls._paged(f"entity/{entity_type}/{entity_id}", {})

    @classmethod
    def for_test_run(cls, test_run_id: str) -> List[Annotation]:
        """Every annotation left anywhere in a test run, newest first.

        Covers the run's test results and the traces it produced, which is why
        it is a server-side parameter rather than a client-side join.
        """
        return cls._paged(
            None, {"test_run_id": test_run_id, "sort_by": "updated_at", "sort_order": "desc"}
        )

    @classmethod
    def for_test_set(cls, test_set_id: str) -> List[Annotation]:
        """Every annotation whose parent ran under the given test set."""
        return cls._paged(
            None, {"test_set_id": test_set_id, "sort_by": "updated_at", "sort_order": "desc"}
        )

    @classmethod
    def for_endpoint(cls, endpoint_id: str) -> List[Annotation]:
        """Every annotation whose parent ran against the given endpoint."""
        return cls._paged(
            None, {"endpoint_id": endpoint_id, "sort_by": "updated_at", "sort_order": "desc"}
        )

    @classmethod
    def for_metric(cls, metric_name: str) -> List[Annotation]:
        """Annotations targeting a specific metric by name (case-insensitive)."""
        return cls._paged(
            None, {"metric": metric_name, "sort_by": "updated_at", "sort_order": "desc"}
        )

    @classmethod
    def for_annotator(cls, annotator_id: str) -> List[Annotation]:
        """Annotations created by a specific user."""
        return cls._paged(
            None, {"annotator_id": annotator_id, "sort_by": "updated_at", "sort_order": "desc"}
        )

    @classmethod
    def for_requirement(cls, requirement_id: str) -> List[Annotation]:
        """Annotations on test results linked to a specific requirement."""
        return cls._paged(
            None, {"requirement_id": requirement_id, "sort_by": "updated_at", "sort_order": "desc"}
        )

    @classmethod
    def for_date_range(
        cls, date_from: Optional[str] = None, date_to: Optional[str] = None
    ) -> List[Annotation]:
        """Annotations updated within a date range (ISO date strings, e.g. '2026-01-15')."""
        params: Dict[str, Any] = {"sort_by": "updated_at", "sort_order": "desc"}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return cls._paged(None, params)
