"""
Reusable utility for syncing metrics from initial_data.json to existing organizations.

This module provides idempotent functions to ensure all organizations have the latest
metrics defined in initial_data.json. Perfect for use in migrations when adding new metrics.

Usage in migrations:
    from rhesis.backend.alembic.utils.metric_sync import sync_metrics_to_organizations

    def upgrade() -> None:
        bind = op.get_bind()
        session = Session(bind=bind)
        sync_metrics_to_organizations(session)
        session.commit()
        session.close()
"""

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import EntityType
from rhesis.backend.app.utils.crud_utils import (
    get_or_create_entity,
    get_or_create_status,
    get_or_create_type_lookup,
)


def load_metrics_from_initial_data() -> List[Dict[str, Any]]:
    """
    Load metrics from initial_data.json file.

    Returns:
        List of metric definitions from initial_data.json
    """
    # Get the path to initial_data.json relative to this file
    current_dir = Path(__file__).parent
    initial_data_path = current_dir.parent.parent / "app" / "services" / "initial_data.json"

    with open(initial_data_path, "r") as f:
        data = json.load(f)

    return data.get("metric", [])


def sync_metrics_to_organizations(
    session: Session, verbose: bool = True, commit: bool = False
) -> Dict[str, int]:
    """
    Sync all metrics from initial_data.json to all existing organizations.

    This function is fully idempotent - it will only create metrics that don't
    already exist in each organization. It's safe to run multiple times.

    Args:
        session: SQLAlchemy database session
        verbose: If True, print progress messages
        commit: If True, commit the session after syncing. If False, caller is responsible.

    Returns:
        Dictionary with stats: {
            'total_created': int,
            'total_skipped': int,
            'total_errors': int,
            'organizations_processed': int
        }
    """
    stats = {
        "total_created": 0,
        "total_skipped": 0,
        "total_errors": 0,
        "organizations_processed": 0,
    }

    try:
        # Load metrics from initial_data.json (single source of truth)
        if verbose:
            print("\n📖 Loading metrics from initial_data.json...")

        all_metrics = load_metrics_from_initial_data()

        if verbose:
            print(f"   Found {len(all_metrics)} metric definitions")

        # Get all organizations
        organizations = session.query(models.Organization).all()

        if verbose:
            print(f"   Found {len(organizations)} organization(s)\n")

        for org in organizations:
            organization_id = str(org.id)
            # Use owner_id or fall back to user_id
            user_id = org.owner_id or org.user_id

            # Skip if no valid user_id
            if not user_id:
                if verbose:
                    print(f"  ⚠ Skipping org {organization_id}: No owner or user")
                continue

            # Convert to string after validation
            user_id = str(user_id)

            # Get existing metrics for this organization
            existing_metrics = (
                session.query(models.Metric).filter(models.Metric.organization_id == org.id).all()
            )
            existing_metric_names = {m.name for m in existing_metrics}

            org_created = 0
            org_skipped = 0
            org_errors = 0

            for metric_item in all_metrics:
                metric_name = metric_item["name"]

                # Skip if metric already exists (idempotent)
                if metric_name in existing_metric_names:
                    org_skipped += 1
                    continue

                try:
                    # Get or create the metric type
                    metric_type = get_or_create_type_lookup(
                        db=session,
                        type_name="MetricType",
                        type_value=metric_item["metric_type"],
                        organization_id=organization_id,
                        user_id=user_id,
                        commit=False,
                    )

                    # Get or create the backend type
                    backend_type = get_or_create_type_lookup(
                        db=session,
                        type_name="BackendType",
                        type_value=metric_item["backend_type"],
                        organization_id=organization_id,
                        user_id=user_id,
                        commit=False,
                    )

                    # Get or create the status
                    status = get_or_create_status(
                        db=session,
                        name=metric_item["status"],
                        entity_type=EntityType.METRIC,
                        organization_id=organization_id,
                        user_id=user_id,
                        commit=False,
                    )

                    # Create metric data
                    metric_data = {
                        "name": metric_item["name"],
                        "description": metric_item["description"],
                        "evaluation_prompt": metric_item["evaluation_prompt"],
                        "evaluation_steps": metric_item.get("evaluation_steps"),
                        "reasoning": metric_item.get("reasoning"),
                        "score_type": metric_item["score_type"],
                        "min_score": metric_item.get("min_score"),
                        "max_score": metric_item.get("max_score"),
                        "threshold": metric_item.get("threshold"),
                        "explanation": metric_item.get("explanation"),
                        "ground_truth_required": metric_item.get("ground_truth_required", False),
                        "context_required": metric_item.get("context_required", False),
                        "class_name": metric_item.get("class_name"),
                        "evaluation_examples": metric_item.get("evaluation_examples"),
                        "threshold_operator": metric_item.get("threshold_operator", ">="),
                        "reference_score": metric_item.get("reference_score"),
                        "categories": metric_item.get("categories"),
                        "passing_categories": metric_item.get("passing_categories"),
                        "metric_scope": metric_item.get("metric_scope"),
                        "metric_type_id": metric_type.id,
                        "backend_type_id": backend_type.id,
                        "status_id": status.id,
                        "user_id": uuid.UUID(user_id),
                        "owner_id": uuid.UUID(user_id),
                    }

                    # Create the metric
                    metric = get_or_create_entity(
                        db=session,
                        model=models.Metric,
                        entity_data=metric_data,
                        organization_id=organization_id,
                        user_id=user_id,
                        commit=False,
                    )

                    # Process behavior associations
                    behavior_names = metric_item.get("behaviors", [])
                    for behavior_name in behavior_names:
                        behavior = (
                            session.query(models.Behavior)
                            .filter(
                                models.Behavior.name == behavior_name,
                                models.Behavior.organization_id == org.id,
                            )
                            .first()
                        )
                        if behavior and behavior not in metric.behaviors:
                            metric.behaviors.append(behavior)

                    org_created += 1

                except Exception as e:
                    if verbose:
                        print(
                            f"  ✗ Error creating metric '{metric_name}' "
                            f"for org {organization_id}: {e}"
                        )
                    org_errors += 1
                    continue

            stats["total_created"] += org_created
            stats["total_skipped"] += org_skipped
            stats["total_errors"] += org_errors
            stats["organizations_processed"] += 1

            if verbose and org_created > 0:
                print(f"  ✓ Org {organization_id}: created {org_created}, skipped {org_skipped}")

        if commit:
            session.commit()

        if verbose:
            print("\n✅ Metric sync complete!")
            print(f"   Created: {stats['total_created']} metrics")
            print(f"   Skipped (already exist): {stats['total_skipped']} metrics")
            if stats["total_errors"] > 0:
                print(f"   Errors: {stats['total_errors']} metrics")
            print()

    except Exception as e:
        if verbose:
            print(f"\n❌ Metric sync failed: {e}\n")
        raise

    return stats


def remove_metrics_from_organizations(
    session: Session, metric_names: List[str], verbose: bool = True, commit: bool = False
) -> int:
    """
    Remove specific metrics from all organizations.

    Useful for downgrade migrations.

    Args:
        session: SQLAlchemy database session
        metric_names: List of metric names to remove
        verbose: If True, print progress messages
        commit: If True, commit the session after removal. If False, caller is responsible.

    Returns:
        Number of metrics deleted
    """
    try:
        if verbose:
            print(f"\n🗑 Removing metrics: {', '.join(metric_names)}...")

        # Find metrics to delete
        metrics_to_delete = (
            session.query(models.Metric).filter(models.Metric.name.in_(metric_names)).all()
        )

        deleted_count = len(metrics_to_delete)

        # Delete each metric individually
        for metric in metrics_to_delete:
            session.delete(metric)

        if commit:
            session.commit()

        if verbose:
            print(f"   Removed {deleted_count} metric(s)\n")

        return deleted_count

    except Exception as e:
        if verbose:
            print(f"\n❌ Metric removal failed: {e}\n")
        raise
