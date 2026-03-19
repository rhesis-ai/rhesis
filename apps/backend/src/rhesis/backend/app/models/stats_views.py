"""Read-only SQLAlchemy models mapped to PostgreSQL stats views.

These models back the v_test_run_stats and v_test_result_stats views
created in alembic migration cb4b107b5daf. They are intentionally thin
-- all join and classification logic lives in the view DDL.
"""

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base
from .guid import GUID


class TestRunStatsView(Base):
    __tablename__ = "v_test_run_stats"
    __table_args__ = {"info": {"is_view": True}}

    test_run_id = Column(GUID(), primary_key=True)
    organization_id = Column(GUID())
    created_at = Column(DateTime)
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


class TestResultStatsView(Base):
    __tablename__ = "v_test_result_stats"
    __table_args__ = {"info": {"is_view": True}}

    test_result_id = Column(GUID(), primary_key=True)
    organization_id = Column(GUID())
    created_at = Column(DateTime)
    test_run_id = Column(GUID())
    test_id = Column(GUID())
    test_metrics = Column(JSONB)
    status_name = Column(String)
    result = Column(String)
    test_status_id = Column(GUID())
    behavior_id = Column(GUID())
    category_id = Column(GUID())
    topic_id = Column(GUID())
    test_user_id = Column(GUID())
    assignee_id = Column(GUID())
    owner_id = Column(GUID())
    prompt_id = Column(GUID())
    priority = Column(Integer)
    test_type_id = Column(GUID())
    behavior_name = Column(String)
    category_name = Column(String)
    topic_name = Column(String)
    run_id = Column(GUID())
    test_run_name = Column(String)
    test_run_created_at = Column(DateTime)
    year = Column(Integer)
    month = Column(Integer)

    # Suppress Base defaults that don't apply to views
    id = None
    nano_id = None
    updated_at = None
    deleted_at = None
