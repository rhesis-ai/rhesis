"""Migrate metric data to SDK-compatible format

This migration performs data transformations to align the database with SDK expectations:
1. Convert score_type='binary' to 'categorical'
2. Populate categories and passing_categories for categorical metrics
3. Update class_name from 'RhesisPromptMetric' to 'NumericJudge' or 'CategoricalJudge'
"""

from alembic import op
import sqlalchemy as sa
from typing import Union, Sequence
import rhesis


# revision identifiers, used by Alembic.
revision: str = "415c0d01df0e"
down_revision: Union[str, None] = "078d2d5b5f9e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Migrate existing metric data to SDK-compatible format.
    """
    connection = op.get_bind()

    # Step 1: Convert binary score_type to categorical
    print("Step 1: Converting binary metrics to categorical...")
    result = connection.execute(
        sa.text("""
        UPDATE metric 
        SET score_type = 'categorical' 
        WHERE score_type = 'binary'
    """)
    )
    print(f"  → Converted {result.rowcount} binary metrics to categorical")

    # Step 2: Populate categories and passing_categories for categorical metrics
    print("Step 2: Populating categories for categorical metrics...")

    # For metrics with reference_score='True', set categories to ["True", "False"]
    result = connection.execute(
        sa.text("""
        UPDATE metric 
        SET 
            categories = '["True", "False"]'::jsonb,
            passing_categories = '["True"]'::jsonb
        WHERE score_type = 'categorical' 
          AND reference_score = 'True'
          AND categories IS NULL
    """)
    )
    print(f"  → Set True/False categories for {result.rowcount} metrics")

    # For metrics with reference_score='False', set categories to ["False", "True"]
    result = connection.execute(
        sa.text("""
        UPDATE metric 
        SET 
            categories = '["False", "True"]'::jsonb,
            passing_categories = '["False"]'::jsonb
        WHERE score_type = 'categorical' 
          AND reference_score = 'False'
          AND categories IS NULL
    """)
    )
    print(f"  → Set False/True categories for {result.rowcount} metrics")

    # For metrics with other reference_score values, create [reference_score, "other"]
    result = connection.execute(
        sa.text("""
        UPDATE metric 
        SET 
            categories = jsonb_build_array(reference_score, 'other'),
            passing_categories = jsonb_build_array(reference_score)
        WHERE score_type = 'categorical' 
          AND reference_score IS NOT NULL
          AND reference_score NOT IN ('True', 'False')
          AND categories IS NULL
    """)
    )
    print(f"  → Set custom categories for {result.rowcount} metrics")

    # For categorical metrics without reference_score, use default categories
    result = connection.execute(
        sa.text("""
        UPDATE metric 
        SET 
            categories = '["pass", "fail"]'::jsonb,
            passing_categories = '["pass"]'::jsonb
        WHERE score_type = 'categorical' 
          AND (reference_score IS NULL OR reference_score = '')
          AND categories IS NULL
    """)
    )
    print(f"  → Set default pass/fail categories for {result.rowcount} metrics")

    # Step 3: Update class_name for RhesisPromptMetric based on score_type
    print("Step 3: Updating class_name to SDK format...")

    # Numeric metrics: RhesisPromptMetric → NumericJudge
    result = connection.execute(
        sa.text("""
        UPDATE metric 
        SET class_name = 'NumericJudge'
        WHERE class_name = 'RhesisPromptMetric' 
          AND score_type = 'numeric'
    """)
    )
    print(f"  → Updated {result.rowcount} numeric metrics to NumericJudge")

    # Categorical metrics: RhesisPromptMetric → CategoricalJudge
    result = connection.execute(
        sa.text("""
        UPDATE metric 
        SET class_name = 'CategoricalJudge'
        WHERE class_name = 'RhesisPromptMetric' 
          AND score_type = 'categorical'
    """)
    )
    print(f"  → Updated {result.rowcount} categorical metrics to CategoricalJudge")

    # Step 4: Validation - Log final distribution
    print("\nMigration completed. Final metric distribution:")
    result = connection.execute(
        sa.text("""
        SELECT 
            class_name, 
            score_type, 
            COUNT(*) as count 
        FROM metric 
        GROUP BY class_name, score_type
        ORDER BY class_name, score_type
    """)
    )
    for row in result:
        print(f"  {row.class_name or 'NULL'} ({row.score_type}): {row.count}")

    # Validation checks
    print("\nValidation checks:")

    # Check for remaining binary metrics
    result = connection.execute(
        sa.text("""
        SELECT COUNT(*) as count FROM metric WHERE score_type = 'binary'
    """)
    )
    binary_count = result.fetchone().count
    print(f"  Binary metrics remaining: {binary_count} (should be 0)")

    # Check for remaining RhesisPromptMetric
    result = connection.execute(
        sa.text("""
        SELECT COUNT(*) as count FROM metric WHERE class_name = 'RhesisPromptMetric'
    """)
    )
    old_class_count = result.fetchone().count
    print(f"  RhesisPromptMetric remaining: {old_class_count} (should be 0)")

    # Check categorical metrics without categories
    result = connection.execute(
        sa.text("""
        SELECT COUNT(*) as count 
        FROM metric 
        WHERE score_type = 'categorical' AND categories IS NULL
    """)
    )
    missing_categories = result.fetchone().count
    print(f"  Categorical metrics without categories: {missing_categories} (should be 0)")

    if binary_count > 0 or old_class_count > 0 or missing_categories > 0:
        print("\n⚠️  WARNING: Some metrics were not migrated successfully!")
    else:
        print("\n✅ All metrics migrated successfully!")


def downgrade() -> None:
    """
    Rollback data migration changes.

    Note: This is a best-effort rollback. Some information loss may occur.
    """
    connection = op.get_bind()

    print("Rolling back metric data migration...")

    # Step 1: Restore class_name to RhesisPromptMetric
    print("Step 1: Restoring class_name to RhesisPromptMetric...")
    result = connection.execute(
        sa.text("""
        UPDATE metric 
        SET class_name = 'RhesisPromptMetric'
        WHERE class_name IN ('NumericJudge', 'CategoricalJudge')
    """)
    )
    print(f"  → Restored {result.rowcount} metrics to RhesisPromptMetric")

    # Step 2: Restore binary score_type for True/False categorical metrics
    print("Step 2: Restoring binary score_type...")
    result = connection.execute(
        sa.text("""
        UPDATE metric 
        SET score_type = 'binary'
        WHERE score_type = 'categorical'
          AND (
              (categories = '["True", "False"]'::jsonb AND passing_categories = '["True"]'::jsonb)
              OR (categories = '["False", "True"]'::jsonb AND passing_categories = '["False"]'::jsonb)
          )
    """)
    )
    print(f"  → Restored {result.rowcount} metrics to binary")

    # Step 3: Clear categories and passing_categories
    print("Step 3: Clearing categories fields...")
    result = connection.execute(
        sa.text("""
        UPDATE metric 
        SET 
            categories = NULL,
            passing_categories = NULL
    """)
    )
    print(f"  → Cleared categories for {result.rowcount} metrics")

    print("\n✅ Rollback completed!")
