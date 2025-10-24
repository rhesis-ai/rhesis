"""Main statistics calculator class with improved maintainability."""

from datetime import datetime, timedelta
from operator import itemgetter
from typing import Any, Dict, List, Optional, Tuple, Type

from sqlalchemy import extract, func, inspect
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from rhesis.backend.app.models import TypeLookup

from .config import DimensionInfo, StatsConfig, StatsResult
from .utils import timer


class StatsCalculator:
    """Main class for stats calculations with improved maintainability"""

    def __init__(self, db: Session, config: StatsConfig = None, organization_id: str = None):
        self.db = db
        self.config = config or StatsConfig()
        self.organization_id = organization_id  # SECURITY CRITICAL: Store organization context

    # ============================================================================
    # Core Stats Processing Methods
    # ============================================================================

    def _apply_organization_filter(self, query, model):
        """Apply organization filtering to a query if organization_id is set and model supports it"""
        if self.organization_id and hasattr(model, "organization_id"):
            from uuid import UUID

            # Handle both string and UUID inputs
            if isinstance(self.organization_id, UUID):
                org_id = self.organization_id
            else:
                org_id = UUID(self.organization_id)
            query = query.filter(model.organization_id == org_id)
        return query

    def _process_dimension_breakdown(self, stats: List[Tuple], top: Optional[int] = None) -> Dict:
        """Process dimension statistics with optional top N filtering"""
        # Filter out items with zero counts and convert None to "None"
        non_zero_stats = [
            (str(name) if name is not None else "None", count) for name, count in stats if count > 0
        ]

        # Sort by count in descending order
        sorted_stats = sorted(non_zero_stats, key=itemgetter(1), reverse=True)

        if not top:
            return dict(sorted_stats)

        # Take top N items and calculate others
        top_items = sorted_stats[:top]
        others_sum = sum(count for _, count in sorted_stats[top:])

        breakdown = dict(top_items)
        if others_sum > 0:
            breakdown["Others"] = others_sum

        return breakdown

    def _discover_entity_dimensions(self, entity_model: Type) -> List[DimensionInfo]:
        """Discover dimensions from entity model relationships"""
        dimensions = []
        inspector = inspect(entity_model)

        for rel in inspector.relationships:
            # Skip many-to-many relationships and those without name attribute
            if rel.secondary is not None or not hasattr(rel.mapper.class_, "name"):
                continue

            target_model = rel.mapper.class_
            foreign_key = list(rel.local_columns)[0]

            dimension = DimensionInfo(
                name=rel.key,
                model=target_model,
                join_column=foreign_key == target_model.id,
                entity_column=foreign_key,
            )

            # Special handling for Status model
            if target_model.__name__ == "Status":
                # Apply organization filtering to TypeLookup query (SECURITY CRITICAL)
                type_lookup_query = self.db.query(TypeLookup.id).filter(
                    TypeLookup.type_name == "EntityType",
                    TypeLookup.type_value == entity_model.__name__,
                )
                type_lookup_query = self._apply_organization_filter(type_lookup_query, TypeLookup)

                dimension.extra_filters = target_model.entity_type_id.in_(
                    type_lookup_query.scalar_subquery()
                )

            dimensions.append(dimension)

        return dimensions

    # ============================================================================
    # Query Building Methods
    # ============================================================================

    def _build_dimension_query(self, dimension: DimensionInfo, related_ids_subquery) -> Select:
        """Build optimized dimension query using JOINs"""

        query = (
            self.db.query(dimension.model.name, func.count())
            .select_from(self.db.query().subquery())  # Base from related entities
            .join(related_ids_subquery)
            .outerjoin(dimension.model, dimension.join_column)
            .group_by(dimension.model.name)
        )

        # Apply organization filtering to dimension model (SECURITY CRITICAL)
        query = self._apply_organization_filter(query, dimension.model)

        if dimension.extra_filters is not None:
            query = query.filter(dimension.extra_filters)

        return query

    def _execute_dimension_stats(
        self, dimension: DimensionInfo, related_model: Type, related_ids_subquery
    ) -> List[Tuple]:
        """Execute dimension stats query with timing"""
        with timer(f"dimension stats for {dimension.name}", self.config.enable_timing):
            # Use direct JOIN with the subquery instead of materializing IDs
            main_query = (
                self.db.query(dimension.model.name, func.count(related_model.id))
                .select_from(related_model)
                .join(related_ids_subquery, related_model.id == related_ids_subquery.c.id)
                .outerjoin(dimension.model, dimension.join_column)
                .group_by(dimension.model.name)
            )

            # Apply organization filtering to dimension model (SECURITY CRITICAL)
            main_query = self._apply_organization_filter(main_query, dimension.model)

            # Apply extra filters if provided
            if dimension.extra_filters is not None:
                main_query = main_query.filter(dimension.extra_filters)

            return main_query.all()

    # ============================================================================
    # Historical Stats Methods
    # ============================================================================

    def _calculate_monthly_counts(
        self, model: Type, start_date: datetime, end_date: datetime, subquery=None
    ) -> List[Tuple]:
        """Calculate monthly counts for a model within a date range"""
        with timer(f"monthly counts calculation for {model.__name__}", self.config.enable_timing):
            query = self.db.query(
                extract("year", model.created_at).label("year"),
                extract("month", model.created_at).label("month"),
                func.count(model.id).label("count"),
            ).filter(model.created_at >= start_date)

            # Apply organization filtering (SECURITY CRITICAL)
            query = self._apply_organization_filter(query, model)

            if subquery is not None:
                query = query.join(subquery, model.id == subquery.c.id)

            return query.group_by("year", "month").order_by("year", "month").all()

    def _process_historical_data(
        self, monthly_counts: List[Tuple], start_date: datetime, end_date: datetime
    ) -> Dict[str, int]:
        """Process monthly counts into cumulative history"""
        with timer("history processing", self.config.enable_timing):
            # Create dictionary of actual counts
            actual_counts = {}
            for year, month, count in monthly_counts:
                date_key = f"{int(year)}-{int(month):02d}"
                actual_counts[date_key] = count
                if self.config.enable_debug_logging:
                    print(f"Month {date_key}: {count} records")

            # Fill in history with cumulative counts
            history = {}
            running_total = 0
            current_date = start_date

            while current_date <= end_date:
                date_key = f"{current_date.year}-{current_date.month:02d}"
                if date_key in actual_counts:
                    running_total += actual_counts[date_key]
                history[date_key] = running_total
                # Move to next month
                current_date = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1)

            return history

    def _get_historical_stats(self, entity_model: Type, months: int = None, subquery=None) -> Dict:
        """Calculate historical statistics for the last N months"""
        months = months or self.config.default_months

        with timer(
            f"historical stats calculation for {entity_model.__name__}", self.config.enable_timing
        ):
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30 * months)

            if self.config.enable_debug_logging:
                print(f"Date range: {start_date.isoformat()} to {end_date.isoformat()}")

            # Get monthly counts
            monthly_counts = self._calculate_monthly_counts(
                entity_model, start_date, end_date, subquery
            )

            if self.config.enable_debug_logging:
                print(f"Found {len(monthly_counts)} monthly records")

            # Process into history
            history = self._process_historical_data(monthly_counts, start_date, end_date)

            return {
                "period": f"Last {months} months",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "monthly_counts": history,
            }

    # ============================================================================
    # Category Processing Methods
    # ============================================================================

    def _process_category_columns(
        self,
        entity_model: Type,
        category_columns: List[str],
        top: Optional[int],
        related_ids_subquery=None,
    ) -> Dict[str, Any]:
        """Process category columns efficiently"""
        category_stats = {}

        if not category_columns:
            return category_stats

        with timer(
            f"processing {len(category_columns)} category columns", self.config.enable_timing
        ):
            for column_name in category_columns:
                if not hasattr(entity_model, column_name):
                    continue

                with timer(f"category column {column_name}", self.config.enable_timing):
                    if related_ids_subquery is not None:
                        # Use JOIN for filtered results
                        column_stats = (
                            self.db.query(
                                getattr(entity_model, column_name), func.count(entity_model.id)
                            )
                            .select_from(entity_model)
                            .join(
                                related_ids_subquery, entity_model.id == related_ids_subquery.c.id
                            )
                            .group_by(getattr(entity_model, column_name))
                            .all()
                        )
                    else:
                        # Direct query for unfiltered results - apply organization filtering (SECURITY CRITICAL)
                        column_query = self.db.query(
                            getattr(entity_model, column_name), func.count(entity_model.id)
                        )
                        column_query = self._apply_organization_filter(column_query, entity_model)
                        column_stats = column_query.group_by(
                            getattr(entity_model, column_name)
                        ).all()

                    # Process results
                    stats_processed = [
                        (str(value), count) for value, count in column_stats if value is not None
                    ]
                    total = sum(count for _, count in stats_processed)

                    if total > 0:
                        category_stats[column_name] = {
                            "dimension": column_name,
                            "total": total,
                            "breakdown": self._process_dimension_breakdown(stats_processed, top),
                        }

                        if self.config.enable_debug_logging:
                            print(f"Added stats for category {column_name} with total {total}")

        return category_stats

    # ============================================================================
    # Main Public Methods
    # ============================================================================

    def get_entity_stats(
        self,
        entity_model: Type,
        organization_id: Optional[str] = None,
        top: Optional[int] = None,
        category_columns: Optional[List[str]] = None,
        months: Optional[int] = None,
    ) -> Dict:
        """Get comprehensive statistics about an entity"""
        top = top or self.config.default_top_items
        months = months or self.config.default_months

        with timer(
            f"entity stats calculation for {entity_model.__name__}", self.config.enable_timing
        ):
            # Get total count
            with timer("total count query", self.config.enable_timing):
                total_count_query = self.db.query(func.count(entity_model.id))
                # Apply organization filtering (SECURITY CRITICAL)
                total_count_query = self._apply_organization_filter(total_count_query, entity_model)
                total_count = total_count_query.scalar()

            # Initialize result
            result = StatsResult(
                total=total_count,
                stats={},
                history={},
                metadata={
                    "generated_at": datetime.utcnow().isoformat(),
                    "organization_id": str(organization_id) if organization_id else None,
                    "entity_type": entity_model.__name__,
                },
            )

            # Add historical stats
            result.history = self._get_historical_stats(entity_model, months)

            # Get and process dimensions
            with timer("getting dimensions", self.config.enable_timing):
                dimensions = self._discover_entity_dimensions(entity_model)

            with timer("all dimensions processing", self.config.enable_timing):
                for dim in dimensions:
                    with timer(f"dimension {dim.name} processing", self.config.enable_timing):
                        # Apply organization filtering to both entity and dimension models (SECURITY CRITICAL)
                        dimension_query = (
                            self.db.query(dim.model.name, func.count(dim.entity_column))
                            .select_from(entity_model)
                            .outerjoin(dim.model, dim.join_column)
                        )
                        # Filter the base entity model by organization
                        dimension_query = self._apply_organization_filter(
                            dimension_query, entity_model
                        )
                        # Also filter the dimension model if it has organization_id
                        dimension_query = self._apply_organization_filter(
                            dimension_query, dim.model
                        )
                        dimension_stats = dimension_query.group_by(dim.model.name)

                        if dim.extra_filters is not None:
                            dimension_stats = dimension_stats.filter(dim.extra_filters)

                        dimension_results = dimension_stats.all()
                        total = sum(count for _, count in dimension_results)

                        if total > 0:
                            result.stats[dim.name] = {
                                "dimension": dim.name,
                                "total": total,
                                "breakdown": self._process_dimension_breakdown(
                                    dimension_results, top
                                ),
                            }

            # Process category columns
            category_stats = self._process_category_columns(
                entity_model, category_columns or [], top
            )
            result.stats.update(category_stats)

            return {
                "total": result.total,
                "stats": result.stats,
                "history": result.history,
                "metadata": result.metadata,
            }

    def get_related_stats(
        self,
        entity_model: Type,
        related_model: Type,
        relationship_attr: str,
        entity_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        top: Optional[int] = None,
        category_columns: Optional[List[str]] = None,
        months: Optional[int] = None,
    ) -> Dict:
        """Get statistics about related entities, optionally filtered by an entity"""
        top = top or self.config.default_top_items
        months = months or self.config.default_months

        with timer(
            f"related stats calculation for {related_model.__name__}", self.config.enable_timing
        ):
            # Initialize result
            result = StatsResult(
                total=0,
                stats={},
                history={},
                metadata={
                    "generated_at": datetime.utcnow().isoformat(),
                    "organization_id": str(organization_id) if organization_id else None,
                    "entity_type": related_model.__name__,
                    "source_entity_type": entity_model.__name__,
                    "source_entity_id": str(entity_id) if entity_id else None,
                },
            )

            # Create subquery for related entities
            with timer("getting related IDs", self.config.enable_timing):
                related_ids_subquery = self._create_related_ids_subquery(
                    entity_model, related_model, relationship_attr, entity_id
                )

                if related_ids_subquery is None:
                    return self._empty_stats_result(result, months)

                # Get total count - OPTIMIZED to use subquery instead of loading entities
                if entity_id:
                    # Count using the subquery instead of loading all entities
                    result.total = (
                        self.db.query(func.count()).select_from(related_ids_subquery).scalar()
                    )
                else:
                    # Apply organization filtering (SECURITY CRITICAL)
                    total_query = self.db.query(func.count(related_model.id))
                    total_query = self._apply_organization_filter(total_query, related_model)
                    result.total = total_query.scalar()

                if self.config.enable_debug_logging:
                    print(f"Found {result.total} total entities")

            if result.total == 0:
                return self._empty_stats_result(result, months)

            # Add historical stats
            result.history = self._get_historical_stats(related_model, months, related_ids_subquery)

            # Process dimensions
            with timer("getting dimensions", self.config.enable_timing):
                dimensions = self._discover_entity_dimensions(related_model)

            with timer("all dimensions processing", self.config.enable_timing):
                for dim in dimensions:
                    dimension_stats = self._execute_dimension_stats(
                        dim, related_model, related_ids_subquery
                    )
                    total = sum(count for _, count in dimension_stats)

                    if total > 0:
                        result.stats[dim.name] = {
                            "dimension": dim.name,
                            "total": total,
                            "breakdown": self._process_dimension_breakdown(dimension_stats, top),
                        }

            # Process category columns
            category_stats = self._process_category_columns(
                related_model, category_columns or [], top, related_ids_subquery
            )
            result.stats.update(category_stats)

            return {
                "total": result.total,
                "stats": result.stats,
                "history": result.history,
                "metadata": result.metadata,
            }

    # ============================================================================
    # Helper Methods
    # ============================================================================

    def _create_related_ids_subquery(
        self,
        entity_model: Type,
        related_model: Type,
        relationship_attr: str,
        entity_id: Optional[str],
    ):
        """Create subquery for related entity IDs"""
        if entity_id:
            if self.config.enable_debug_logging:
                print(f"Getting related IDs for entity {entity_id}")

            # PERFORMANCE OPTIMIZATION: Query association table directly instead of loading entities
            # This is critical for performance when dealing with large numbers of related entities
            inspector = inspect(entity_model)
            relationship = inspector.relationships.get(relationship_attr)

            if relationship is None:
                if self.config.enable_debug_logging:
                    print(f"No relationship found with name {relationship_attr}")
                return None

            # Check if it's a many-to-many relationship with an association table
            if relationship.secondary is not None:
                # For many-to-many (e.g., TestSet <-> Test), query the association table directly
                association_table = relationship.secondary

                # Determine which columns to use based on the relationship direction
                # The relationship.synchronize_pairs tells us which columns are linked
                if relationship.direction.name == "MANYTOMANY":
                    # Find the foreign key columns in the association table
                    for fk in association_table.foreign_keys:
                        if fk.column.table == entity_model.__table__:
                            entity_fk_col = fk.parent
                        elif fk.column.table == related_model.__table__:
                            related_fk_col = fk.parent

                    # Build efficient subquery using association table
                    # Label the column as 'id' so other methods can reference it consistently
                    related_ids_query = (
                        self.db.query(related_fk_col.label("id"))
                        .select_from(association_table)
                        .filter(entity_fk_col == entity_id)
                    )

                    # Apply organization filtering if the association table has organization_id
                    if "organization_id" in [col.name for col in association_table.columns]:
                        if self.organization_id:
                            from uuid import UUID

                            org_id = (
                                UUID(self.organization_id)
                                if not isinstance(self.organization_id, UUID)
                                else self.organization_id
                            )
                            related_ids_query = related_ids_query.filter(
                                association_table.c.organization_id == org_id
                            )

                    return related_ids_query.subquery()

            # Fallback to the old approach for one-to-many relationships
            # First check if entity exists
            entity_exists = self.db.query(entity_model.id).filter_by(id=entity_id).first()
            if not entity_exists:
                if self.config.enable_debug_logging:
                    print("No entity found with the given ID")
                return None

            # For one-to-many, we can still optimize by not loading full entities
            # Just get the count and IDs without joinedload
            related_query = (
                self.db.query(related_model.id)
                .join(
                    entity_model,
                    getattr(related_model, relationship.back_populates) == entity_model,
                )
                .filter(entity_model.id == entity_id)
            )

            return related_query.subquery()
        else:
            if self.config.enable_debug_logging:
                print("Getting all related entity IDs")
            # Apply organization filtering to related model query (SECURITY CRITICAL)
            related_query = self.db.query(related_model.id)
            related_query = self._apply_organization_filter(related_query, related_model)
            return related_query.subquery()

    def _empty_stats_result(self, result: StatsResult, months: int) -> Dict:
        """Create empty stats result with proper structure"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30 * months)

        result.history = {
            "period": f"Last {months} months",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "monthly_counts": {},
        }

        return {
            "total": result.total,
            "stats": result.stats,
            "history": result.history,
            "metadata": result.metadata,
        }
