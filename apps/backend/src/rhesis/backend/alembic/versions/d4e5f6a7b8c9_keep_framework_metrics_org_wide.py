"""Keep framework provider metrics org-wide

DeepEval, Ragas, Garak, and Rhesis built-in metrics should remain visible in
every project (project_id NULL). Undo any example-project scoping applied by
the prior onboarding backfill migration.

Revision ID: d4e5f6a7b8c9
Revises: b3c4d5e6f7a8
Create Date: 2026-07-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EXAMPLE_PROJECT_NAME = "Example Project (Insurance Chatbot)"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE metric DISABLE ROW LEVEL SECURITY"))
    conn.execute(
        sa.text(
            """
            UPDATE metric m
            SET project_id = NULL
            FROM type_lookup bt, project p
            WHERE m.backend_type_id = bt.id
              AND m.project_id = p.id
              AND p.name = :example_name
              AND bt.type_value IN ('deepeval', 'ragas', 'garak', 'rhesis')
            """
        ),
        {"example_name": EXAMPLE_PROJECT_NAME},
    )
    conn.execute(sa.text("ALTER TABLE metric ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE metric FORCE ROW LEVEL SECURITY"))


def downgrade() -> None:
    pass
