"""add trace table for OpenTelemetry spans

Revision ID: c5516aad2f45
Revises: 6cf857d168bd
Create Date: 2025-12-21

"""

from typing import Sequence, Union

import rhesis
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c5516aad2f45"
down_revision: Union[str, None] = "6cf857d168bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create trace table and indexes."""

    # Create trace table
    op.create_table(
        "trace",
        sa.Column(
            "id",
            rhesis.backend.app.models.guid.GUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("nano_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        # OpenTelemetry identifiers
        sa.Column("trace_id", sa.String(32), nullable=False),
        sa.Column("span_id", sa.String(16), nullable=False),
        sa.Column("parent_span_id", sa.String(16), nullable=True),
        # Rhesis identifiers
        sa.Column("project_id", rhesis.backend.app.models.guid.GUID(), nullable=False),
        sa.Column("organization_id", rhesis.backend.app.models.guid.GUID(), nullable=False),
        sa.Column("environment", sa.String(50), nullable=False),
        # Span metadata
        sa.Column("span_name", sa.String(255), nullable=False),
        sa.Column("span_kind", sa.String(20), nullable=False),
        # Timing
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        # Status
        sa.Column("status_code", sa.String(20), nullable=False),
        sa.Column("status_message", sa.Text(), nullable=True),
        # Flexible data storage
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "events",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "links",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "resource",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        # Processing metadata
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("enriched_data", postgresql.JSONB(astext_type=sa.Text()), server_default="{}"),
        # Foreign key
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(op.f("ix_trace_id"), "trace", ["id"], unique=True)
    op.create_index(op.f("ix_trace_deleted_at"), "trace", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_trace_trace_id"), "trace", ["trace_id"], unique=False)
    op.create_index(op.f("ix_trace_span_id"), "trace", ["span_id"], unique=False)
    op.create_index(op.f("ix_trace_parent_span_id"), "trace", ["parent_span_id"], unique=False)
    op.create_index(op.f("ix_trace_project_id"), "trace", ["project_id"], unique=False)
    op.create_index(op.f("ix_trace_organization_id"), "trace", ["organization_id"], unique=False)
    op.create_index(op.f("ix_trace_environment"), "trace", ["environment"], unique=False)
    op.create_index(op.f("ix_trace_span_name"), "trace", ["span_name"], unique=False)
    op.create_index(op.f("ix_trace_start_time"), "trace", ["start_time"], unique=False)
    op.create_index(op.f("ix_trace_status_code"), "trace", ["status_code"], unique=False)

    # Composite indexes
    op.create_index("idx_trace_project_time", "trace", ["project_id", sa.text("start_time DESC")])
    op.create_index("idx_trace_trace_id", "trace", ["trace_id", "start_time"])
    op.create_index("idx_trace_span_name_time", "trace", ["span_name", sa.text("start_time DESC")])
    op.create_index(
        "idx_trace_environment_time",
        "trace",
        ["environment", sa.text("start_time DESC")],
    )
    op.create_index("idx_trace_status_time", "trace", ["status_code", sa.text("start_time DESC")])
    op.create_index(
        "idx_trace_org_time",
        "trace",
        ["organization_id", sa.text("start_time DESC")],
    )
    op.create_index(
        "idx_trace_unprocessed",
        "trace",
        ["created_at"],
        postgresql_where=sa.text("processed_at IS NULL"),
    )

    # GIN index for JSONB
    op.execute("CREATE INDEX idx_trace_attributes ON trace USING GIN(attributes jsonb_path_ops)")


def downgrade() -> None:
    """Drop trace table and indexes."""
    op.drop_table("trace")
