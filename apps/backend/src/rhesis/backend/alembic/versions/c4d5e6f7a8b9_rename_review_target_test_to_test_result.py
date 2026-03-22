"""rename review target type 'test' to 'test_result'

Normalizes all existing review target types from 'test' to 'test_result'
to support the new multi-target review system (test_result, turn, metric).

Revision ID: c4d5e6f7a8b9
Revises: d3e4f5a6b7c8
Create Date: 2026-03-11

"""

from typing import Sequence, Union

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE test_result
        SET test_reviews = jsonb_set(
            test_reviews,
            '{reviews}',
            (
                SELECT COALESCE(jsonb_agg(
                    CASE
                        WHEN r->'target'->>'type' = 'test'
                        THEN jsonb_set(r, '{target,type}', '"test_result"')
                        ELSE r
                    END
                ), '[]'::jsonb)
                FROM jsonb_array_elements(test_reviews->'reviews') AS r
            )
        )
        WHERE test_reviews IS NOT NULL
          AND test_reviews->'reviews' IS NOT NULL
          AND jsonb_typeof(test_reviews->'reviews') = 'array'
          AND EXISTS (
              SELECT 1
              FROM jsonb_array_elements(test_reviews->'reviews') AS r
              WHERE r->'target'->>'type' = 'test'
          )
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE test_result
        SET test_reviews = jsonb_set(
            test_reviews,
            '{reviews}',
            (
                SELECT COALESCE(jsonb_agg(
                    CASE
                        WHEN r->'target'->>'type' = 'test_result'
                        THEN jsonb_set(r, '{target,type}', '"test"')
                        ELSE r
                    END
                ), '[]'::jsonb)
                FROM jsonb_array_elements(test_reviews->'reviews') AS r
            )
        )
        WHERE test_reviews IS NOT NULL
          AND test_reviews->'reviews' IS NOT NULL
          AND jsonb_typeof(test_reviews->'reviews') = 'array'
          AND EXISTS (
              SELECT 1
              FROM jsonb_array_elements(test_reviews->'reviews') AS r
              WHERE r->'target'->>'type' = 'test_result'
          )
    """)
