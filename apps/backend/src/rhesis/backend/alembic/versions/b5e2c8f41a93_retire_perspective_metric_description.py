"""Stop describing Toxicity Detection as Perspective API

Perspective API shuts down on 31 Dec 2026. The detector path stays as the metric's
identifier, but the SDK now scores it with Google Cloud Natural Language moderation or
the judge model. Only descriptions that still mention Perspective are rewritten, so a
description a user changed to something else is left alone.

Revision ID: b5e2c8f41a93
Revises: c5e1a8f3b902
Create Date: 2026-10-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from rhesis.backend.alembic.utils.tenant_scope import iter_tenant_scopes

revision: str = "b5e2c8f41a93"
down_revision: Union[str, None] = "c5e1a8f3b902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DETECTOR_PATH = "garak.detectors.perspective.Toxicity"
NEW_DESCRIPTION = (
    "Detects toxic content in LLM outputs. Scores with Google Cloud Natural Language "
    "text moderation when GOOGLE_MODERATION_API_KEY is set, and with the judge model "
    "otherwise."
)

_UPDATE = sa.text("""
    UPDATE metric
    SET description = :description
    WHERE organization_id = CAST(:org_id AS uuid)
      AND evaluation_prompt = :path
      AND description LIKE '%Perspective API%'
""")


def upgrade() -> None:
    conn = op.get_bind()
    # metric has no project_id, so each org's own scope reaches all of its rows.
    for org_id, project_id in iter_tenant_scopes(conn):
        if project_id is None:
            conn.execute(
                _UPDATE,
                {"description": NEW_DESCRIPTION, "org_id": org_id, "path": DETECTOR_PATH},
            )


def downgrade() -> None:
    # Description text only; the old wording is not worth restoring.
    pass
