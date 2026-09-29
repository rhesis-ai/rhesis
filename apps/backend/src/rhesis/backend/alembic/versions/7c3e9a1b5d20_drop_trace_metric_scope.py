"""drop the Trace metric scope

A project now picks its trace metrics explicitly in its settings, from any
metric, so "Trace" no longer means anything as a scope. Strip it from every
metric. A metric scoped only ["Trace"] ran on single-turn traces and on whole
conversations, so it becomes ["Single-Turn", "Multi-Turn"] to keep running on
both.

Downgrade restores the lookup row but not the scopes removed here.

Revision ID: 7c3e9a1b5d20
Revises: 2dfc229bb2a8
Create Date: 2026-09-29 10:00:00

"""

from typing import Sequence, Union

from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "7c3e9a1b5d20"
down_revision: Union[str, None] = "2dfc229bb2a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # jsonb_agg over zero rows is NULL, so a ["Trace"]-only scope falls to the COALESCE.
    op.execute(
        """
        UPDATE metric
        SET metric_scope = COALESCE(
            (
                SELECT jsonb_agg(scope)
                FROM jsonb_array_elements(metric_scope) AS scope
                WHERE scope <> '"Trace"'::jsonb
            ),
            '["Single-Turn", "Multi-Turn"]'::jsonb
        )
        WHERE metric_scope @> '["Trace"]'::jsonb
        """
    )
    op.execute(load_cleanup_type_lookup_template("MetricScope", "'Trace'"))


def downgrade() -> None:
    op.execute(
        load_type_lookup_template("('MetricScope', 'Trace', 'Metric applies to execution traces')")
    )
