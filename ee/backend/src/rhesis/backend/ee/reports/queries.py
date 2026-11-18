"""Read queries for the EE report sections."""

import uuid
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from rhesis.backend.app import models


def requirement_impacts(
    db: Session, requirement_ids: Iterable[uuid.UUID]
) -> Dict[uuid.UUID, Tuple[Optional[uuid.UUID], Optional[str]]]:
    """Each requirement's impact as (lookup id, name); (None, None) when unset.

    A requirement without an impact of its own takes its parent's, the same way a
    parent row adds up its children's results in the requirements table.
    """
    ids = list(requirement_ids)
    if not ids:
        return {}
    parent = aliased(models.Requirement)
    impact = aliased(models.TypeLookup)
    rows = (
        db.query(models.Requirement.id, impact.id, impact.type_value)
        .outerjoin(parent, parent.id == models.Requirement.parent_id)
        .outerjoin(
            impact,
            impact.id == func.coalesce(models.Requirement.impact_id, parent.impact_id),
        )
        .filter(models.Requirement.id.in_(ids))
        .all()
    )
    return {req_id: (impact_id, name) for req_id, impact_id, name in rows}


def users(db: Session, user_ids: Iterable[uuid.UUID]) -> List[models.User]:
    ids = [i for i in set(user_ids) if i is not None]
    if not ids:
        return []
    return db.query(models.User).filter(models.User.id.in_(ids)).all()


def run_executors(db: Session, test_run_ids: Iterable[uuid.UUID]) -> List[uuid.UUID]:
    ids = list(test_run_ids)
    if not ids:
        return []
    rows = db.query(models.TestRun.user_id).filter(models.TestRun.id.in_(ids)).distinct().all()
    return [row[0] for row in rows if row[0] is not None]


def result_reviewers(db: Session, test_result_ids: Iterable[uuid.UUID]) -> List[uuid.UUID]:
    """Who annotated any of the results."""
    ids = list(test_result_ids)
    if not ids:
        return []
    rows = (
        db.query(models.Annotation.user_id)
        .filter(
            models.Annotation.entity_type == "TestResult",
            models.Annotation.entity_id.in_(ids),
        )
        .distinct()
        .all()
    )
    return [row[0] for row in rows if row[0] is not None]


def execution_times_ms(db: Session, test_result_ids: Iterable[uuid.UUID]) -> List[float]:
    ids = list(test_result_ids)
    if not ids:
        return []
    rows = db.query(models.TestResult.test_metrics).filter(models.TestResult.id.in_(ids)).all()
    times = []
    for (metrics,) in rows:
        value = (metrics or {}).get("execution_time")
        if isinstance(value, (int, float)):
            times.append(float(value))
    return times
