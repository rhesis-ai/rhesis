"""Add Image type to TestType, TestSetType, and MetricScope type lookups

Revision ID: add_image_type_lookups
Revises: 7b998a6fe52d
Create Date: 2026-01-20

"""

from typing import Sequence, Union

from alembic import op

# Import our simple template loader
from rhesis.backend.alembic.utils.template_loader import (
    load_cleanup_type_lookup_template,
    load_type_lookup_template,
)

# revision identifiers, used by Alembic.
revision: str = "78a3f23a9d29"
down_revision: Union[str, None] = "7b998a6fe52d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Image entries to type_lookup table for TestType, TestSetType, and MetricScope
    image_type_values = """
        ('TestType', 'Image', 'Image generation and analysis tests'),
        ('TestSetType', 'Image', 'Test set containing image generation/analysis tests'),
        ('MetricScope', 'Image', 'Metric applies to image generation/analysis tests')
    """.strip()
    op.execute(load_type_lookup_template(image_type_values))


def downgrade() -> None:
    # Remove Image entries from type_lookup table for each type
    # TestType
    op.execute(load_cleanup_type_lookup_template("TestType", "'Image'"))
    # TestSetType
    op.execute(load_cleanup_type_lookup_template("TestSetType", "'Image'"))
    # MetricScope
    op.execute(load_cleanup_type_lookup_template("MetricScope", "'Image'"))
