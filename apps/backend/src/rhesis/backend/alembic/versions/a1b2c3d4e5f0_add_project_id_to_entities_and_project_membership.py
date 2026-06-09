"""Add project_id to entity tables and create project_membership table

Phase 2 of the project-container feature:
- Creates project_membership table (Phase 1)
- Adds nullable project_id FK column to 31 entity tables (Phase 2)
- Adds nullable project_id (no FK) to token, architect_message (Phase 2)
- Adds project_id to 4 association tables (Phase 2)

Revision ID: a1b2c3d4e5f0
Revises: f3a4b5c6d7e8
Create Date: 2026-05-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f0"
down_revision: Union[str, None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that get a nullable project_id FK to project.id + index
ENTITY_TABLES_WITH_FK = [
    "test_set",
    "test",
    "test_result",
    "test_run",
    "test_configuration",
    "test_context",
    "behavior",
    "category",
    "demographic",
    "dimension",
    "use_case",
    "risk",
    "topic",
    "metric",
    "prompt",
    "prompt_template",
    "response_pattern",
    "model",
    "source",
    "chunk",
    "file",
    "tool",
    "tag",
    "tagged_item",
    "status",
    "type_lookup",
    "task",
    "comment",
    "architect_session",
    "embedding",
    "subscription",
]

# Association tables that get project_id FK (no unique constraint changes)
ASSOCIATION_TABLES_WITH_FK = [
    "test_set_metric",
    "test_test_set",
    "behavior_metric",
    "prompt_test_set",
]

# Tables that get project_id without a FK (looked up before tenant context)
TABLES_WITHOUT_FK = [
    "token",
    "architect_message",
]


def upgrade() -> None:
    # 1. Create project_membership table
    op.create_table(
        "project_membership",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("nano_id", sa.String(), unique=True, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_membership_project_user"),
    )
    op.create_index(
        "ix_project_membership_project_id",
        "project_membership",
        ["project_id"],
    )
    op.create_index(
        "ix_project_membership_user_id",
        "project_membership",
        ["user_id"],
    )
    op.create_index(
        "ix_project_membership_organization_id",
        "project_membership",
        ["organization_id"],
    )

    # 2. Add nullable project_id FK to entity tables
    for table_name in ENTITY_TABLES_WITH_FK:
        op.add_column(
            table_name,
            sa.Column(
                "project_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("project.id"),
                nullable=True,
            ),
        )
        op.create_index(
            f"ix_{table_name}_project_id",
            table_name,
            ["project_id"],
        )

    # 3. Add nullable project_id FK to association tables (no index needed for
    #    small junction tables, but add for consistency)
    for table_name in ASSOCIATION_TABLES_WITH_FK:
        op.add_column(
            table_name,
            sa.Column(
                "project_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                sa.ForeignKey("project.id"),
                nullable=True,
            ),
        )

    # 4. Add project_id without FK to token and architect_message
    for table_name in TABLES_WITHOUT_FK:
        op.add_column(
            table_name,
            sa.Column(
                "project_id",
                sa.dialects.postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.create_index(
            f"ix_{table_name}_project_id",
            table_name,
            ["project_id"],
        )


def downgrade() -> None:
    # Remove project_id from tables without FK
    for table_name in reversed(TABLES_WITHOUT_FK):
        op.drop_index(f"ix_{table_name}_project_id", table_name=table_name)
        op.drop_column(table_name, "project_id")

    # Remove project_id from association tables
    for table_name in reversed(ASSOCIATION_TABLES_WITH_FK):
        op.drop_column(table_name, "project_id")

    # Remove project_id from entity tables
    for table_name in reversed(ENTITY_TABLES_WITH_FK):
        op.drop_index(f"ix_{table_name}_project_id", table_name=table_name)
        op.drop_column(table_name, "project_id")

    # Drop project_membership table
    op.drop_index("ix_project_membership_organization_id", table_name="project_membership")
    op.drop_index("ix_project_membership_user_id", table_name="project_membership")
    op.drop_index("ix_project_membership_project_id", table_name="project_membership")
    op.drop_table("project_membership")
