from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence
import rhesis
import os
import sys

# Add the alembic directory to sys.path so we can import utils
current_dir = os.path.dirname(os.path.abspath(__file__))
alembic_dir = os.path.dirname(current_dir)
if alembic_dir not in sys.path:
    sys.path.append(alembic_dir)

from utils.template_loader import load_type_lookup_template, load_cleanup_type_lookup_template

# revision identifiers, used by Alembic.
revision: str = 'c05814d9a399'
down_revision: Union[str, None] = 'cc1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new 'Trace' type for MetricScope
    values = "('MetricScope', 'Trace', 'Metric applies to execution traces')"
    sql = load_type_lookup_template(values)
    op.execute(sa.text(sql))


def downgrade() -> None:
    # Remove the 'Trace' types
    sql = load_cleanup_type_lookup_template('MetricScope', "'Trace'")
    op.execute(sa.text(sql))