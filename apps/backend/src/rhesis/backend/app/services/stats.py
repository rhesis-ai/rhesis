from datetime import datetime, timedelta
from operator import itemgetter
from typing import Dict, List, Tuple, Type

from sqlalchemy import extract, func, inspect
from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app.models import TypeLookup

# ============================================================================
# Helper Functions for Dimension Stats
# ============================================================================


def _process_dimension_stats(stats: List[Tuple], top: int | None = None) -> Dict:
    """Helper function to process dimension statistics with top N items"""
    # Filter out items with zero counts and convert None to "None"
    non_zero_stats = [
        (str(name) if name is not None else "None", count) for name, count in stats if count > 0
    ]

    # Sort by count in descending order
    sorted_stats = sorted(non_zero_stats, key=itemgetter(1), reverse=True)

    if not top:
        # Return all non-zero items maintaining sorting
        return dict(sorted_stats)

    # Take top N items
    top_items = sorted_stats[:top]

    # Calculate sum of remaining items
    others_sum = sum(count for _, count in sorted_stats[top:])

    # Create breakdown dictionary maintaining order
    breakdown = dict(top_items)
    if others_sum > 0:
        breakdown["Others"] = others_sum

    return breakdown


def _get_dimension_stats(db: Session, model, join_column, entity_column, extra_filters=None):
    """Helper to get stats for a dimension"""
    query = (
        db.query(model.name, func.count(entity_column))
        .outerjoin(model, join_column)
        .group_by(model.name)
    )

    # Apply extra filters if provided, without checking the boolean value
    if extra_filters is not None:
        query = query.filter(extra_filters)

    return query.all()


def _get_entity_dimensions(entity_model: Type, db: Session) -> List[Dict]:
    """Automatically discover dimensions from entity model relationships."""
    dimensions = []
    inspector = inspect(entity_model)

    # Pre-load relationship metadata to avoid repeated inspection
    relationships = list(inspector.relationships)

    for rel in relationships:
        # Skip many-to-many relationships and those without name attribute
        if rel.secondary is not None or not hasattr(rel.mapper.class_, "name"):
            continue

        target_model = rel.mapper.class_
        foreign_key = list(rel.local_columns)[0]

        dimension = {
            "name": rel.key,
            "model": target_model,
            "join_column": foreign_key == target_model.id,
            "entity_column": foreign_key,
        }

        # Special handling for Status model
        if target_model.__name__ == "Status":
            # Get or create the entity type lookup for this entity model
            dimension["extra_filters"] = target_model.entity_type_id.in_(
                db.query(TypeLookup.id)
                .filter(
                    TypeLookup.type_name == "EntityType",
                    TypeLookup.type_value == entity_model.__name__,
                )
                .subquery()
            )

        dimensions.append(dimension)

    return dimensions


def _get_filtered_dimension_stats(
    db: Session, dimension: Dict, related_model: Type, related_ids: List[str]
):
    """
    Helper to get dimension stats filtered by related entity IDs with optimized session handling
    """

    # Create materialized subquery for better performance
    related_subquery = (
        db.query(related_model.id).filter(related_model.id.in_(related_ids)).subquery()
    )

    # Build the main query
    main_query = (
        db.query(dimension["model"].name, func.count(dimension["entity_column"]))
        .join(related_subquery, related_model.id == related_subquery.c.id)
        .outerjoin(dimension["model"], dimension["join_column"])
        .group_by(dimension["model"].name)
        .statement
    )

    # Execute the query
    result = db.execute(main_query).fetchall()

    return result


# ============================================================================
# Historical Stats Functions
# ============================================================================


def _calculate_monthly_counts(
    db: Session, model: Type, start_date: datetime, end_date: datetime, subquery=None
) -> List[Tuple]:
    """Calculate monthly counts for a model within a date range."""
    query = db.query(
        extract("year", model.created_at).label("year"),
        extract("month", model.created_at).label("month"),
        func.count(model.id).label("count"),
    ).filter(model.created_at >= start_date)

    if subquery is not None:
        query = query.join(subquery, model.id == subquery.c.id)

    return query.group_by("year", "month").order_by("year", "month").all()


def _get_historical_stats(db: Session, entity_model: Type, months: int = 6, subquery=None) -> Dict:
    """Calculate historical statistics for the last N months."""
    print(f"Starting historical stats calculation for {entity_model.__name__}")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30 * months)

    print(f"Date range: {start_date.isoformat()} to {end_date.isoformat()}")

    # Get monthly counts
    monthly_counts = _calculate_monthly_counts(db, entity_model, start_date, end_date, subquery)
    print(f"Found {len(monthly_counts)} monthly records")

    # Initialize history with all months in the range
    history = {}
    running_total = 0

    # First, create a dictionary of actual counts
    actual_counts = {}
    for year, month, count in monthly_counts:
        date_key = f"{int(year)}-{int(month):02d}"
        actual_counts[date_key] = count
        print(f"Month {date_key}: {count} records")

    # Now fill in the history with cumulative counts
    current_date = start_date
    while current_date <= end_date:
        date_key = f"{current_date.year}-{current_date.month:02d}"
        if date_key in actual_counts:
            # Add this month's count to the running total
            running_total += actual_counts[date_key]
        history[date_key] = running_total
        # Move to next month
        current_date = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1)

    result = {
        "period": f"Last {months} months",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "monthly_counts": history,
    }

    return result


# ============================================================================
# Main Stats Functions
# ============================================================================


