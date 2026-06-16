"""Drop auto-assigned behavior association for the PythonPypi garak detector

The ``PythonPypi`` (Package Hallucination) garak detector was seeded into the
``Reliability`` behavior, so it auto-ran on every Reliability test. It only
makes sense for code-generation outputs and, on first use, downloads a
~555K-row PyPI dataset from HuggingFace with no timeout — which intermittently
hangs test-run execution.

``detectors.yaml`` now declares ``behavior: null`` for PythonPypi (catalog-only,
no auto-assignment), but that change only affects *fresh* seeding. This data
migration removes the already-seeded ``behavior_metric`` rows so existing
deployments stop auto-running it. The metric itself is left intact and remains
selectable / attachable to a test set explicitly.

Revision ID: c7d8e9f0a1b2
Revises: 2b59776c5ef3
Create Date: 2026-06-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "2b59776c5ef3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DETECTOR_PATH = "garak.detectors.packagehallucination.PythonPypi"


def upgrade() -> None:
    conn = op.get_bind()

    # Temporarily disable RLS on the joined tables. The tenant_isolation
    # policies call current_setting('app.current_organization') without
    # missing_ok=true; the migration user is not a superuser, so RLS is
    # evaluated and the unregistered GUC would raise an error.
    conn.execute(sa.text("ALTER TABLE behavior_metric DISABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE metric DISABLE ROW LEVEL SECURITY"))

    # Delete every behavior association (across all organizations) for the
    # PythonPypi metric, identified by its detector path in evaluation_prompt.
    conn.execute(
        sa.text(
            """
            DELETE FROM behavior_metric
            WHERE metric_id IN (
                SELECT id FROM metric WHERE evaluation_prompt = :path
            )
            """
        ),
        {"path": _DETECTOR_PATH},
    )

    conn.execute(sa.text("ALTER TABLE behavior_metric ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE metric ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    # No-op: re-creating the association would reintroduce the hang this
    # migration fixes, and the original (behavior_id, user_id) pairs are not
    # recoverable here. Re-running initial-data seeding would re-link the
    # detector only if its behavior is restored in detectors.yaml.
    pass
