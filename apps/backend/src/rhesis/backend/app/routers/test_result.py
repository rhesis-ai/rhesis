from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app import models, schemas
from rhesis.backend.app.auth.affordances import populate_review_permitted_actions
from rhesis.backend.app.auth.capabilities import Permission
from rhesis.backend.app.auth.principal import resolve_principal_from_request
from rhesis.backend.app.auth.rbac import authorize_object, project_id_from_scope
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.crud import file as file_crud
from rhesis.backend.app.crud import test_result as test_result_crud
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.services.review import (
    apply_review_resolved,
    authorize_review_action,
    get_review_status_details,
    update_review_metadata,
)
from rhesis.backend.app.services.review_override import (
    apply_review_override,
    revert_override,
)
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.app.utils.decorators import with_count_header
from rhesis.backend.app.utils.odata import apply_select


router = RhesisRouter(
    prefix="/test_results",
    tags=["test_results"],
    responses={404: {"description": "Not found"}},
    resource="test_result",
)


@router.post("/", response_model=schemas.TestResult)
@handle_database_exceptions(
    entity_name="test result", custom_unique_message="test result with this name already exists"
)
def create_test_result(
    test_result: schemas.TestResultCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Create a new test result.

    The test result can include:
    - test_metrics: Automated metric evaluations
    - test_reviews: Human feedback with created_at/updated_at timestamps
    - test_output: The actual test execution output

    Note: If test_metrics are provided but status_id is not, the status will be
    automatically set based on whether all metrics passed.
    """
    organization_id, user_id = tenant_context

    # Set the user_id to the current user if not provided
    if not test_result.user_id:
        test_result.user_id = current_user.id

    # Auto-set status based on test_metrics if not provided
    if not test_result.status_id and test_result.test_metrics:
        from rhesis.backend.app.constants import TestResultStatus
        from rhesis.backend.app.utils.crud_utils import get_or_create_status

        metrics = test_result.test_metrics.get("metrics", {})
        if metrics:
            # Check if all metrics passed
            all_metrics_passed = all(
                metric_data.get("is_successful", False)
                for metric_data in metrics.values()
                if isinstance(metric_data, dict)
            )

            status_value = (
                TestResultStatus.PASS.value if all_metrics_passed else TestResultStatus.FAIL.value
            )
            status = get_or_create_status(
                db, status_value, "TestResult", organization_id=organization_id
            )
            test_result.status_id = status.id

    return test_result_crud.create_test_result(
        db=db, test_result=test_result, organization_id=organization_id, user_id=user_id
    )


@router.get("/", response_model=list[schemas.TestResultDetail])
@with_count_header(model=models.TestResult)
def read_test_results(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filter: str | None = Query(None, alias="$filter", description="OData filter expression"),
    select: str | None = Query(
        None,
        alias="$select",
        description="Comma-separated list of fields to return",
    ),
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get all test results"""
    organization_id, user_id = tenant_context
    results = test_result_crud.get_test_results(
        db,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
        organization_id=organization_id,
        user_id=user_id,
    )
    if select:
        serialized = jsonable_encoder(results)
        return JSONResponse(content=apply_select(serialized, select))
    return results


@router.get("/{test_result_id}", response_model=schemas.TestResultDetail)
def read_test_result(
    test_result_id: UUID,
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a specific test result by ID"""
    organization_id, user_id = tenant_context
    db_test_result = test_result_crud.get_test_result(
        db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")
    if db_test_result.test_reviews and "reviews" in db_test_result.test_reviews:
        populate_review_permitted_actions(db_test_result.test_reviews["reviews"])
    return db_test_result


@router.put("/{test_result_id}", response_model=schemas.TestResult)
def update_test_result(
    test_result_id: UUID,
    test_result: schemas.TestResultUpdate,
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Update a test result.

    Supports updating:
    - test_metrics: Automated evaluations
    - test_reviews: Human feedback (add new reviews or edit existing ones with updated_at)
    - status_id: Overall status of the test result

    Note: If test_metrics are updated but status_id is not provided, the status will be
    automatically updated based on whether all metrics passed.
    """
    organization_id, user_id = tenant_context
    db_test_result = test_result_crud.get_test_result(
        db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")

    principal = resolve_principal_from_request(current_user, request)
    project_id = project_id_from_scope(db)
    if not authorize_object(
        principal, Permission.TestResult.UPDATE_OWN, db_test_result, project_id=project_id, db=db
    ):
        raise HTTPException(status_code=403, detail="Not authorized to update this test result")

    # Auto-update status based on test_metrics if status_id is not explicitly provided
    if test_result.test_metrics and not test_result.status_id:
        from rhesis.backend.app.constants import TestResultStatus
        from rhesis.backend.app.utils.crud_utils import get_or_create_status

        metrics = test_result.test_metrics.get("metrics", {})
        if metrics:
            # Check if all metrics passed
            all_metrics_passed = all(
                metric_data.get("is_successful", False)
                for metric_data in metrics.values()
                if isinstance(metric_data, dict)
            )

            status_value = (
                TestResultStatus.PASS.value if all_metrics_passed else TestResultStatus.FAIL.value
            )
            status = get_or_create_status(
                db, status_value, "TestResult", organization_id=organization_id
            )
            test_result.status_id = status.id

    return test_result_crud.update_test_result(
        db=db,
        test_result_id=test_result_id,
        test_result=test_result,
        organization_id=organization_id,
        user_id=user_id,
    )


@router.delete("/{test_result_id}", response_model=schemas.TestResult)
def delete_test_result(
    test_result_id: UUID,
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Delete a test result. Only the creator may delete their own result."""
    organization_id, user_id = tenant_context
    db_test_result = test_result_crud.get_test_result(
        db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")

    principal = resolve_principal_from_request(current_user, request)
    project_id = project_id_from_scope(db)
    if not authorize_object(
        principal, Permission.TestResult.DELETE_OWN, db_test_result, project_id=project_id, db=db
    ):
        raise HTTPException(status_code=403, detail="Not authorized to delete this test result")

    return test_result_crud.delete_test_result(
        db=db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id
    )


# ============================================================================
# Review Management Routes
# ============================================================================


@router.post("/{test_result_id}/reviews", response_model=schemas.ReviewResponse)
def add_review(
    test_result_id: UUID,
    review: schemas.ReviewCreate,
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Add a new review to a test result.

    Creates a new review entry with:
    - Unique review_id
    - Current user as reviewer
    - Created_at and updated_at timestamps
    - Status and target information
    - Updates metadata automatically
    """
    organization_id, user_id = tenant_context

    # Get the test result
    db_test_result = test_result_crud.get_test_result(
        db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")

    # Get status details
    status_details = get_review_status_details(db, review.status_id, organization_id)

    # Initialize test_reviews if it doesn't exist
    if not db_test_result.test_reviews:
        db_test_result.test_reviews = {"metadata": {}, "reviews": []}
    elif not isinstance(db_test_result.test_reviews, dict):
        db_test_result.test_reviews = {"metadata": {}, "reviews": []}

    if "reviews" not in db_test_result.test_reviews:
        db_test_result.test_reviews["reviews"] = []

    # Create the new review
    now = datetime.now(timezone.utc).isoformat()
    new_review = {
        "review_id": str(uuid4()),
        "status": status_details,
        "user": {"user_id": str(current_user.id), "name": current_user.name or current_user.email},
        "comments": review.comments,
        "created_at": now,
        "updated_at": now,
        "target": {"type": review.target.type, "reference": review.target.reference},
        "resolved": False,
        "resolved_at": None,
        "resolved_by": None,
    }

    # Add the review
    db_test_result.test_reviews["reviews"].append(new_review)

    # Preserve any already-snapshotted original status before metadata gets
    # rebuilt below (update_review_metadata overwrites the whole dict).
    preserved_original_status_id = (db_test_result.test_reviews.get("metadata") or {}).get(
        "original_status_id"
    )

    # Update metadata
    update_review_metadata(db_test_result.test_reviews, current_user, status_details)

    # Snapshot the automated status once, before apply_review_override() below
    # overwrites status_id to match the reviewer's verdict. Without this,
    # matches_review/classify_test_result_review_counts would compare the
    # verdict against itself post-override and never detect a disagreement.
    db_test_result.test_reviews["metadata"]["original_status_id"] = (
        preserved_original_status_id
        or (str(db_test_result.status_id) if db_test_result.status_id else None)
    )

    # Mark as modified for SQLAlchemy
    flag_modified(db_test_result, "test_reviews")

    # Apply override to source data (metrics / turns)
    apply_review_override(
        db_test_result,
        review.target.type,
        review.target.reference,
        status_details,
        current_user,
        new_review["review_id"],
    )

    db.flush()
    db.refresh(db_test_result)
    # Commit before returning so the updated test_output is visible to the
    # immediately following GET /test_results/{id} call on the frontend.
    # Without this, FastAPI's dependency-cleanup commit races the next request.
    db.commit()

    populate_review_permitted_actions([new_review])
    return new_review


@router.put("/{test_result_id}/reviews/{review_id}", response_model=schemas.ReviewResponse)
def update_review(
    test_result_id: UUID,
    review_id: str,
    review: schemas.ReviewUpdate,
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Update an existing review.

    Updates review fields:
    - status_id (optional)
    - comments (optional)
    - target (optional)
    - Updates updated_at timestamp
    - Updates metadata automatically
    """
    organization_id, user_id = tenant_context

    # Get the test result
    db_test_result = test_result_crud.get_test_result(
        db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")

    # Check if test_reviews exists
    if not db_test_result.test_reviews or "reviews" not in db_test_result.test_reviews:
        raise HTTPException(status_code=404, detail="No reviews found for this test result")

    # Find the review to update
    reviews = db_test_result.test_reviews["reviews"]
    review_to_update = None

    for rev in reviews:
        if rev.get("review_id") == review_id:
            review_to_update = rev
            break

    if review_to_update is None:
        raise HTTPException(status_code=404, detail="Review not found")

    principal = resolve_principal_from_request(current_user, request)
    project_id = project_id_from_scope(db)
    if not authorize_review_action(
        principal,
        review_to_update,
        Permission.TestResult.UPDATE_OWN,
        project_id=project_id,
        db=db,
    ):
        raise HTTPException(status_code=403, detail="Not authorized to update this review")

    old_target = review_to_update.get("target", {})

    # Update fields if provided
    status_changed = False
    if review.status_id is not None:
        status_details = get_review_status_details(db, review.status_id, organization_id)
        review_to_update["status"] = status_details
        status_changed = True

    if review.comments is not None:
        review_to_update["comments"] = review.comments

    if review.resolved is not None:
        apply_review_resolved(review_to_update, resolved=review.resolved, current_user=current_user)

    target_changed = False
    if review.target is not None:
        review_to_update["target"] = {
            "type": review.target.type,
            "reference": review.target.reference,
        }
        target_changed = True

    # Update timestamp
    review_to_update["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Preserve the snapshotted original status before metadata gets rebuilt
    # below (update_review_metadata overwrites the whole dict).
    preserved_original_status_id = (db_test_result.test_reviews.get("metadata") or {}).get(
        "original_status_id"
    )

    # Update metadata
    latest_status = review_to_update["status"]
    update_review_metadata(db_test_result.test_reviews, current_user, latest_status)
    if preserved_original_status_id is not None:
        db_test_result.test_reviews["metadata"]["original_status_id"] = preserved_original_status_id

    # Mark as modified for SQLAlchemy
    flag_modified(db_test_result, "test_reviews")

    # Re-apply override when status or target changed
    if status_changed or target_changed:
        if target_changed:
            # Pass [] for remaining_reviews: the old-target override is
            # unconditionally cleared here. apply_review_override() immediately
            # re-installs the correct value for the new target within the same
            # flush, so no replacement search is needed.
            revert_override(
                db_test_result,
                old_target.get("type", ""),
                old_target.get("reference"),
                review_id,
                [],
            )
        apply_review_override(
            db_test_result,
            review_to_update["target"]["type"],
            review_to_update["target"].get("reference"),
            review_to_update["status"],
            current_user,
            review_id,
        )

    db.flush()
    db.refresh(db_test_result)
    db.commit()

    populate_review_permitted_actions([review_to_update])
    return review_to_update


@router.delete("/{test_result_id}/reviews/{review_id}", response_model=dict)
def delete_review(
    test_result_id: UUID,
    review_id: str,
    request: Request,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Delete a review from a test result.

    Removes the specified review and updates metadata automatically.
    Returns confirmation message with deleted review_id.
    """
    organization_id, user_id = tenant_context

    # Get the test result
    db_test_result = test_result_crud.get_test_result(
        db, test_result_id=test_result_id, organization_id=organization_id, user_id=user_id
    )
    if db_test_result is None:
        raise HTTPException(status_code=404, detail="Test result not found")

    # Check if test_reviews exists
    if not db_test_result.test_reviews or "reviews" not in db_test_result.test_reviews:
        raise HTTPException(status_code=404, detail="No reviews found for this test result")

    # Find and remove the review
    reviews = db_test_result.test_reviews["reviews"]
    review_index = None

    for idx, rev in enumerate(reviews):
        if rev.get("review_id") == review_id:
            review_index = idx
            break

    if review_index is None:
        raise HTTPException(status_code=404, detail="Review not found")

    principal = resolve_principal_from_request(current_user, request)
    project_id = project_id_from_scope(db)
    if not authorize_review_action(
        principal,
        reviews[review_index],
        Permission.TestResult.DELETE_OWN,
        project_id=project_id,
        db=db,
    ):
        raise HTTPException(status_code=403, detail="Not authorized to delete this review")

    # Remove the review
    deleted_review = reviews.pop(review_index)

    # Update metadata if there are remaining reviews
    if reviews:
        preserved_original_status_id = (db_test_result.test_reviews.get("metadata") or {}).get(
            "original_status_id"
        )
        latest_review = max(
            reviews,
            key=lambda r: r.get("updated_at", r.get("created_at", "")),
        )
        latest_status = latest_review.get("status", {"status_id": None, "name": "Unknown"})
        update_review_metadata(
            db_test_result.test_reviews,
            current_user,
            latest_status,
        )
        if preserved_original_status_id is not None:
            db_test_result.test_reviews["metadata"]["original_status_id"] = (
                preserved_original_status_id
            )
    else:
        db_test_result.test_reviews["metadata"] = {
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "last_updated_by": {
                "user_id": str(current_user.id),
                "name": current_user.name or current_user.email,
            },
            "total_reviews": 0,
            "latest_status": None,
            "summary": "All reviews removed",
        }

    flag_modified(db_test_result, "test_reviews")

    # Revert override on source data
    target = deleted_review.get("target", {})
    revert_override(
        db_test_result,
        target.get("type", ""),
        target.get("reference"),
        review_id,
        reviews,
    )

    db.flush()
    db.commit()

    return {
        "message": "Review deleted successfully",
        "review_id": review_id,
        "deleted_review": deleted_review,
    }


@router.get("/{test_result_id}/files", response_model=List[schemas.FileResponse])
def list_test_result_files(
    test_result_id: UUID,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """List output files attached to a test result."""
    organization_id, user_id = tenant_context
    return file_crud.get_files_for_entity(
        db, test_result_id, "TestResult", organization_id, user_id
    )
