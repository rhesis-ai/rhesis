"""require a non-empty metric_scope

A metric whose metric_scope is unset is filtered out by every execution path, so
it never evaluates and reports no error. Backfill the rows that never got one,
then constrain the column so it cannot happen again.

The CHECK does the work rather than a plain NOT NULL: the offending rows in
practice hold JSONB ``'null'`` (a JSON null value), which NOT NULL does not
reject. It also rejects an empty array and any non-array value.

Revision ID: 40a5b6b88a52
Revises: e90c29496562
Create Date: 2026-08-10

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "40a5b6b88a52"
down_revision: Union[str, None] = "e90c29496562"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# SQL NULL, JSONB 'null', a non-array value, or an empty array.
#
# jsonb_array_length() raises (not NULL) on a non-array argument, so the third
# branch guards it with its own jsonb_typeof check rather than relying on the
# OR's left-to-right evaluation order, which SQL does not guarantee.
_UNSCOPED = """
    metric_scope IS NULL
    OR jsonb_typeof(metric_scope) <> 'array'
    OR (jsonb_typeof(metric_scope) = 'array' AND jsonb_array_length(metric_scope) = 0)
"""

_CONSTRAINT = "ck_metric_metric_scope_non_empty"


def upgrade() -> None:
    # Backfill by class_name. The existing distribution is unambiguous:
    # ConversationalJudge is Multi-Turn (670 of 681 rows), while NumericJudge and
    # CategoricalJudge are Single-Turn (293 of 331 and 146 of 153).
    op.execute(f"""
        UPDATE metric
        SET metric_scope = '["Multi-Turn"]'::jsonb
        WHERE ({_UNSCOPED}) AND class_name = 'ConversationalJudge'
    """)

    # Everything else, including rows with no class_name, follows the Single-Turn
    # default that migration 5806494f1668 used for the original backfill.
    op.execute(f"""
        UPDATE metric
        SET metric_scope = '["Single-Turn"]'::jsonb
        WHERE {_UNSCOPED}
    """)

    op.create_check_constraint(
        _CONSTRAINT,
        "metric",
        "jsonb_typeof(metric_scope) = 'array' AND jsonb_array_length(metric_scope) > 0",
    )
    op.alter_column("metric", "metric_scope", nullable=False)


def downgrade() -> None:
    op.alter_column("metric", "metric_scope", nullable=True)
    op.drop_constraint(_CONSTRAINT, "metric", type_="check")
