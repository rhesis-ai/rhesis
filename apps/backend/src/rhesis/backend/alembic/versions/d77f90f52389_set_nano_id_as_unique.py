from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from nanoid import generate

from rhesis.backend.app.models.base import custom_alphabet

# revision identifiers, used by Alembic.
revision: str = "d77f90f52389"
down_revision: Union[str, None] = "946a0da4f7bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# All tables that have nano_id (all models inheriting from Base)
TABLES_WITH_NANO_ID = [
    "behavior",
    "category",
    "comment",
    "demographic",
    "dimension",
    "endpoint",
    "metric",
    "model",
    "organization",
    "project",
    "prompt",
    "prompt_template",
    "response_pattern",
    "risk",
    "source",
    "status",
    "subscription",
    "tag",
    "tagged_item",
    "task",
    "test",
    "test_configuration",
    "test_context",
    "test_result",
    "test_run",
    "test_set",
    "token",
    "tool",
    "topic",
    "type_lookup",
    "use_case",
    "user",
]


def upgrade() -> None:
    # First, fix any duplicate nano_id values
    conn = op.get_bind()

    for table_name in TABLES_WITH_NANO_ID:
        # Quote table name to handle reserved keywords like "user"
        quoted_table_name = conn.dialect.identifier_preparer.quote(table_name)

        # Find duplicates and update them with new unique nano_ids
        result = conn.execute(
            sa.text(
                f"""
                SELECT id, nano_id,
                    ROW_NUMBER() OVER (PARTITION BY nano_id ORDER BY created_at) as rn
                FROM {quoted_table_name}
                WHERE nano_id IN (
                    SELECT nano_id
                    FROM {quoted_table_name}
                    WHERE nano_id IS NOT NULL
                    GROUP BY nano_id
                    HAVING COUNT(*) > 1
                )
                ORDER BY nano_id, created_at
                """
            )
        )
        duplicates = result.fetchall()

        # Update duplicates (keep first occurrence, update rest)
        for row in duplicates:
            if row[2] > 1:  # rn > 1 means it's a duplicate (not the first occurrence)
                new_nano_id = generate(size=12, alphabet=custom_alphabet)
                # Ensure the new nano_id doesn't already exist
                while True:
                    check = conn.execute(
                        sa.text(
                            f"SELECT COUNT(*) FROM {quoted_table_name} WHERE nano_id = :nano_id"
                        ),
                        {"nano_id": new_nano_id},
                    ).scalar()
                    if check == 0:
                        break
                    new_nano_id = generate(size=12, alphabet=custom_alphabet)

                conn.execute(
                    sa.text(
                        f"UPDATE {quoted_table_name} SET nano_id = :new_nano_id WHERE id = :id"
                    ),
                    {"new_nano_id": new_nano_id, "id": row[0]},
                )

    # Now add unique constraints
    for table_name in TABLES_WITH_NANO_ID:
        # Create unique index on nano_id for each table
        op.create_unique_constraint(
            f"uq_{table_name}_nano_id",
            table_name,
            ["nano_id"],
        )


def downgrade() -> None:
    # Remove unique constraint from nano_id for all tables
    for table_name in TABLES_WITH_NANO_ID:
        op.drop_constraint(
            f"uq_{table_name}_nano_id",
            table_name,
            type_="unique",
        )
