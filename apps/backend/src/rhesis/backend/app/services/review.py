"""Shared helpers for JSONB review sub-resource routes.

Both the test_result and telemetry routers carry JSONB review sub-documents
with identical ownership, metadata, and affordance patterns.  Centralised here
so the two routers stay thin and the owner-resolution / authorization pattern
is not duplicated.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.auth.rbac import authorize_object

if TYPE_CHECKING:
    from rhesis.backend.app.models.user import User


def get_review_status_details(db: Session, status_id: UUID, organization_id: str) -> dict:
    """Fetch status details for a review, raising HTTP 404 if not found."""
    status_obj = (
        db.query(models.Status)
        .filter(models.Status.id == status_id, models.Status.organization_id == organization_id)
        .first()
    )
    if not status_obj:
        raise HTTPException(status_code=404, detail="Status not found")
    return {"status_id": str(status_obj.id), "name": status_obj.name}


def update_review_metadata(reviews_data: dict, current_user: "User", latest_status: dict) -> None:
    """Overwrite the ``metadata`` key of a reviews JSONB blob with current state."""
    now = datetime.now(timezone.utc).isoformat()
    reviews_data["metadata"] = {
        "last_updated_at": now,
        "last_updated_by": {
            "user_id": str(current_user.id),
            "name": current_user.name or current_user.email,
        },
        "total_reviews": len(reviews_data.get("reviews", [])),
        "latest_status": latest_status,
        "summary": f"Last updated by {current_user.name or current_user.email}",
    }


def resolve_review_owner_uuid(review: dict) -> Optional[UUID]:
    """Parse ``review["user"]["user_id"]`` to a UUID.

    Returns ``None`` when the field is absent, empty, or not a valid UUID.
    """
    raw_uid = review.get("user", {}).get("user_id")
    if not raw_uid:
        return None
    try:
        return UUID(str(raw_uid))
    except (ValueError, AttributeError):
        return None


ENTITY_REVIEW_TARGET_TYPES = ("test_result", "test")


def classify_test_result_review_counts(
    test_reviews,
    status_id,
) -> tuple[bool, bool]:
    """Classify a test result's review state for run-level aggregation.

    Returns ``(is_reviewed, is_corrected)`` where:

    - *is_reviewed* is ``True`` when the result has any human review entry
      (entity-level or metric-level).
    - *is_corrected* is ``True`` when the latest entity-level review verdict
      differs from the automated ``status_id`` (``matches_review`` is false).
    """
    if not test_reviews or not isinstance(test_reviews, dict):
        return False, False

    reviews = test_reviews.get("reviews")
    if not reviews or not isinstance(reviews, list):
        return False, False

    is_reviewed = len(reviews) > 0

    entity_level = []
    for review in reviews:
        if not isinstance(review, dict):
            continue
        target = review.get("target") or {}
        raw_type = target.get("type", "test_result")
        if raw_type in ENTITY_REVIEW_TARGET_TYPES:
            entity_level.append(review)

    if not entity_level:
        return is_reviewed, False

    last_review = max(
        entity_level,
        key=lambda r: r.get("updated_at") or r.get("created_at") or "",
    )
    review_status = last_review.get("status") or {}
    review_status_id = review_status.get("status_id")
    if not review_status_id or not status_id:
        return is_reviewed, False

    is_corrected = str(review_status_id) != str(status_id)
    return is_reviewed, is_corrected


def authorize_review_action(
    principal: object,
    review: dict,
    permission: "str | Permission",
    *,
    project_id: Optional[UUID],
    db: Session,
) -> bool:
    """Return ``True`` iff *principal* holds *permission* on the review's owner.

    Wraps :func:`~rhesis.backend.app.auth.rbac.authorize_object` with the
    review-dict ownership extraction so callers do not repeat the
    ``SimpleNamespace`` shim pattern.

    Usage::

        if not authorize_review_action(
            principal, review_dict, Permission.TestResult.UPDATE_OWN,
            project_id=project_id, db=db,
        ):
            raise HTTPException(403, "Not authorized to update this review")
    """
    owner_uuid = resolve_review_owner_uuid(review)
    return authorize_object(
        principal,
        permission,
        SimpleNamespace(user_id=owner_uuid),
        project_id=project_id,
        db=db,
    )
