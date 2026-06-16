"""merge rbac rls, conversation-id, and auth-provider heads

Revision ID: 7d8e9f0a1b2c
Revises: 33e3f87f44aa, a1c2d3e4f5g6, 6c7d8e9f0a1b
Create Date: 2026-06-16

Three independent heads accumulated:
- 33e3f87f44aa (add_conversation_id_to_trace) — from main, unmerged
- a1c2d3e4f5g6 (add_auth_provider_columns) — SSO-related, from a1b2c3d4e5f8 fork
- 6c7d8e9f0a1b (add_rls_to_organization_member) — RBAC SP8 work

This empty merge makes ``alembic upgrade head`` (singular) unambiguous again.
"""

from typing import Sequence, Union

revision: str = "7d8e9f0a1b2c"
down_revision: Union[str, None] = ("33e3f87f44aa", "a1c2d3e4f5g6", "6c7d8e9f0a1b")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
