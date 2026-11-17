"""Reports: create and edit a draft, show it live, publish it frozen, copy it, export it.

Nothing here commits: the request session does, so a publish, its frozen rows and its
audit entry land together or not at all.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.crud import report as report_crud
from rhesis.backend.app.models.report import REPORT_STATUS_PUBLISHED
from rhesis.backend.app.services.audit_events import record_audit_event
from rhesis.backend.app.services.report.counting import (
    CountedResult,
    RequirementInfo,
    inconsistent_tests,
    pick_counted,
    requirement_tree,
    totals,
)
from rhesis.backend.app.services.report.sections import ReportContext, build_sections
from rhesis.backend.app.services.report.snapshot import endpoint_snapshot, run_hashes, snapshot_hash
from rhesis.backend.app.services.version_info import VERSION_INFO_KEY
from rhesis.backend.app.utils.crud_utils import get_item
from rhesis.backend.events.audit_actions import audit_action
from rhesis.backend.events.types import FieldChange


class ReportError(Exception):
    status_code = 400


class ReportNotFound(ReportError):
    status_code = 404


class ReportConflict(ReportError):
    status_code = 409


def _check_endpoint(db: Session, endpoint_id: uuid.UUID, organization_id: str) -> None:
    if get_item(db, models.Endpoint, endpoint_id, organization_id) is None:
        raise ReportError("Endpoint not found")


def _check_runs(db: Session, endpoint_id: uuid.UUID, test_run_ids: Sequence[uuid.UUID]) -> None:
    endpoints = report_crud.get_run_endpoints(db, test_run_ids)
    missing = [str(i) for i in test_run_ids if i not in endpoints]
    if missing:
        raise ReportError(f"Test runs not found: {', '.join(missing)}")
    others = [str(i) for i, e in endpoints.items() if e != endpoint_id]
    if others:
        raise ReportError(f"Test runs tested a different endpoint: {', '.join(others)}")


def _check_requirements(db: Session, requirement_ids: Sequence[uuid.UUID]) -> None:
    found = {row.id for row in report_crud.get_requirements(db, requirement_ids)}
    missing = [str(i) for i in requirement_ids if i not in found]
    if missing:
        raise ReportError(f"Requirements not found: {', '.join(missing)}")


def load_report(
    db: Session, report_id: uuid.UUID, organization_id: str, user_id: str
) -> models.Report:
    report = report_crud.get_report(db, report_id, organization_id, user_id)
    if report is None:
        raise ReportNotFound("Report not found")
    return report


def load_draft(
    db: Session, report_id: uuid.UUID, organization_id: str, user_id: str
) -> models.Report:
    report = load_report(db, report_id, organization_id, user_id)
    if report.is_published:
        raise ReportConflict("A published report can't be changed. Copy it as a new draft.")
    return report


def create_report(
    db: Session, data: schemas.ReportCreate, organization_id: str, user_id: str
) -> models.Report:
    _check_endpoint(db, data.endpoint_id, organization_id)
    _check_runs(db, data.endpoint_id, data.test_run_ids)
    _check_requirements(db, data.requirement_ids)
    report = report_crud.create_report(db, data, organization_id, user_id)
    report_crud.set_report_test_runs(db, report.id, data.test_run_ids, organization_id, user_id)
    report_crud.set_report_requirements(
        db, report.id, data.requirement_ids, organization_id, user_id
    )
    return load_report(db, report.id, organization_id, user_id)


def update_report(
    db: Session,
    report_id: uuid.UUID,
    data: schemas.ReportUpdate,
    organization_id: str,
    user_id: str,
) -> models.Report:
    report = load_draft(db, report_id, organization_id, user_id)
    if data.test_run_ids is not None:
        _check_runs(db, report.endpoint_id, data.test_run_ids)
        report_crud.set_report_test_runs(db, report.id, data.test_run_ids, organization_id, user_id)
    if data.requirement_ids is not None:
        _check_requirements(db, data.requirement_ids)
        report_crud.set_report_requirements(
            db, report.id, data.requirement_ids, organization_id, user_id
        )
    values = data.model_dump(
        exclude_unset=True, exclude={"test_run_ids", "requirement_ids", "project_id"}
    )
    if values:
        # No user_id: editing a draft doesn't make the editor its author.
        report_crud.update_report(db, report.id, values, organization_id)
    return load_report(db, report.id, organization_id, user_id)


def delete_report(db: Session, report_id: uuid.UUID, organization_id: str, user_id: str) -> None:
    load_draft(db, report_id, organization_id, user_id)
    report_crud.delete_report(db, report_id, organization_id, user_id)


def _requirements(db: Session, requirement_ids: Sequence[uuid.UUID]) -> List[RequirementInfo]:
    return [
        RequirementInfo(id=row.id, name=row.name, parent_id=row.parent_id)
        for row in report_crud.get_requirements(db, requirement_ids)
    ]


def _run_rows(runs: List[models.TestRun], counted: List[CountedResult]) -> List[Dict[str, Any]]:
    per_run: Dict[uuid.UUID, int] = {}
    for result in counted:
        per_run[result.test_run_id] = per_run.get(result.test_run_id, 0) + 1
    return [
        {
            "id": run.id,
            "name": run.name,
            "created_at": run.created_at,
            "user_id": run.user_id,
            "results": per_run.get(run.id, 0),
            "version_info": (run.attributes or {}).get(VERSION_INFO_KEY),
        }
        for run in runs
    ]


def _versions_differ(run_rows: List[Dict[str, Any]]) -> bool:
    versions = {repr(row["version_info"]) for row in run_rows if row["version_info"]}
    return len(versions) > 1


def _compute(db: Session, report: models.Report) -> tuple:
    """Live numbers for a report: (context, metrics)."""
    run_ids = report_crud.get_report_test_run_ids(db, report.id)
    requirement_ids = report_crud.get_report_requirement_ids(db, report.id)
    rows = report_crud.get_results_for_runs(db, run_ids)
    counted = pick_counted(rows, report.result_rule)
    # Only meaningful when more than one result per test is looked at.
    inconsistent = inconsistent_tests(rows) if report.result_rule != "latest" else set()
    tree = requirement_tree(
        _requirements(db, requirement_ids),
        counted,
        report_crud.count_tests_by_requirement(db, requirement_ids),
        inconsistent,
    )
    run_rows = _run_rows(report_crud.get_test_runs(db, run_ids), counted)
    metrics = schemas.ReportMetrics(
        result_rule=report.result_rule,
        totals=totals(counted, tree, inconsistent),
        requirements=tree,
        runs=run_rows,
        versions_differ=_versions_differ(run_rows),
    )
    context = ReportContext(
        report=report,
        test_run_ids=tuple(run_ids),
        requirement_ids=tuple(requirement_ids),
        counted=tuple(counted),
    )
    return context, metrics


def compute_metrics(db: Session, report: models.Report) -> schemas.ReportMetrics:
    """The report's live numbers, whatever its status."""
    return _compute(db, report)[1]


