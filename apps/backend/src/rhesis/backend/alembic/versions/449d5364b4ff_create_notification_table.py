"""create notification table

Revision ID: 449d5364b4ff
Revises: 82881df987af
Create Date: 2026-08-09

RLS policies are added explicitly below rather than relying solely on the
``auto_apply_rls_policies`` event trigger (see
``b8c9d0e1f2a3_fail_closed_project_isolation_rls``): the trigger does not
reliably fire for a brand-new ``CREATE TABLE`` in every environment
(``tests/backend/security/test_rls_coverage.py`` caught this table missing
its policies under a fresh migration replay), so the exact policy bodies
are duplicated here. Each ``CREATE POLICY`` is preceded by
``DROP POLICY IF EXISTS`` -- the same guard ``b8c9d0e1f2a3`` uses -- so this
stays idempotent on an environment where the trigger *did* already create
the same policy.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import rhesis.backend.app.models.guid

# revision identifiers, used by Alembic.
revision: str = "449d5364b4ff"
down_revision: Union[str, None] = "82881df987af"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create notification table with indexes."""
    op.create_table(
        "notification",
        sa.Column(
            "id",
            rhesis.backend.app.models.guid.GUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("nano_id", sa.String(), nullable=True),
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
        # Notification content
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("section", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("is_failure", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", rhesis.backend.app.models.guid.GUID(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        # Multi-tenancy. project_id is nullable: NULL means org-wide, visible
        # regardless of the recipient's active project.
        sa.Column(
            "organization_id",
            rhesis.backend.app.models.guid.GUID(),
            nullable=True,
        ),
        sa.Column(
            "project_id",
            rhesis.backend.app.models.guid.GUID(),
            nullable=True,
        ),
        # NOT NULL, unlike the nullable user_id the mixin declares for most
        # tables: here it's the recipient, not "created by". A NULL would be
        # unreachable anyway -- every read filters user_id == the caller -- so
        # the row would be invisible dead data rather than a shared notification.
        sa.Column(
            "user_id",
            rhesis.backend.app.models.guid.GUID(),
            nullable=False,
        ),
        # Constraints. A notification is meaningless without its recipient, org,
        # or project, so all three cascade on delete (unlike Chunk.user_id,
        # which is "created by" and survives the user's deletion). Declared here
        # rather than on the mixins -- see the Notification model docstring.
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes
    op.create_index("ix_notification_id", "notification", ["id"], unique=True)
    op.create_index("ix_notification_nano_id", "notification", ["nano_id"], unique=True)
    op.create_index("ix_notification_event_type", "notification", ["event_type"])
    op.create_index("ix_notification_section", "notification", ["section"])
    op.create_index("ix_notification_entity_id", "notification", ["entity_id"])
    op.create_index("ix_notification_read_at", "notification", ["read_at"])
    op.create_index("ix_notification_organization_id", "notification", ["organization_id"])
    op.create_index("ix_notification_project_id", "notification", ["project_id"])
    op.create_index("ix_notification_user_id", "notification", ["user_id"])

    # RLS: tenant_isolation (PERMISSIVE, organization_id) + project_isolation
    # (RESTRICTIVE, fail-closed on project_id) -- exact bodies duplicated from
    # d4e5f6a7b8c3 and b8c9d0e1f2a3 respectively. DROP ... IF EXISTS first:
    # see the module docstring for why.
    op.execute("ALTER TABLE notification ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notification FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notification")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON notification
            USING (organization_id = current_setting('app.current_organization')::uuid)
        """
    )
    op.execute("DROP POLICY IF EXISTS project_isolation ON notification")
    op.execute(
        """
        CREATE POLICY project_isolation ON notification
            AS RESTRICTIVE
            FOR ALL
            USING (
                project_id = NULLIF(current_setting('app.current_project', true), '')::uuid
                OR project_id IS NULL
                OR current_setting('app.current_organization', true) = ''
            )
        """
    )


def downgrade() -> None:
    """Drop notification table and indexes."""
    op.drop_index("ix_notification_user_id", table_name="notification")
    op.drop_index("ix_notification_project_id", table_name="notification")
    op.drop_index("ix_notification_organization_id", table_name="notification")
    op.drop_index("ix_notification_read_at", table_name="notification")
    op.drop_index("ix_notification_entity_id", table_name="notification")
    op.drop_index("ix_notification_section", table_name="notification")
    op.drop_index("ix_notification_event_type", table_name="notification")
    op.drop_index("ix_notification_nano_id", table_name="notification")
    op.drop_index("ix_notification_id", table_name="notification")
    op.drop_table("notification")
