from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Import our simple template loader
from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "5806494f1668"
down_revision: Union[str, None] = "6fe8376f15b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add MetricScope entries to type_lookup table
    metric_scope_values = """
        ('MetricScope', 'Single-Turn', 'Metric applies to single-turn tests only'),
        ('MetricScope', 'Multi-Turn', 'Metric applies to multi-turn tests only')
    """.strip()
    op.execute(load_type_lookup_template(metric_scope_values))

    # Step 2: Add metric_scope column to metric table
    op.add_column(
        "metric",
        sa.Column("metric_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Step 3: Set default metric_scope for existing metrics to ['Single-Turn']
    op.execute("""
        UPDATE metric 
        SET metric_scope = '["Single-Turn"]'::jsonb
        WHERE metric_scope IS NULL
    """)


def downgrade() -> None:
    # Step 1: Drop the metric_scope column
    op.drop_column("metric", "metric_scope")

    # Step 2: Remove MetricScope entries from type_lookup table
    metric_scope_values = "'Single-Turn', 'Multi-Turn'"
    op.execute(load_cleanup_type_lookup_template("MetricScope", metric_scope_values))