def get_entity_stats(
    db: Session,
    entity_model: Type,
    organization_id: str | None = None,
    top: int | None = None,
    category_columns: List[str] | None = None,
    months: int = 6,
) -> Dict:
    """Get comprehensive statistics about an entity."""

    # Get total count
    total_count = db.query(func.count(entity_model.id)).scalar()

    # Initialize stats dictionary
    stats = {
        "total": total_count,
        "stats": {},
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "organization_id": str(organization_id) if organization_id else None,
            "entity_type": entity_model.__name__,
        },
    }

    # Add historical stats
    stats["history"] = _get_historical_stats(db, entity_model, months)

    # Get dimensions automatically from model
    dimensions = _get_entity_dimensions(entity_model, db)

    # Process each dimension
    for dim in dimensions:
        dimension_stats = _get_dimension_stats(
            db, dim["model"], dim["join_column"], dim["entity_column"], dim.get("extra_filters")
        )
        total = sum(count for _, count in dimension_stats)
        if total > 0:
            stats["stats"][dim["name"]] = {
                "dimension": dim["name"],
                "total": total,
                "breakdown": _process_dimension_stats(dimension_stats, top),
            }

    # Handle category columns if provided
    if category_columns:
        print(f"\nProcessing {len(category_columns)} category columns")
        for column_name in category_columns:
            if hasattr(entity_model, column_name):
                print(f"Processing category column: {column_name}")
                column_stats = (
                    db.query(getattr(entity_model, column_name), func.count(entity_model.id))
                    .group_by(getattr(entity_model, column_name))
                    .all()
                )

                # Convert to string and filter out None values
                stats_processed = [
                    (str(value), count) for value, count in column_stats if value is not None
                ]
                total = sum(count for _, count in stats_processed)
                if total > 0:
                    stats["stats"][column_name] = {
                        "dimension": column_name,
                        "total": total,
                        "breakdown": _process_dimension_stats(stats_processed, top),
                    }

    return stats


def get_related_stats(
    db: Session,
    entity_model: Type,
    related_model: Type,
    relationship_attr: str,
    entity_id: str | None = None,
    organization_id: str | None = None,
    top: int | None = None,
    category_columns: List[str] | None = None,
    months: int = 6,
) -> Dict:
    """Get statistics about related entities, optionally filtered by an entity."""

    # Initialize stats dictionary with empty values
    stats = {
        "total": 0,
        "stats": {},
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "organization_id": str(organization_id) if organization_id else None,
            "entity_type": related_model.__name__,
            "source_entity_type": entity_model.__name__,
            "source_entity_id": str(entity_id) if entity_id else None,
        },
    }

    # Get related IDs based on whether we're filtering by entity
    if entity_id:
        print(f"Getting related IDs for entity {entity_id}")
        entity_with_related = (
            db.query(entity_model)
            .filter_by(id=entity_id)
            .options(joinedload(getattr(entity_model, relationship_attr)))
            .first()
        )

        if not entity_with_related:
            print("No entity found with the given ID")
            return stats

        related_ids = [entity.id for entity in getattr(entity_with_related, relationship_attr)]
        if not related_ids:
            print("No related entities found")
            return stats

        stats["total"] = len(related_ids)
        print(f"Found {len(related_ids)} related entities")
    else:
        print("Getting all related entity IDs")
        related_ids = [id for (id,) in db.query(related_model.id).all()]
        stats["total"] = len(related_ids)
        print(f"Found {len(related_ids)} total entities")

    # Add historical stats for related entities
    if related_ids:
        # Create a subquery for the related entities
        related_subquery = (
            db.query(related_model.id).filter(related_model.id.in_(related_ids)).subquery()
        )

        stats["history"] = _get_historical_stats(db, related_model, months, related_subquery)

    else:
        # Add empty historical stats
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30 * months)
        stats["history"] = {
            "period": f"Last {months} months",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "monthly_counts": {},
        }

    # Get dimensions in a single inspection
    dimensions = _get_entity_dimensions(related_model, db)

    # Process dimensions in bulk
    if related_ids:
        for dim in dimensions:
            with db.begin_nested():  # Use savepoint for each dimension query
                dimension_stats = _get_filtered_dimension_stats(db, dim, related_model, related_ids)
                total = sum(count for _, count in dimension_stats)
                if total > 0:
                    stats["stats"][dim["name"]] = {
                        "dimension": dim["name"],
                        "total": total,
                        "breakdown": _process_dimension_stats(dimension_stats, top),
                    }

    # Handle category columns if provided
    if category_columns and related_ids:
        print(f"\nProcessing {len(category_columns)} category columns")
        for column_name in category_columns:
            if hasattr(related_model, column_name):
                print(f"Processing category column: {column_name}")
                # Create materialized subquery for better performance
                related_subquery = (
                    db.query(related_model.id).filter(related_model.id.in_(related_ids)).subquery()
                )

                # Get category stats with optimized query
                column_stats = db.execute(
                    db.query(getattr(related_model, column_name), func.count(related_model.id))
                    .join(related_subquery, related_model.id == related_subquery.c.id)
                    .group_by(getattr(related_model, column_name))
                    .statement
                ).fetchall()

                # Convert to string and filter out None values
                stats_processed = [
                    (str(value), count) for value, count in column_stats if value is not None
                ]
                total = sum(count for _, count in stats_processed)
                if total > 0:
                    stats["stats"][column_name] = {
                        "dimension": column_name,
                        "total": total,
                        "breakdown": _process_dimension_stats(stats_processed, top),
                    }
                    print(f"Added stats for category {column_name} with total {total}")

    return stats
