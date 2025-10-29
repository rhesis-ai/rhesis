"""update_type_lookup_descriptions

This migration updates the descriptions of existing type_lookup entries
to match the descriptions defined in initial_data.json.

Revision ID: a6a7196f4949
Revises: e9320c797e43
Create Date: 2025-10-29 12:27:41

"""

import json
import os
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "a6a7196f4949"
down_revision: Union[str, None] = "e9320c797e43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def load_initial_data():
    """Load the initial_data.json file."""
    # Get the path to initial_data.json relative to this migration file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up from alembic/versions to the backend/app/services directory
    initial_data_path = os.path.join(
        current_dir, "..", "..", "app", "services", "initial_data.json"
    )
    initial_data_path = os.path.normpath(initial_data_path)

    with open(initial_data_path, "r") as file:
        return json.load(file)


def upgrade() -> None:
    """Update descriptions for all type_lookup entries based on initial_data.json."""
    # Load initial data
    initial_data = load_initial_data()
    type_lookup_entries = initial_data.get("type_lookup", [])

    connection = op.get_bind()
    updated_count = 0

    # Update each type_lookup entry with its description
    for entry in type_lookup_entries:
        type_name = entry.get("type_name")
        type_value = entry.get("type_value")
        description = entry.get("description")

        if type_name and type_value and description:
            # Update the description for matching type_lookup entries
            result = connection.execute(
                text(
                    """
                    UPDATE type_lookup 
                    SET description = :description 
                    WHERE type_name = :type_name 
                    AND type_value = :type_value
                    AND deleted_at IS NULL
                    """
                ),
                {
                    "description": description,
                    "type_name": type_name,
                    "type_value": type_value,
                },
            )
            updated_count += result.rowcount

    print(f"✓ Updated descriptions for {updated_count} type_lookup entries")


def downgrade() -> None:
    """
    Downgrade is not implemented as we don't want to remove descriptions.
    The descriptions are additive and don't break existing functionality.
    """
    print("⚠ Downgrade not implemented - descriptions are left as-is")
    print("  (Descriptions are informational and do not affect functionality)")
