"""CRUD operations for reports, their picked runs and requirements, and frozen results."""

import uuid
from typing import Dict, Iterable, List, Optional

from sqlalchemy import delete, func
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.utils.crud_utils import (
    create_item,
    delete_item,
    get_item_detail,
    get_items_detail,
    update_item,
)
from rhesis.backend.app.utils.query_utils import include

_REPORT_RELATED_FIELDS = [
    include(models.Report.user),
    include(models.Report.endpoint),
    include(models.Report.published_by),
]


def get_report(
    db: Session,
    report_id: uuid.UUID,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[models.Report]:
    return get_item_detail(
        db,
        models.Report,
        report_id,
        organization_id,
        user_id,
        related_fields=_REPORT_RELATED_FIELDS,
    )


def get_reports_detail(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: Optional[str] = None,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> List[models.Report]:
    return get_items_detail(
        db,
        models.Report,
        skip,
        limit,
        sort_by,
        sort_order,
        filter,
        related_fields=_REPORT_RELATED_FIELDS,
        organization_id=organization_id,
        user_id=user_id,
    )


def create_report(
    db: Session,
    report: schemas.ReportCreate,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> models.Report:
    data = report.model_dump(exclude={"test_run_ids", "requirement_ids"})
    return create_item(db, models.Report, data, organization_id, user_id, commit=False)


def update_report(
    db: Session,
    report_id: uuid.UUID,
    values: dict,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[models.Report]:
    return update_item(db, models.Report, report_id, values, organization_id, user_id)


def delete_report(
    db: Session,
    report_id: uuid.UUID,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[models.Report]:
    return delete_item(db, models.Report, report_id, organization_id, user_id)


def _replace_links(
    db: Session,
    link,
    column: str,
    report_id: uuid.UUID,
    ids: Iterable[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> None:
    db.execute(delete(link).where(link.c.report_id == report_id))
    rows = [
        {
            "report_id": report_id,
            column: linked_id,
            "user_id": user_id,
            "organization_id": organization_id,
        }
        for linked_id in dict.fromkeys(ids)
    ]
    if rows:
        db.execute(link.insert(), rows)


def set_report_test_runs(
    db: Session,
    report_id: uuid.UUID,
    test_run_ids: Iterable[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> None:
    _replace_links(
        db,
        models.report_test_run_association,
        "test_run_id",
        report_id,
        test_run_ids,
        organization_id,
        user_id,
    )


def set_report_requirements(
    db: Session,
    report_id: uuid.UUID,
    requirement_ids: Iterable[uuid.UUID],
    organization_id: str,
    user_id: str,
) -> None:
    _replace_links(
        db,
        models.report_requirement_association,
        "requirement_id",
        report_id,
        requirement_ids,
        organization_id,
        user_id,
    )


def get_report_test_run_ids(db: Session, report_id: uuid.UUID) -> List[uuid.UUID]:
    link = models.report_test_run_association
    return [row[0] for row in db.query(link.c.test_run_id).filter(link.c.report_id == report_id)]


def get_report_requirement_ids(db: Session, report_id: uuid.UUID) -> List[uuid.UUID]:
    link = models.report_requirement_association
    return [row[0] for row in db.query(link.c.requirement_id).filter(link.c.report_id == report_id)]


def get_run_endpoints(db: Session, test_run_ids: Iterable[uuid.UUID]) -> Dict[uuid.UUID, uuid.UUID]:
    """Map each existing run to the endpoint it tested."""
    rows = (
        db.query(models.TestRun.id, models.TestConfiguration.endpoint_id)
        .join(
            models.TestConfiguration,
            models.TestConfiguration.id == models.TestRun.test_configuration_id,
        )
        .filter(models.TestRun.id.in_(list(test_run_ids)))
        .all()
    )
    return {run_id: endpoint_id for run_id, endpoint_id in rows}


def get_test_runs(db: Session, test_run_ids: Iterable[uuid.UUID]) -> List[models.TestRun]:
    ids = list(test_run_ids)
    if not ids:
        return []
    return (
        db.query(models.TestRun)
        .filter(models.TestRun.id.in_(ids))
        .order_by(models.TestRun.created_at)
        .all()
    )


def get_results_for_runs(db: Session, test_run_ids: Iterable[uuid.UUID]) -> list:
    """Every result in the runs, with its test's requirement, oldest run first."""
    ids = list(test_run_ids)
    if not ids:
        return []
    return (
        db.query(
            models.TestResult.id,
            models.TestResult.test_id,
            models.TestResult.test_run_id,
            models.TestResult.execution,
            models.TestResult.verdict,
            models.TestResult.status_id,
            models.TestResult.original_status_id,
            models.TestResult.created_at,
            models.Test.requirement_id,
        )
        .join(models.Test, models.Test.id == models.TestResult.test_id)
        .join(models.TestRun, models.TestRun.id == models.TestResult.test_run_id)
        .filter(models.TestResult.test_run_id.in_(ids))
        # "Latest" means from the most recent run; the result's own time breaks a tie.
        .order_by(models.TestRun.created_at, models.TestResult.created_at, models.TestResult.id)
        .all()
    )


def get_requirements(db: Session, requirement_ids: Iterable[uuid.UUID]) -> list:
    ids = list(requirement_ids)
    if not ids:
        return []
    return (
        db.query(models.Requirement.id, models.Requirement.name, models.Requirement.parent_id)
        .filter(models.Requirement.id.in_(ids))
        .all()
    )


def count_tests_by_requirement(
    db: Session, requirement_ids: Iterable[uuid.UUID]
) -> Dict[uuid.UUID, int]:
    ids = list(requirement_ids)
    if not ids:
        return {}
    rows = (
        db.query(models.Test.requirement_id, func.count(models.Test.id))
        .filter(models.Test.requirement_id.in_(ids))
        .group_by(models.Test.requirement_id)
        .all()
    )
    return {requirement_id: count for requirement_id, count in rows}


def insert_report_results(db: Session, rows: List[dict]) -> None:
    if rows:
        db.bulk_insert_mappings(models.ReportResult, rows)
