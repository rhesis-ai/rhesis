from typing import Sequence, Union

import rhesis
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "0da7faeee4f5"
down_revision: Union[str, None] = "ee42160dfacf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add "Tool" SourceType to type_lookup table
    tool_source_type = (
        "('SourceType', 'Tool', 'Source imported from tool integration (MCP or API)')"
    )
    op.execute(load_type_lookup_template(tool_source_type))

    # Step 2: Remove "API" SourceType entries from type_lookup table
    api_type_values = "'API'"
    op.execute(load_cleanup_type_lookup_template("SourceType", api_type_values))


def downgrade() -> None:
    # Step 1: Re-add "API" SourceType to type_lookup table
    api_source_type = "('SourceType', 'API', 'API documentation or response')"
    op.execute(load_type_lookup_template(api_source_type))

    # Step 2: Remove "Tool" SourceType entries from type_lookup table
    tool_type_values = "'Tool'"
    op.execute(load_cleanup_type_lookup_template("SourceType", tool_type_values))
