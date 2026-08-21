"""Drift guard: ``id``/``nano_id`` are server-owned and must never be accepted in a request body.

Both values are assigned by the backend (``id`` via the ``gen_random_uuid()`` server default,
``nano_id`` via the python-side default on ``models.base.Base``). Accepting them from a client
lets a caller squat a UUID, inject a predictable short id, or -- on update -- repoint an existing
row's identity.

The structural fix is that ``schemas.base.Base`` carries neither field, because it is inherited by
both write and read schemas. Read schemas opt back in via ``schemas.base.ServerIdentity``. These
tests pin both halves of that arrangement:

1. no request body model exposes ``id``/``nano_id`` (the security invariant, derived from the
   live route table so new endpoints are covered automatically), and
2. the response models whose ``nano_id`` clients actually consume still expose it (the
   regression guard -- dropping it degrades silently rather than erroring, because callers
   fall back to ``nano_id || id``).
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

from rhesis.backend.app import schemas
from rhesis.backend.app.main import app
from rhesis.backend.app.schemas.base import Base, ServerIdentity

SERVER_OWNED_FIELDS = ("id", "nano_id")

# Legitimate exceptions to the "no id/nano_id in a request body" rule:
#
# - FileCreate pre-generates its primary key so the storage path and the
#   ``__file_attached__`` marker in test_output JSONB can embed the id before the row
#   exists (routers/file.py, tasks/execution/executors/results.py). It deliberately
#   derives from BaseModel rather than Base, and carries no nano_id.
# - ExtractToolRequest.id is not an entity primary key at all: it is a caller-supplied
#   reference to an item *inside* an external tool (e.g. a Jira ticket id, a Confluence
#   page id) that the caller wants extracted (routers/tools.py, POST
#   /tools/{tool_id}/extract). The field name collides with our heuristic, not with the
#   thing the heuristic is protecting.
BODY_MODEL_ALLOWLIST = {"FileCreate", "ExtractToolRequest"}

# Response models whose nano_id is read by the frontend or the SDK. Verified consumers:
# frontend detail links and list captions (RunDrawer, TraceDrawer, compare page, explorer
# identifier resolution) and the SDK's metric pull filter.
NANO_ID_RESPONSE_CONTRACT = [
    schemas.Test,
    schemas.TestDetail,
    schemas.TestSet,
    schemas.TestSetDetail,
    schemas.TestRun,
    schemas.TestRunDetail,
    schemas.TestResult,
    schemas.TestResultDetail,
    schemas.Endpoint,
    schemas.EndpointDetail,
    schemas.Metric,
    schemas.MetricDetail,
    schemas.Project,
    schemas.ProjectDetail,
    schemas.Prompt,
    schemas.ModelRead,
    schemas.Task,
    schemas.TaskDetail,
]


def _nested_models(annotation) -> list[type[BaseModel]]:
    """Pull every BaseModel subclass out of an annotation (unwrapping List/Optional/Union)."""
    found, stack = [], [annotation]
    while stack:
        current = stack.pop()
        if isinstance(current, type) and issubclass(current, BaseModel):
            found.append(current)
        stack.extend(getattr(current, "__args__", ()) or ())
    return found


def _request_body_models() -> dict[type[BaseModel], set[str]]:
    """Map each top-level request body model to the routes that accept it.

    Only the top-level body model is inspected. A nested ``id`` is often a legitimate
    reference to an existing row (e.g. ``ExecutionMetric.id`` inside a test set execution
    request), whereas a top-level one would set the identity of the row being written.
    """
    models: dict[type[BaseModel], set[str]] = {}
    for route in app.router.routes:
        if not isinstance(route, APIRoute) or route.body_field is None:
            continue
        annotation = getattr(route.body_field, "type_", None)
        if annotation is None:
            annotation = route.body_field.field_info.annotation
        for model in _nested_models(annotation):
            label = f"{','.join(sorted(route.methods))} {route.path}"
            models.setdefault(model, set()).add(label)
    return models


class TestWriteSchemasRejectServerIdentity:
    """No request body may carry server-owned identity."""

    def test_base_schema_carries_no_identity(self):
        """``Base`` is shared by read and write schemas, so identity must not live on it."""
        for field in SERVER_OWNED_FIELDS:
            assert field not in Base.model_fields, (
                f"schemas.base.Base must not declare {field!r}: every <Entity>Base inherits it, "
                "so the field would leak into every Create/Update payload. Put it on "
                "ServerIdentity and mix that into the response schema instead."
            )

    def test_server_identity_mixin_provides_both_fields(self):
        for field in SERVER_OWNED_FIELDS:
            assert field in ServerIdentity.model_fields

    def test_no_request_body_accepts_server_owned_identity(self):
        """Derived from the live route table, so a new endpoint is covered automatically."""
        offenders: list[str] = []
        for model, routes in sorted(_request_body_models().items(), key=lambda kv: kv[0].__name__):
            if model.__name__ in BODY_MODEL_ALLOWLIST:
                continue
            present = [f for f in SERVER_OWNED_FIELDS if f in model.model_fields]
            if present:
                where = "; ".join(sorted(routes))
                offenders.append(f"{model.__module__}.{model.__name__} accepts {present} ({where})")

        assert not offenders, (
            "These request body schemas accept server-owned identity fields:\n  "
            + "\n  ".join(offenders)
            + "\n\nFix by removing the field from the write schema (do not inherit "
            "ServerIdentity on a Create/Update model). If a pre-generated id is genuinely "
            "required, add the schema to BODY_MODEL_ALLOWLIST with a justification."
        )

    @pytest.mark.parametrize(
        "schema",
        [s for s in dir(schemas) if s.endswith(("Create", "Update"))],
    )
    def test_create_and_update_schemas_have_no_identity(self, schema):
        """Belt-and-braces over the exported schema surface, including unrouted schemas."""
        model = getattr(schemas, schema)
        if not (isinstance(model, type) and issubclass(model, BaseModel)):
            pytest.skip(f"{schema} is not a pydantic model")
        if schema in BODY_MODEL_ALLOWLIST:
            pytest.skip(f"{schema} is an allowlisted pre-generated-id schema")

        present = [f for f in SERVER_OWNED_FIELDS if f in model.model_fields]
        assert not present, f"schemas.{schema} must not accept {present}"


class TestResponseSchemasKeepNanoId:
    """nano_id must stay on the responses that clients read it from."""

    @pytest.mark.parametrize("schema", NANO_ID_RESPONSE_CONTRACT, ids=lambda s: s.__name__)
    def test_response_schema_exposes_nano_id(self, schema):
        assert "nano_id" in schema.model_fields, (
            f"{schema.__name__} lost nano_id. The frontend builds detail links as "
            "`nano_id || id`, so this degrades silently instead of failing. Mix in "
            "schemas.base.ServerIdentity."
        )

    @pytest.mark.parametrize("schema", NANO_ID_RESPONSE_CONTRACT, ids=lambda s: s.__name__)
    def test_response_schema_exposes_id(self, schema):
        assert "id" in schema.model_fields
