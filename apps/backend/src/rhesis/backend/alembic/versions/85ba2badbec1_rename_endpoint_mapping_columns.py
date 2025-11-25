from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "85ba2badbec1"
down_revision: Union[str, None] = "c6e7f9f35a99"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename request_body_template to request_mapping
    op.alter_column("endpoint", "request_body_template", new_column_name="request_mapping")

    # Rename response_mappings to response_mapping
    op.alter_column("endpoint", "response_mappings", new_column_name="response_mapping")


def downgrade() -> None:
    # Revert request_mapping to request_body_template
    op.alter_column("endpoint", "request_mapping", new_column_name="request_body_template")

    # Revert response_mapping to response_mappings
    op.alter_column("endpoint", "response_mapping", new_column_name="response_mappings")
