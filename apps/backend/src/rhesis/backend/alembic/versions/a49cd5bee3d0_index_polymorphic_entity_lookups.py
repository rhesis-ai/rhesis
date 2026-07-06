"""index polymorphic entity lookups

Adds a composite index on (entity_id, entity_type) for comment, task, and
tagged_item -- the columns filtered by CommentsMixin/TasksMixin/TagsMixin's
polymorphic relationships (see app/models/mixins.py). These relationships
are lazy-loaded once per object during list-endpoint serialization
(counts/tags on Test, TestSet, Prompt, Behavior, etc.), and without an
index each lookup was a full sequential scan. Confirmed via EXPLAIN
ANALYZE: a single lookup against a 50k-row comment table took ~27ms doing
`Seq Scan ... Rows Removed by Filter: 50000`.

`file` already has single-column indexes on both columns and is
intentionally left alone here.

Revision ID: a49cd5bee3d0
Revises: b3c4d5e6f7a8
Create Date: 2026-07-06
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a49cd5bee3d0"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES = [
    ("ix_comment_entity_id_entity_type", "comment", ["entity_id", "entity_type"]),
    ("ix_task_entity_id_entity_type", "task", ["entity_id", "entity_type"]),
    ("ix_tagged_item_entity_id_entity_type", "tagged_item", ["entity_id", "entity_type"]),
]


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)
