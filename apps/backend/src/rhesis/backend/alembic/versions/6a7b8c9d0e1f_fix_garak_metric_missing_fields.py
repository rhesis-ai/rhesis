"""fix_garak_metric_missing_fields

This migration fixes Garak metrics that were dynamically created by the
Garak probe importer but are missing critical fields like:
- metric_scope (required for execution filtering)
- backend_type_id (required for proper backend identification)
- metric_type_id (required for metric type identification)
- status_id (required for status tracking)

These metrics were created when importing Garak probes and have
class_name='GarakDetectorMetric' but were missing required lookup IDs.

Uses the existing CRUD infrastructure to ensure consistency.

Revision ID: 6a7b8c9d0e1f
Revises: 5d7e4f2a3b1c
Create Date: 2026-01-25
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas

# revision identifiers, used by Alembic.
revision: str = "6a7b8c9d0e1f"
down_revision: Union[str, None] = "5d7e4f2a3b1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Fix Garak metrics that are missing required fields.

    Finds metrics with class_name='GarakDetectorMetric' that have missing
    metric_scope, backend_type_id, metric_type_id, or status_id and updates
    them using the existing CRUD infrastructure.
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        print("\n🔧 Fixing Garak metrics with missing fields...")

        # Find all Garak detector metrics (dynamically created by importer)
        garak_metrics = (
            session.query(models.Metric)
            .filter(models.Metric.class_name == "GarakDetectorMetric")
            .all()
        )

        if not garak_metrics:
            print("   No GarakDetectorMetric metrics found.")
            return

        print(f"   Found {len(garak_metrics)} GarakDetectorMetric(s)")

        fixed_count = 0
        for metric in garak_metrics:
            organization_id = str(metric.organization_id)
            user_id = str(metric.user_id)

            # Check what fields need fixing
            needs_scope = not metric.metric_scope
            needs_backend = not metric.backend_type_id
            needs_type = not metric.metric_type_id
            needs_status = not metric.status_id
            needs_owner = not metric.owner_id and metric.user_id

            if not any([needs_scope, needs_backend, needs_type, needs_status, needs_owner]):
                continue

            # Build update data - CRUD handles string -> ID conversions
            update_data = schemas.MetricUpdate()

            if needs_scope:
                update_data.metric_scope = ["Single-Turn"]
                print(f"   → Fixing metric_scope for '{metric.name}'")

            if needs_backend:
                update_data.backend_type = "garak"
                print(f"   → Fixing backend_type for '{metric.name}'")

            if needs_type:
                update_data.metric_type = "framework"
                print(f"   → Fixing metric_type for '{metric.name}'")

            if needs_owner:
                update_data.owner_id = metric.user_id
                print(f"   → Fixing owner_id for '{metric.name}'")

            # Use CRUD to update - handles type conversions and status
            crud.update_metric(
                db=session,
                metric_id=metric.id,
                metric=update_data,
                organization_id=organization_id,
                user_id=user_id,
            )

            # Handle status separately if needed (update_metric doesn't set default status)
            if needs_status:
                from rhesis.backend.app.constants import EntityType
                from rhesis.backend.app.utils.crud_utils import get_or_create_status

                status = get_or_create_status(
                    db=session,
                    name="New",
                    entity_type=EntityType.METRIC,
                    organization_id=organization_id,
                    user_id=user_id,
                    commit=False,
                )
                metric.status_id = status.id
                print(f"   → Fixing status_id for '{metric.name}'")

            fixed_count += 1

        session.commit()
        print(f"\n✅ Fixed {fixed_count} Garak metric(s)\n")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def downgrade() -> None:
    """
    No downgrade needed - fixing missing fields doesn't require reversal.

    The fields added are required for proper operation, so removing them
    would break functionality.
    """
    print("\n⚠ No downgrade action needed for this migration.\n")
