from typing import Callable, Dict, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import desc, inspect, or_
from sqlalchemy.orm import Query, RelationshipProperty, Session, joinedload, selectinload

# Removed unused imports - legacy tenant functions no longer needed
from rhesis.backend.app.utils.odata import apply_odata_filter
from rhesis.backend.app.utils.query_validation import (
    validate_odata_filter,
    validate_pagination,
    validate_sort_field,
    validate_sort_order,
)
from rhesis.backend.logging import logger

# Define a generic type variable
T = TypeVar("T")


class QueryBuilder:
    """
    A flexible query builder that allows selective application of filters and transformations.
    """

    def __init__(self, db: Session, model: Type[T]):
        self.db = db
        self.model = model
        # Always create a fresh query to avoid leaking state between requests
        try:
            self.query = db.query(model)
        except Exception as e:
            logger.debug(f"Error creating query in QueryBuilder: {e}")
            # If query creation fails, the session may be in a bad state
            # Log the error and raise it - caller should handle session issues
            logger.error(f"Failed to create query for model {model.__name__}: {e}")
            raise
        self._skip = 0
        self._limit = None
        self._sort_by = None
        self._sort_order = "asc"

    def with_joinedloads(
        self, skip_many_to_many: bool = True, skip_one_to_many: bool = False
    ) -> "QueryBuilder":
        """Apply joinedloads for relationships"""
        self.query = apply_joinedloads(self.query, self.model, skip_many_to_many, skip_one_to_many)
        return self

    def with_optimized_loads(
        self,
        skip_many_to_many: bool = True,
        skip_one_to_many: bool = False,
        nested_relationships: dict = None,
    ) -> "QueryBuilder":
        """Apply optimized loading strategy (selectinload for many-to-many, joinedload for others)"""
        self.query = apply_optimized_loads(
            self.query, self.model, skip_many_to_many, skip_one_to_many, nested_relationships
        )
        return self



    def with_organization_filter(self, organization_id: str = None) -> "QueryBuilder":
        """
        Apply organization filter with optimized approach - no session variables needed.
        
        Performance improvements:
        - Completely bypasses database session variables
        - No SHOW queries for organization context
        - Direct organization ID filtering
        """
        if has_organization_id(self.model):
            if organization_id:
                # Use direct organization_id filtering (optimized)
                self.query = self.query.filter(self.model.organization_id == organization_id)
            else:
                # No fallback - organization_id must be provided explicitly
                logger.warning(
                    f"with_organization_filter called without organization_id for model {self.model.__name__}. "
                    "This may result in data leakage across organizations."
                )
        return self

    def with_visibility_filter(self) -> "QueryBuilder":
        """Apply visibility filter if the model supports it"""
        if has_visibility(self.model):
            self.query = apply_visibility_filter(self.db, self.query, self.model)
        return self

    def with_odata_filter(self, filter_str: Optional[str]) -> "QueryBuilder":
        """Apply OData filter if provided"""
        if filter_str:
            validate_odata_filter(self.model, filter_str)
            self.query = apply_odata_filter(self.query, self.model, filter_str)
        return self

    def with_pagination(self, skip: int = 0, limit: Optional[int] = None) -> "QueryBuilder":
        """Add pagination parameters"""
        validate_pagination(skip, limit or 100)  # Default to 100 if limit is None
        self._skip = skip
        self._limit = limit
        return self

    def with_sorting(
        self, sort_by: Optional[str] = None, sort_order: str = "asc"
    ) -> "QueryBuilder":
        """Add sorting parameters"""
        if sort_by:
            validate_sort_field(self.model, sort_by)
        validate_sort_order(sort_order)
        self._sort_by = sort_by
        self._sort_order = sort_order.lower()
        return self

    def with_custom_filter(self, filter_func: Callable[[Query], Query]) -> "QueryBuilder":
        """Apply a custom filter function"""
        self.query = filter_func(self.query)
        return self

    def _apply_sorting(self):
        """Apply sorting if configured"""
        if self._sort_by:
            order_column = getattr(self.model, self._sort_by)
            if self._sort_order == "desc":
                self.query = self.query.order_by(desc(order_column))
            else:
                self.query = self.query.order_by(order_column)

    def _apply_pagination(self):
        """Apply pagination if configured"""
        if self._skip:
            self.query = self.query.offset(self._skip)
        if self._limit:
            self.query = self.query.limit(self._limit)

    def build(self) -> Query:
        """Return the final query"""
        self._apply_sorting()
        self._apply_pagination()
        return self.query

    def count(self) -> int:
        """Execute query and return the count of results without pagination"""
        # Create a count query without pagination or sorting
        return self.query.count()

    def first(self) -> Optional[T]:
        """Execute query and return first result"""
        return self.build().first()

    def all(self) -> List[T]:
        """Execute query and return all results"""
        return self.build().all()

    def filter_by_id(self, id: UUID) -> Optional[T]:
        """Filter by ID and return first result"""
        return self.query.filter(self.model.id == id).first()