def _organization(db: Session, organization_id: str) -> Optional[models.Organization]:
    return db.get(models.Organization, uuid.UUID(str(organization_id)))


def report_detail(db: Session, report: models.Report, organization_id: str) -> Dict[str, Any]:
    """The report as the page shows it: frozen when published, live while draft."""
    detail = schemas.Report.model_validate(report).model_dump()
    detail["test_run_ids"] = report_crud.get_report_test_run_ids(db, report.id)
    detail["requirement_ids"] = report_crud.get_report_requirement_ids(db, report.id)
    if report.is_published:
        detail["metrics"] = report.metrics
        detail["sections"] = report.sections or {}
        return detail
    context, metrics = _compute(db, report)
    detail["metrics"] = metrics.model_dump(mode="json")
    detail["sections"] = build_sections(
        db, context, _organization(db, organization_id), strict=False
    )
    return detail


def publish_report(
    db: Session, report_id: uuid.UUID, organization_id: str, user_id: str
) -> models.Report:
    report = load_draft(db, report_id, organization_id, user_id)
    context, metrics = _compute(db, report)
    if not context.test_run_ids:
        raise ReportError("Pick at least one test run before publishing")
    sections = build_sections(db, context, _organization(db, organization_id), strict=True)

    report_crud.insert_report_results(
        db,
        [
            {
                "report_id": report.id,
                "organization_id": report.organization_id,
                "project_id": report.project_id,
                "test_id": r.test_id,
                "test_result_id": r.test_result_id,
                "test_run_id": r.test_run_id,
                "requirement_id": r.requirement_id,
                "parent_requirement_id": _parent_of(metrics, r.requirement_id),
                "execution": r.execution,
                "verdict": r.verdict,
                "overridden": r.overridden,
            }
            for r in context.counted
        ],
    )
    published_at = datetime.now(timezone.utc)
    frozen = {
        "report_id": str(report.id),
        "title": report.title,
        "summary": report.summary,
        "recommendation": report.recommendation,
        "published_at": published_at.isoformat(),
        "endpoint": endpoint_snapshot(report.endpoint),
        "metrics": metrics.model_dump(mode="json"),
        "sections": sections,
    }
    digest = snapshot_hash(frozen, context.counted)
    report.status = REPORT_STATUS_PUBLISHED
    report.published_at = published_at
    report.published_by_id = uuid.UUID(str(user_id))
    report.endpoint_snapshot = frozen["endpoint"]
    report.metrics = frozen["metrics"]
    report.sections = sections
    report.snapshot_hash = digest

    record_audit_event(
        audit_action(Permission.Report.PUBLISH),
        organization_id,
        db=db,
        resource_id=report.id,
        resource_label=report.title,
        project_id=report.project_id,
        changes=[
            FieldChange(field="snapshot_hash", kind="value", after=digest),
            FieldChange(field="test_runs", kind="value", after=run_hashes(context.counted)),
        ],
    )
    return load_report(db, report.id, organization_id, user_id)


