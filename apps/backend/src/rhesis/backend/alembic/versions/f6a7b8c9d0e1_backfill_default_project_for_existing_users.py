"""Backfill default_project user setting for existing users

The default_project setting (user_settings -> 'default_project') is set going
forward whenever a user is first enrolled in a project. Users that existed
before that logic landed have no default, so the frontend cannot auto-select a
project for them on login.

This migration sets default_project for every user that does not already have
one, choosing:
  1. the earliest-created project the user owns (owner_id or user_id = user.id), else
  2. the user's earliest-joined project membership.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            WITH candidates AS (
                SELECT
                    u.id   AS user_id,
                    p.id   AS project_id,
                    p.name AS project_name,
                    CASE WHEN p.owner_id = u.id OR p.user_id = u.id
                         THEN 0 ELSE 1 END                 AS owns_rank,
                    p.created_at                            AS project_created,
                    COALESCE(pm.created_at, p.created_at)   AS join_time
                FROM "user" u
                JOIN project_membership pm
                  ON pm.user_id = u.id
                 AND pm.organization_id = u.organization_id
                JOIN project p
                  ON p.id = pm.project_id
                WHERE u.user_settings -> 'default_project' IS NULL
                  AND (u.deleted_at IS NULL OR u.deleted_at > now())
                  AND (p.deleted_at IS NULL OR p.deleted_at > now())
            ),
            chosen AS (
                SELECT DISTINCT ON (user_id)
                    user_id,
                    project_id,
                    project_name
                FROM candidates
                ORDER BY
                    user_id,
                    owns_rank ASC,
                    CASE WHEN owns_rank = 0 THEN project_created ELSE join_time END ASC
            )
            UPDATE "user" u
            SET user_settings = jsonb_set(
                    COALESCE(u.user_settings, '{}'::jsonb),
                    '{default_project}',
                    jsonb_build_object(
                        'project_id', chosen.project_id::text,
                        'name', chosen.project_name
                    ),
                    true
                )
            FROM chosen
            WHERE u.id = chosen.user_id
            """
        )
    )


def downgrade() -> None:
    # Remove the default_project key from every user's settings.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE "user"
            SET user_settings = user_settings #- '{default_project}'
            WHERE user_settings ? 'default_project'
            """
        )
    )