def has_organization_id(model: Type[T]) -> bool:
    """Check if model has organization_id column"""
    return hasattr(model, "organization_id") or "organization_id" in inspect(model).columns.keys()


def has_visibility(model: Type[T]) -> bool:
    """Check if model supports visibility filtering (has visibility, organization_id and user_id
    fields)"""
    columns = inspect(model).columns.keys()
    return "visibility" in columns and "organization_id" in columns and "user_id" in columns


def get_model_relationships(
    model: Type, skip_many_to_many: bool = True, skip_one_to_many: bool = True
) -> Dict[str, RelationshipProperty]:
    """
    Get relationships from a SQLAlchemy model.

    Args:
        model: The SQLAlchemy model class
        skip_many_to_many: If True, excludes many-to-many relationships
                          (those with secondary tables)
        skip_one_to_many: If True, excludes one-to-many relationships (those with uselist=True)

    Returns:
        Dictionary of relationship name to RelationshipProperty
    """
    mapper = inspect(model)
    relationships = {}

    for rel in mapper.relationships:
        # Use hierarchical filtering to avoid overlap between many-to-many and one-to-many

        # First, check if it's many-to-many (has secondary table)
        if getattr(rel, "secondary", None) is not None:
            # This is a many-to-many relationship
            if skip_many_to_many:
                continue
        # Then, check if it's one-to-many (uselist=True but no secondary table)
        elif rel.uselist:
            # This is a pure one-to-many relationship
            if skip_one_to_many:
                continue
        # Otherwise, it's many-to-one or one-to-one (uselist=False, no secondary)

        # Include this relationship
        relationships[rel.key] = rel

    return relationships


def apply_joinedloads(
    query: Query, model: Type, skip_many_to_many: bool = True, skip_one_to_many: bool = False
) -> Query:
    """
    Apply joinedload options to a query based on model relationships.

    Args:
        query: The SQLAlchemy query to modify
        model: The SQLAlchemy model class
        skip_many_to_many: If True, excludes many-to-many relationships
        skip_one_to_many: If True, excludes one-to-many relationships

    Returns:
        Modified query with joinedload options applied
    """
    relationships = get_model_relationships(
        model, skip_many_to_many=skip_many_to_many, skip_one_to_many=skip_one_to_many
    )

    for rel_name, _ in relationships.items():
        relationship_attr = getattr(model, rel_name)
        query = query.options(joinedload(relationship_attr))

    return query


def apply_optimized_loads(
    query: Query,
    model: Type,
    skip_many_to_many: bool = True,
    skip_one_to_many: bool = False,
    nested_relationships: dict = None,
) -> Query:
    """
    Apply optimized loading strategy using selectinload for many-to-many relationships
    and joinedload for one-to-many/many-to-one relationships.

    This avoids the cartesian product problem that occurs with joinedload on many-to-many.

    Args:
        nested_relationships: Dict specifying nested relationships to load.
                            Format: {"relationship_name": ["nested_rel1", "nested_rel2"]}
    """
    relationships = get_model_relationships(
        model, skip_many_to_many=False, skip_one_to_many=skip_one_to_many
    )

    for rel_name, rel_prop in relationships.items():
        relationship_attr = getattr(model, rel_name)

        # Use selectinload for many-to-many relationships to avoid cartesian products
        if rel_prop.direction.name in ["MANYTOMANY"]:
            if not skip_many_to_many:
                if nested_relationships and rel_name in nested_relationships:
                    # Load the main relationship with selectinload
                    query = query.options(selectinload(relationship_attr))
                    # Load each nested relationship separately
                    for nested_rel in nested_relationships[rel_name]:
                        nested_attr = getattr(rel_prop.mapper.class_, nested_rel)
                        query = query.options(
                            selectinload(relationship_attr).selectinload(nested_attr)
                        )
                else:
                    query = query.options(selectinload(relationship_attr))
        # Use joinedload for one-to-many and many-to-one relationships
        else:
            query = query.options(joinedload(relationship_attr))

    return query


# Removed apply_organization_filter and apply_visibility_filter functions
# These functions relied on session variables and have been replaced with direct parameter passing
# Use QueryBuilder.with_organization_filter(organization_id) and with_visibility_filter(user_id, organization_id) instead
