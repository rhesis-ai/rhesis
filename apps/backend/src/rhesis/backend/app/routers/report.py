import uuid
from typing import List
from urllib.parse import quote

from fastapi import Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.constants import REPORT_RESOURCE_NAME, REPORT_ROUTE_PREFIX, REPORT_TAG
from rhesis.backend.app.crud import report as report_crud
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.error_handlers import internal_error
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.services.report import service as report_service
from rhesis.backend.app.services.report.service import ReportError
from rhesis.backend.app.services.report.summary import (
    ReportSummaryAnswer,
    SummaryUnavailable,
    draft_summary,
)
from rhesis.backend.app.utils.decorators import with_count_header

router = RhesisRouter(
    prefix=REPORT_ROUTE_PREFIX,
    tags=[REPORT_TAG],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
    resource=REPORT_RESOURCE_NAME,
)


def _http(error: ReportError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=str(error))


@router.post("/", response_model=schemas.Report)
def create_report(
    report: schemas.ReportCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    organization_id, user_id = tenant_context
    try:
        return report_service.create_report(db, report, organization_id, user_id)
    except ReportError as e:
        raise _http(e) from e


@router.get("/", response_model=List[schemas.Report])
@with_count_header(model=models.Report)
def read_reports(
    response: Response,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    organization_id, user_id = tenant_context
    return report_crud.get_reports_detail(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.get("/{report_id}", response_model=schemas.ReportDetail)
def read_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """The report with its numbers: frozen when published, live while draft."""
    organization_id, user_id = tenant_context
    try:
        report = report_service.load_report(db, report_id, organization_id, user_id)
    except ReportError as e:
        raise _http(e) from e
    return report_service.report_detail(db, report, organization_id)


@router.put("/{report_id}", response_model=schemas.Report)
def update_report(
    report_id: uuid.UUID,
    report: schemas.ReportUpdate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    organization_id, user_id = tenant_context
    try:
        return report_service.update_report(db, report_id, report, organization_id, user_id)
    except ReportError as e:
        raise _http(e) from e


@router.delete("/{report_id}")
def delete_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """Delete a draft. A published report is the lasting record and can't be deleted."""
    organization_id, user_id = tenant_context
    try:
        report_service.delete_report(db, report_id, organization_id, user_id)
    except ReportError as e:
        raise _http(e) from e
    return {"status": "success", "message": "Report deleted"}


@router.post(
    "/{report_id}/publish",
    response_model=schemas.Report,
    **capability(Permission.Report.PUBLISH),
)
def publish_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """Freeze the numbers, the counted results and the endpoint config, and hash them."""
    organization_id, user_id = tenant_context
    try:
        return report_service.publish_report(db, report_id, organization_id, user_id)
    except ReportError as e:
        raise _http(e) from e


@router.post(
    "/{report_id}/copy",
    response_model=schemas.Report,
    **capability(Permission.Report.CREATE),
)
def copy_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """Start a new draft with the same endpoint, runs, requirements and text."""
    organization_id, user_id = tenant_context
    try:
        return report_service.copy_report(db, report_id, organization_id, user_id)
    except ReportError as e:
        raise _http(e) from e


@router.post(
    "/{report_id}/summary",
    response_model=ReportSummaryAnswer,
    **capability(Permission.Report.UPDATE),
)
def draft_report_summary(
    report_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Ask the generation model for a summary draft. Not saved: the author edits it first."""
    organization_id, user_id = tenant_context
    try:
        report = report_service.load_draft(db, report_id, organization_id, user_id)
    except ReportError as e:
        raise _http(e) from e
    try:
        return draft_summary(db, report, current_user)
    except SummaryUnavailable as e:
        raise internal_error(
            e,
            context=f"drafting the summary of report {report_id}",
            status_code=502,
            public_detail=(
                "Failed to draft the summary: the generation model could not be used. "
                "Check the model configured for your organization."
            ),
        ) from e


@router.get("/{report_id}/pdf", **capability(Permission.Report.EXPORT))
def export_report_pdf(
    report_id: uuid.UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    """The report as a PDF: frozen for a published report, marked DRAFT otherwise.
    Each download is recorded as report.exported."""
    organization_id, user_id = tenant_context
    try:
        report = report_service.load_report(db, report_id, organization_id, user_id)
    except ReportError as e:
        raise _http(e) from e
    content = report_service.export_pdf(db, report, organization_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": _pdf_disposition(report.title)},
    )


def _pdf_disposition(title: str) -> str:
    """An ASCII filename for old clients plus the real title as UTF-8 (RFC 6266), since
    a header that isn't Latin-1 can't be sent at all."""
    name = "-".join(title.split())[:80] or "report"
    ascii_name = "".join(c if c.isascii() and (c.isalnum() or c in "-_.") else "_" for c in name)
    if not ascii_name.strip("_"):
        ascii_name = "report"
    # safe="": a "/" in the title must not reach the file name.
    utf8_name = quote(name + ".pdf", safe="")
    return f"attachment; filename=\"{ascii_name}.pdf\"; filename*=UTF-8''{utf8_name}"
