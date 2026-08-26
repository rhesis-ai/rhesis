"""Read-only SQLAlchemy models mapped to PostgreSQL stats views.

These models back the v_test_run_stats/v_test_result_stats views (migration
cb4b107b5daf), v_metric_stats (migration d3f8a91c5b02), and v_test_stats
(migration 90104949ab99). They are intentionally thin -- all join and
classification logic lives in the view DDL.
"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base
from .guid import GUID


class TestRunStatsView(Base):
    __tablename__ = "v_test_run_stats"
    __table_args__ = {"info": {"is_view": True}}

    test_run_id = Column(GUID(), primary_key=True)
    organization_id = Column(GUID())
    created_at = Column(DateTime(timezone=True))
    user_id = Column(GUID())
    status_name = Column(String)
    result = Column(String)
    test_set_id = Column(GUID())
    endpoint_id = Column(GUID())
    test_set_name = Column(String)
    executor_name = Column(String)
    year = Column(Integer)
    month = Column(Integer)

    # Suppress Base defaults that don't apply to views
    id = None
    nano_id = None
    updated_at = None
    deleted_at = None


class MetricStatsView(Base):
    """Backs v_metric_stats -- one row per (test_result, metric_name), created by
    alembic migration d3f8a91c5b02 (fixed by d52329dc7e4e). effective_success is
    each metric's own recorded verdict (automated, or corrected by a review that
    targeted that specific metric); automated_success is the pre-review value.
    """

    __tablename__ = "v_metric_stats"
    __table_args__ = {"info": {"is_view": True}}

    test_result_id = Column(GUID(), primary_key=True)
    organization_id = Column(GUID())
    test_run_id = Column(GUID())
    test_id = Column(GUID())
    requirement_id = Column(GUID())
    created_at = Column(DateTime(timezone=True))
    year = Column(Integer)
    month = Column(Integer)
    metric_name = Column(String, primary_key=True)
    has_override = Column(Boolean)
    automated_success = Column(Boolean)
    effective_success = Column(Boolean)

    # Suppress Base defaults that don't apply to views
    id = None
    nano_id = None
    updated_at = None
    deleted_at = None


class TestStatsView(Base):
    """Backs v_test_stats -- one row per test, created by alembic migration
    90104949ab99. Unlike v_test_result_stats/v_metric_stats (anchored on
    test_result, so a test with zero results is structurally invisible),
    this view is anchored on test and LEFT JOINs an aggregate of its
    test_result rows, so unrun tests surface with run_count=0/is_unrun=True.
    """

    __tablename__ = "v_test_stats"
    __table_args__ = {"info": {"is_view": True}}

    test_id = Column(GUID(), primary_key=True)
    organization_id = Column(GUID())
    requirement_id = Column(GUID())
    category_id = Column(GUID())
    topic_id = Column(GUID())
    test_type_id = Column(GUID())
    test_user_id = Column(GUID())
    assignee_id = Column(GUID())
    owner_id = Column(GUID())
    prompt_id = Column(GUID())
    priority = Column(Integer)
    test_status_id = Column(GUID())
    requirement_name = Column(String)
    category_name = Column(String)
    topic_name = Column(String)
    created_at = Column(DateTime(timezone=True))
    year = Column(Integer)
    month = Column(Integer)
    run_count = Column(Integer)
    passed_count = Column(Integer)
    failed_count = Column(Integer)
    pending_count = Column(Integer)
    is_unrun = Column(Boolean)
    last_run_at = Column(DateTime(timezone=True))

    # Suppress Base defaults that don't apply to views
    id = None
    nano_id = None
    updated_at = None
    deleted_at = None


class TestResultStatsView(Base):
    __tablename__ = "v_test_result_stats"
    __table_args__ = {"info": {"is_view": True}}

    test_result_id = Column(GUID(), primary_key=True)
    organization_id = Column(GUID())
    created_at = Column(DateTime(timezone=True))
    test_run_id = Column(GUID())
    test_id = Column(GUID())
    test_metrics = Column(JSONB)
    status_name = Column(String)
    result = Column(String)
    result_status_id = Column(GUID())
    test_status_id = Column(GUID())
    requirement_id = Column(GUID())
    category_id = Column(GUID())
    topic_id = Column(GUID())
    test_user_id = Column(GUID())
    assignee_id = Column(GUID())
    owner_id = Column(GUID())
    prompt_id = Column(GUID())
    priority = Column(Integer)
    test_type_id = Column(GUID())
    requirement_name = Column(String)
    category_name = Column(String)
    topic_name = Column(String)
    run_id = Column(GUID())
    test_run_name = Column(String)
    test_run_created_at = Column(DateTime(timezone=True))
    year = Column(Integer)
    month = Column(Integer)

    # Suppress Base defaults that don't apply to views
    id = None
    nano_id = None
    updated_at = None
    deleted_at = None
