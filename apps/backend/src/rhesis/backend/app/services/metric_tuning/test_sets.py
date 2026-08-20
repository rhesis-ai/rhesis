"""Lifecycle of a metric's tuning test set.

The set is created lazily, on the first case added, so a ``GET`` stays free of
side effects and metrics nobody tunes never accumulate empty test sets.

It carries no metric of its own, permanently. Comparing a metric's verdict
against the human's expected one is plain code, not a metric resolved through the
execution path (domain.local/adr/0004), so nothing is waiting to be attached
here. An earlier design put a placeholder metric in the slot to hold it open for
exactly that, which cost a user-visible metric row that computed nothing.
"""

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.constants import TestSetType
from rhesis.backend.app.crud import create_test_set
from rhesis.backend.app.crud import metric_tuning as crud_metric_tuning
from rhesis.backend.app.utils.crud_utils import get_or_create_type_lookup

logger = logging.getLogger(__name__)


def get_tuning_test_set(
    db: Session, metric_id: uuid.UUID, organization_id: str
) -> Optional[models.TestSet]:
    """The metric's tuning test set, or None when it has none yet."""
    return crud_metric_tuning.get_tuning_test_set(db, metric_id, organization_id)


def get_or_create_tuning_test_set(
    db: Session,
    metric: models.Metric,
    organization_id: str,
    user_id: str,
) -> models.TestSet:
    """Return the metric's tuning test set, creating it on first use.

    Follows ``services/explorer/tests.py::create_explorer_test_set``: build a
    plain ``TestSetCreate``, then stamp the ownership column server-side, since
    a client-settable one would let anyone hide a test set.

    Hardcodes Single-Turn. A tuning case is one (input, output) pair being
    judged, which is exactly the single-turn shape.

    The name tracks the metric's name at creation time and is never updated. The
    set is not displayed anywhere, so the name drifting after a rename has no
    visible effect.
    """
    existing = crud_metric_tuning.get_tuning_test_set(db, metric.id, organization_id)
    if existing:
        return existing

    test_set_type_lookup = get_or_create_type_lookup(
        db=db,
        type_name="TestType",
        type_value=TestSetType.SINGLE_TURN.value,
        organization_id=organization_id,
        user_id=user_id,
    )

    test_set_data = schemas.TestSetCreate(
        name=f"{metric.name} — Tuning",
        description=(
            f"Labelled cases for tuning the {metric.name} metric. "
            "Managed from the metric's Tuning tab."
        ),
        test_set_type_id=test_set_type_lookup.id,
    )
    test_set = create_test_set(
        db=db,
        test_set=test_set_data,
        organization_id=organization_id,
        user_id=user_id,
    )
    test_set = crud_metric_tuning.mark_test_set_as_tuning(db, test_set, metric.id)

    logger.info("Created tuning test set %s for metric %s", test_set.id, metric.id)
    return test_set
