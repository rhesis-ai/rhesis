"""List annotations by flattening review JSONB on test results and traces."""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from rhesis.backend.app.schemas.annotation import AnnotationListItem

logger = logging.getLogger(__name__)

AnnotationSource = Literal["test_result", "trace"]
AnnotationRating = Literal["Pass", "Fail"]
AnnotationTargetType = Literal["test_result", "trace", "metric", "turn"]


def _row_to_item(row: Any) -> AnnotationListItem:
    review = row.review if isinstance(row.review, dict) else {}
    target = review.get("target") or {}
    if isinstance(target, dict) and target.get("type") == "test":
        target = {**target, "type": "test_result"}

    return AnnotationListItem(
        review_id=str(review.get("review_id") or row.review_id or ""),
        source=row.source,
        comments=str(review.get("comments") or ""),
        created_at=review.get("created_at"),
        updated_at=review.get("updated_at"),
        status=review.get("status") or {},
        user=review.get("user") or {},
        target=target if isinstance(target, dict) else {},
        resolved=bool(review.get("resolved")),
        test_result_id=row.test_result_id,
        test_run_id=row.test_run_id,
        trace_db_id=row.trace_db_id,
        trace_id=row.trace_id,
        project_id=row.project_id,
        span_name=row.span_name,
    )


def list_annotations(
    db: Session,
    *,
    organization_id: str,
    project_id: Optional[str] = None,
    include_test_results: bool = True,
    include_traces: bool = True,
    source: Optional[AnnotationSource] = None,
    search: Optional[str] = None,
    resolved: Optional[bool] = None,
    rating: Optional[AnnotationRating] = None,
    target_type: Optional[AnnotationTargetType] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[AnnotationListItem], int]:
    """Return flattened reviews with correct row-level pagination.

    Each source branch is included only when the corresponding flag is True.
    Explicit org/project predicates are required because this uses ``text()``
    SQL (ORM auto-filter does not apply).
    """
    if source == "test_result":
        include_traces = False
        include_test_results = True
    elif source == "trace":
        include_test_results = False
        include_traces = True

    if not include_test_results and not include_traces:
        return [], 0

    search_term = search.strip() if search and search.strip() else None

    branches: list[str] = []
    if include_test_results:
        branches.append(
            """
            SELECT
                (elem->>'review_id') AS review_id,
                'test_result' AS source,
                tr.id AS test_result_id,
                tr.test_run_id AS test_run_id,
                NULL::uuid AS trace_db_id,
                NULL::text AS trace_id,
                tr.project_id AS project_id,
                NULL::text AS span_name,
                elem AS review,
                COALESCE(elem->>'updated_at', elem->>'created_at') AS sort_at
            FROM test_result tr,
                 LATERAL jsonb_array_elements(tr.test_reviews->'reviews') AS elem
            WHERE tr.organization_id = CAST(:organization_id AS uuid)
              AND tr.deleted_at IS NULL
              AND tr.test_reviews IS NOT NULL
              AND jsonb_typeof(tr.test_reviews->'reviews') = 'array'
              AND jsonb_array_length(tr.test_reviews->'reviews') > 0
              AND (
                    CAST(:project_id AS uuid) IS NULL
                    OR tr.project_id = CAST(:project_id AS uuid)
                  )
            """
        )
    if include_traces:
        branches.append(
            """
            SELECT
                (elem->>'review_id') AS review_id,
                'trace' AS source,
                NULL::uuid AS test_result_id,
                NULL::uuid AS test_run_id,
                t.id AS trace_db_id,
                t.trace_id AS trace_id,
                t.project_id AS project_id,
                t.span_name AS span_name,
                elem AS review,
                COALESCE(elem->>'updated_at', elem->>'created_at') AS sort_at
            FROM trace t,
                 LATERAL jsonb_array_elements(t.trace_reviews->'reviews') AS elem
            WHERE t.organization_id = CAST(:organization_id AS uuid)
              AND t.deleted_at IS NULL
              AND t.trace_reviews IS NOT NULL
              AND jsonb_typeof(t.trace_reviews->'reviews') = 'array'
              AND jsonb_array_length(t.trace_reviews->'reviews') > 0
              AND (
                    CAST(:project_id AS uuid) IS NULL
                    OR t.project_id = CAST(:project_id AS uuid)
                  )
            """
        )

    union_sql = " UNION ALL ".join(branches)
    sql = text(
        f"""
        WITH flattened AS (
            {union_sql}
        )
        SELECT
            review_id,
            source,
            test_result_id,
            test_run_id,
            trace_db_id,
            trace_id,
            project_id,
            span_name,
            review,
            sort_at,
            COUNT(*) OVER() AS total_count
        FROM flattened
        WHERE
              (
                CAST(:search AS text) IS NULL
                OR review->>'comments' ILIKE '%' || CAST(:search AS text) || '%'
                OR review->'user'->>'name' ILIKE '%' || CAST(:search AS text) || '%'
                OR COALESCE(review->'target'->>'reference', '')
                    ILIKE '%' || CAST(:search AS text) || '%'
                OR COALESCE(review->'status'->>'name', '')
                    ILIKE '%' || CAST(:search AS text) || '%'
              )
          AND (
                CAST(:resolved AS boolean) IS NULL
                OR COALESCE((review->>'resolved')::boolean, false)
                    = CAST(:resolved AS boolean)
              )
          AND (
                CAST(:rating AS text) IS NULL
                OR lower(COALESCE(review->'status'->>'name', ''))
                    = lower(CAST(:rating AS text))
              )
          AND (
                CAST(:target_type AS text) IS NULL
                OR CASE
                     WHEN review->'target'->>'type' = 'test' THEN 'test_result'
                     ELSE review->'target'->>'type'
                   END = CAST(:target_type AS text)
              )
        ORDER BY sort_at DESC NULLS LAST
        LIMIT :limit OFFSET :skip
        """
    )

    params: dict[str, Any] = {
        "organization_id": organization_id,
        "project_id": project_id,
        "search": search_term,
        "resolved": resolved,
        "rating": rating,
        "target_type": target_type,
        "limit": limit,
        "skip": skip,
    }

    result = db.execute(sql, params)
    rows = result.fetchall()
    if not rows:
        return [], 0

    total_count = int(rows[0].total_count or 0)
    items = [_row_to_item(row) for row in rows]
    return items, total_count
