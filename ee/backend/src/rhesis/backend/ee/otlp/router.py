"""OTLP/HTTP trace ingest: ``POST /telemetry/v1/traces`` (Enterprise).

Lets an agent instrumented with the OpenTelemetry GenAI semantic conventions
send traces with any standard OTLP exporter (OTel Collector, Grafana Alloy, an
SDK's ``OTLPSpanExporter``) pointed at ``https://<api host>/telemetry``.

The request is admitted, decoded and translated, then queued; a worker stores
it through the same path as ``POST /telemetry/traces``.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import Depends, Request, Response

from rhesis.backend.app.auth.feature_gates import require_feature
from rhesis.backend.app.auth.quota_gates import require_backstop
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.config.settings import TraceIngestSettings
from rhesis.backend.app.dependencies import (
    get_project_context,
    get_tenant_context,
)
from rhesis.backend.app.features import FeatureName
from rhesis.backend.app.models.user import User
from rhesis.backend.app.quota import QuotaResource
from rhesis.backend.app.routers import telemetry_intake as intake
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.services.telemetry.admission import IngestRejected
from rhesis.backend.app.services.telemetry.ingest import (
    IngestJob,
    TooManySpans,
    apply_span_limits,
)
from rhesis.backend.app.utils.rate_limit import limiter
from rhesis.backend.ee.otlp.conversation_join import PRE_STORE_HOOK
from rhesis.backend.ee.otlp.decode import (
    OTLPDecodeError,
    OTLPEncoding,
    OTLPPayloadTooLarge,
    OTLPUnsupportedMediaType,
    decompress,
    encoding_for,
    parse_request,
)
from rhesis.backend.ee.otlp.responses import error_response, export_response
from rhesis.backend.ee.otlp.translate import TranslatedRequest, translate_request
from rhesis.telemetry.schemas import OTELSpan

logger = logging.getLogger(__name__)


def _request_encoding(request: Request) -> OTLPEncoding:
    try:
        return encoding_for(request.headers.get("content-type"))
    except OTLPUnsupportedMediaType:
        return OTLPEncoding.PROTOBUF


# Errors raised before or around the handler (auth, feature gate, quota backstop)
# are rewritten as OTLP statuses by OTLPErrorMiddleware.
router = RhesisRouter(prefix="/telemetry", tags=["telemetry"], resource="telemetry")


class OTLPBadRequest(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def _decode(
    body: bytes, content_type: Optional[str], content_encoding: Optional[str], limits
) -> tuple[bytes, OTLPEncoding]:
    """The decompressed payload and its encoding. Raises :class:`OTLPBadRequest`."""
    try:
        encoding = encoding_for(content_type)
        return decompress(body, content_encoding, limits.max_decompressed_bytes), encoding
    except OTLPUnsupportedMediaType as exc:
        raise OTLPBadRequest(415, str(exc)) from exc
    except OTLPPayloadTooLarge as exc:
        raise OTLPBadRequest(413, str(exc)) from exc
    except OTLPDecodeError as exc:
        raise OTLPBadRequest(400, str(exc)) from exc


def _translate(raw: bytes, encoding: OTLPEncoding, limits) -> TranslatedRequest:
    try:
        request = parse_request(raw, encoding)
    except OTLPDecodeError as exc:
        raise OTLPBadRequest(400, str(exc)) from exc
    translated = translate_request(request)
    try:
        apply_span_limits(translated.spans, limits)
    except TooManySpans as exc:
        raise OTLPBadRequest(413, str(exc)) from exc
    return translated


def _group_by_project(
    spans: List[OTELSpan], fixed_project_id: Optional[str]
) -> Dict[Optional[str], List[OTELSpan]]:
    """Token or header scope wins; otherwise each resource's ``rhesis.project_id``."""
    groups: Dict[Optional[str], List[OTELSpan]] = defaultdict(list)
    for span in spans:
        groups[fixed_project_id or span.project_id].append(span)
    return groups