def _parent_of(metrics: schemas.ReportMetrics, requirement_id: Optional[uuid.UUID]):
    if requirement_id is None:
        return None
    for row in metrics.requirements:
        if row.id == requirement_id:
            return row.parent_id
    return None


def copy_report(
    db: Session, report_id: uuid.UUID, organization_id: str, user_id: str
) -> models.Report:
    """A new draft with the same endpoint, runs, requirements and text."""
    source = load_report(db, report_id, organization_id, user_id)
    data = schemas.ReportCreate(
        title=f"{source.title} (copy)"[:200],
        summary=source.summary,
        recommendation=source.recommendation,
        result_rule=source.result_rule,
        endpoint_id=source.endpoint_id,
        test_run_ids=report_crud.get_report_test_run_ids(db, source.id),
        requirement_ids=report_crud.get_report_requirement_ids(db, source.id),
    )
    return create_report(db, data, organization_id, user_id)


def export_pdf(db: Session, report: models.Report, organization_id: str) -> bytes:
    """The report as a PDF, recorded as an export."""
    # Local import: reportlab loads only when someone exports.
    from rhesis.backend.app.services.report.pdf import render_report_pdf

    detail = report_detail(db, report, organization_id)
    if report.is_published and report.endpoint_snapshot:
        detail["endpoint"] = {"name": report.endpoint_snapshot.get("name")}
    content = render_report_pdf(db, report, detail, _organization(db, organization_id))
    record_export(db, report, organization_id)
    return content


def record_export(db: Session, report: models.Report, organization_id: str) -> None:
    """Note a PDF export in the audit log. A no-op without the audit log (Community)."""
    record_audit_event(
        audit_action(Permission.Report.EXPORT),
        organization_id,
        db=db,
        resource_id=report.id,
        resource_label=report.title,
        project_id=report.project_id,
        changes=[FieldChange(field="snapshot_hash", kind="value", after=report.snapshot_hash)],
    )
