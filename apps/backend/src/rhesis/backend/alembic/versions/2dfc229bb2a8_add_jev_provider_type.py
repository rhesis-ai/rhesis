"""add_jev_provider_type

Adds 'jev' as a ProviderType for TypeSafe AI's Jev decision model, which only
judges categorical metrics.

Revision ID: 2dfc229bb2a8
Revises: c1d2e3f4a5b6
Create Date: 2026-09-28 10:00:00

"""

from typing import Sequence, Union

from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "2dfc229bb2a8"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(load_type_lookup_template("('ProviderType', 'jev', 'Jev by TypeSafe AI')"))


def downgrade() -> None:
    op.execute(load_cleanup_type_lookup_template("ProviderType", "'jev'"))