def _jobs(
    request: Request,
    current_user: User,
    tenant_context,
    spans: List[OTELSpan],
    scope_project_id: Optional[str],
) -> List[IngestJob]:
    """One job per project, each access-checked. Raises :class:`OTLPBadRequest` or 403."""
    organization_id, user_id = tenant_context
    groups = _group_by_project(spans, scope_project_id)
    if None in groups:
        raise OTLPBadRequest(
            400,
            "No project could be resolved. Use a project-scoped token, send an "
            "X-Project-Id header, or set the resource attribute rhesis.project_id.",
        )
    jobs = []
    for project_id, project_spans in groups.items():
        if project_id != scope_project_id:
            project_id = intake.check_project_access(request, current_user, project_id)
        jobs.append(
            IngestJob(
                project_spans,
                organization_id,
                user_id,
                str(project_id),
                pre_store_hooks=[PRE_STORE_HOOK],
            )
        )
    return jobs


async def _ingest(
    request: Request,
    current_user: User,
    tenant_context,
    scope_project_id: Optional[str],
    limits: TraceIngestSettings,
) -> Response:
    async with intake.admitted(tenant_context[0], request, limits) as (body, slot):
        raw, encoding = await intake.in_thread(
            _decode,
            body,
            request.headers.get("content-type"),
            request.headers.get("content-encoding"),
            limits,
        )
        if raw is not body:
            slot.add(len(raw))
        translated = await intake.in_thread(_translate, raw, encoding, limits)
        del raw
        jobs = await intake.in_thread(
            _jobs, request, current_user, tenant_context, translated.spans, scope_project_id
        )
        for job in jobs:
            await intake.enqueue(job, limits)

    logger.info(
        f"OTLP TRACE INGESTION | spans={len(translated.spans)} | rejected={translated.rejected} | "
        f"projects={len(jobs)} | org={tenant_context[0]} | queued"
    )
    return export_response(encoding, translated.rejected, "; ".join(translated.errors))


@router.post(
    "/v1/traces",
    response_class=Response,
    summary="Ingest traces over OTLP/HTTP",
    responses={
        200: {"description": "ExportTraceServiceResponse (partial_success when spans dropped)"},
        400: {"description": "Undecodable payload or no project"},
        413: {"description": "Body or span count over the limit"},
        415: {"description": "Neither application/x-protobuf nor application/json"},
        429: {"description": "Rate limit or tracing backstop reached; retry after Retry-After"},
        503: {"description": "Ingest busy or unavailable; retry after Retry-After"},
    },
)
# Metered by the tracing quota and the ingest limits instead of the default limit.
@limiter.exempt
async def ingest_otlp_traces(
    request: Request,
    tenant_context=Depends(get_tenant_context),
    scope_project_id: Optional[str] = Depends(get_project_context),
    current_user: User = Depends(require_current_user_or_token),
    _feature=Depends(require_feature(FeatureName.OTLP_INGEST)),
    _backstop: None = Depends(require_backstop(QuotaResource.TRACING_SPANS)),
) -> Response:
    """Accept an OTLP ``ExportTraceServiceRequest`` (protobuf or JSON, optionally gzip).

    Spans following the OpenTelemetry GenAI semantic conventions are translated
    into the Rhesis trace model and queued for storage. Project: the token's
    scope, else ``X-Project-Id``, else the resource attribute ``rhesis.project_id``.
    """
    limits = intake.settings()
    try:
        return await _ingest(request, current_user, tenant_context, scope_project_id, limits)
    except IngestRejected as exc:
        rejection = exc.rejection
        retry_after = rejection.retry_after if rejection.status_code != 413 else None
        return error_response(
            rejection.status_code, rejection.message, _request_encoding(request), retry_after
        )
    except OTLPBadRequest as exc:
        return error_response(exc.status_code, str(exc), _request_encoding(request))
