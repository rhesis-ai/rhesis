"""add_bedrock_provider_type

Adds 'bedrock' as a ProviderType for Amazon Bedrock, authenticated with a
Bedrock API key.

Revision ID: b7e2d4a9c31f
Revises: f1a7c3e9d2b5
Create Date: 2026-11-13 10:00:00

"""

from typing import Sequence, Union

from alembic import op

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "b7e2d4a9c31f"
down_revision: Union[str, None] = "f1a7c3e9d2b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(load_type_lookup_template("('ProviderType', 'bedrock', 'Amazon Bedrock')"))


def downgrade() -> None:
    op.execute(load_cleanup_type_lookup_template("ProviderType", "'bedrock'"))
