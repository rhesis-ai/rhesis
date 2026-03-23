from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence
import rhesis



# revision identifiers, used by Alembic.
revision: str = 'c05814d9a399'
down_revision: Union[str, None] = 'cc1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new 'Trace' type for MetricScope only
    op.execute(
        """
        INSERT INTO type_lookup (id, type_name, type_value, description, created_at, updated_at)
        SELECT gen_random_uuid(), 'MetricScope', 'Trace', 'Metric applies to execution traces', NOW(), NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM type_lookup WHERE type_name = 'MetricScope' AND type_value = 'Trace'
        );
        """
    )


def downgrade() -> None:
    # Remove the 'Trace' types
    op.execute(
        """
        DELETE FROM type_lookup
        WHERE type_name = 'MetricScope' AND type_value = 'Trace';
        """
    )