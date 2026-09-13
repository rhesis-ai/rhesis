"""merge release v0.15.2 back onto the performance head

Revision ID: a0a48c28ad64
Revises: c3a4b5d6e7f8, b8d2f3e4a5c6
Create Date: 2026-09-13

release/v0.15.2 was cut before a7c1e2d3f4b5, so its own c3a4b5d6e7f8 and main's
b8d2f3e4a5c6 both hang off b7e1c9d4a2f3. Re-pointing either one is not an option
here: c3a4b5d6e7f8 ships from the release branch, and moving an applied
revision's parent makes Alembic treat the new parent as applied on databases
that never ran it. This empty merge joins the two tips instead, so
``alembic upgrade head`` reaches every migration from either side.
"""

from typing import Sequence, Union

revision: str = "a0a48c28ad64"
down_revision: Union[str, None] = ("c3a4b5d6e7f8", "b8d2f3e4a5c6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
