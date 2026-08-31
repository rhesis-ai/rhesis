import logging
from typing import Callable, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import desc, inspect, or_
from sqlalchemy.orm import Query, Session, joinedload, selectinload

# Removed unused imports - legacy tenant functions no longer needed
from rhesis.backend.app.utils.odata import apply_odata_filter
from rhesis.backend.app.utils.query_validation import (
    validate_odata_filter,
    validate_pagination,
    validate_sort_field,
    validate_sort_order,
)

logger = logging.getLogger(__name__)

# Define a generic type variable
T = TypeVar("T")

# Warn when a single query eager-loads more relationships than this. The
# Test/test-set blow-up that necessitated this guard was caused by a 22-join
# SQL statement; anything close to that warrants a second look.
_MAX_EAGER_LOADS_WARN = 12


def resolve_chain(model: Type, names: list) -> tuple:
    """Resolve a runtime ``[name, ...]`` relationship-name chain into a tuple of
    real attributes, one per hop, starting from ``model``.

    Used where relationship names are only known dynamically per-model (e.g.
    ``with_default_derived_field_loads``, which runs across every model), so a
    static ``Model.attr`` reference isn't available at the call site.
    """
    attrs = []
    current_model = model
    for name in names:
        attrs.append(getattr(current_model, name))
        rel_prop = inspect(current_model).relationships.get(name)
        if rel_prop is not None:
            current_model = rel_prop.mapper.class_
    return tuple(attrs)


def include(*path, cols: list | None = None):
    """Build one eager-load option for ``QueryBuilder.with_related``.

    ``path`` is one or more relationship attributes forming a chain (e.g.
    ``Test.test_configuration, TestConfiguration.endpoint``). ``joinedload`` vs.
    ``selectinload`` is picked per hop from that relationship's own cardinality,
    so a collection relationship can never regress into the cartesian-product
    blowup a plain JOIN would produce (see ``_MAX_EAGER_LOADS_WARN`` below).
    ``cols`` scopes the final hop to specific columns -- omit it (leave as
    ``None``) to load the full related row. ``cols=[]`` is rejected outright
    rather than silently treated as "no scoping", since that's the opposite
    of what an empty list reads as.

    Example::

        include(Test.requirement, cols=[Requirement.id, Requirement.name])
        include(Test.test_configuration, TestConfiguration.endpoint,
                cols=[Endpoint.id, Endpoint.name])
    """
    if cols is not None and not cols:
        raise ValueError(
            "include(): cols=[] is not allowed -- omit cols to load the full "
            "row, or pass at least one column"
        )
    opt = selectinload(path[0]) if path[0].property.uselist else joinedload(path[0])
    for attr in path[1:]:
        opt = opt.selectinload(attr) if attr.property.uselist else opt.joinedload(attr)
    if cols is not None:
        opt = opt.load_only(*cols)
    return opt


class QueryBuilder:
    """
    A flexible query builder that allows selective application of filters and transformations.
    """

    def __init__(self, db: Session, model: Type[T]):
        self.db = db
        self.model = model
        self._include_deleted = False
        self._only_deleted = False

        # Always create a fresh query to avoid leaking state between requests
        try:
            self.query = db.query(model)
            # Signal to event listener about soft delete filtering preference
            self.query._include_soft_deleted = False
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
        self._secondary_sort_by = None
        self._secondary_sort_order = "asc"
        # Track eager-load count so we can warn callers who request an
        # unreasonably large number of relationships on a single query. Not
        # split by strategy (joined vs. selectin) -- that decision happens
        # inside include() now, invisibly to with_related, so a joined/
        # selectin breakdown here would just be made up.
        self._eager_load_count = 0

    def with_related(self, *options) -> "QueryBuilder":
        """Eager-load each relationship option, built via ``include(...)`` (see
        module level) -- e.g. ``include(Test.requirement, cols=[Requirement.id,
        Requirement.name])`` or a multi-hop chain: ``include(Test.test_configuration,
        TestConfiguration.endpoint, cols=[Endpoint.id, Endpoint.name])``.

        A pass-through onto the query's own ``.options()`` -- all of the
        strategy-picking and column-scoping happens in ``include()`` itself.
        """
        if options:
            self.query = self.query.options(*options)
            # Approximate: counts top-level options, not each hop of a multi-hop
            # chain, which is enough to catch the "far too many relationships in
            # one query" pattern that caused the 22-join blowup this guards
            # against -- see _MAX_EAGER_LOADS_WARN above.
            self._eager_load_count += len(options)
            self._maybe_warn_load_count()
        return self

    def with_default_derived_field_loads(self, extra_chains: list | None = None) -> "QueryBuilder":
        """Eager-load comments/tasks/files/tags for this model (and one level of
        cascade into related models that carry the same mixins) -- see
        ``derived_field_loads.derived_field_load_options`` for the policy.
        """
        from rhesis.backend.app.utils.derived_field_loads import derived_field_load_options

        return self.with_related(*derived_field_load_options(self.model, extra_chains))

    def _maybe_warn_load_count(self) -> None:
        if self._eager_load_count >= _MAX_EAGER_LOADS_WARN:
            logger.warning(
                "QueryBuilder(%s) has accumulated %d eager loads; consider "
                "whether the response schema actually needs all of these.",
                self.model.__name__,
                self._eager_load_count,
            )

    def with_deleted(self) -> "QueryBuilder":
        """
        Include soft-deleted records in the query results.

        This disables the automatic soft delete filter for this query,
        allowing both active and deleted records to be returned.

        Usage:
            QueryBuilder(db, User).with_deleted().all()

        Returns:
            Self for method chaining
        """
        self._include_deleted = True
        # Signal to event listener to NOT filter this query
        self.query._include_soft_deleted = True
        return self

    def only_deleted(self) -> "QueryBuilder":
        """
        Only return soft-deleted records.

        This explicitly filters for records where deleted_at IS NOT NULL,
        showing only items in the recycle bin.

        Usage:
            QueryBuilder(db, User).only_deleted().all()

        Returns:
            Self for method chaining
        """
        self._only_deleted = True
        # Signal to event listener to NOT filter this query
        self.query._include_soft_deleted = True

        # Apply filter to only show deleted records
        if hasattr(self.model, "deleted_at"):
            self.query = self.query.filter(self.model.deleted_at.isnot(None))
        return self

    def with_organization_filter(self, organization_id: str | None = None) -> "QueryBuilder":
        """
        Filter query by organization_id for tenant isolation.

        Raises:
            ValueError: If organization_id is required but not provided
        """
        if not has_organization_id(self.model):
            return self

        provided = organization_id and (
            not isinstance(organization_id, str) or organization_id.strip()
        )
        if provided:
            self.query = self.query.filter(self.model.organization_id == organization_id)
        elif self.model.__name__ not in ("User", "Organization", "Token"):
            # SECURITY: organization_id must be provided for non-exempt models
            # that have it, to prevent data leakage across organizations.
            raise ValueError(
                f"organization_id is required for {self.model.__name__} "
                "but was not provided. This is a security requirement to "
                "prevent data leakage across organizations."
            )
        return self

    def with_project_filter(self, project_id: Optional[str] = None) -> "QueryBuilder":
        """
        Filter query by project_id, allowing NULL rows to pass through.

        When ``project_id`` is provided the filter applied is::

            model.project_id = :pid OR model.project_id IS NULL

        NULL rows represent org-wide entities created before project containers
        were introduced.  They are intentionally visible inside every project's
        view.  Pass ``project_id=None`` (or omit the argument) to skip the
        filter entirely.

        The ambient auto-filter listener in ``scope_events.py`` applies the
        same predicate automatically for most request paths.  Use this method
        only when you need an explicit, call-site-visible project filter —
        e.g. in admin paths that operate outside the normal request scope.
        """
        if project_id and has_project_id(self.model):
            self.query = self.query.filter(
                or_(
                    self.model.project_id == project_id,
                    self.model.project_id.is_(None),
                )
            )
        return self

    def with_visibility_filter(self, user_id: Optional[str] = None) -> "QueryBuilder":
        """Hide owner-only rows from non-owners.

        Models that declare a ``visibility`` column alongside an owner column
        (``user_id`` or ``owner_user_id``) are filtered so that rows whose
        visibility marks them as private (``'user'`` for TestSet,
        ``'private'`` for Experiment) are visible only to their owner.
        Models without these columns are returned unfiltered.

        Owner column priority: ``user_id`` > ``owner_user_id``.  Some
        models (e.g. TestSet) also carry an ``owner_id`` column, but
        ``user_id`` is the canonical field used by capability / ``:own``
        checks and creation paths.  ``owner_id`` is intentionally
        ignored here to stay aligned with the auth layer.
        """
        columns = inspect(self.model).columns.keys()
        if "visibility" not in columns:
            return self

        # owner_id is intentionally not checked — see docstring.
        if "user_id" in columns:
            owner_col = self.model.user_id
        elif "owner_user_id" in columns:
            owner_col = self.model.owner_user_id
        else:
            return self

        private_values = ("user", "private")

        vis = self.model.visibility
        if user_id:
            self.query = self.query.filter(
                or_(
                    vis.is_(None),
                    ~vis.in_(private_values),
                    owner_col == user_id,
                )
            )
        else:
            self.query = self.query.filter(or_(vis.is_(None), ~vis.in_(private_values)))

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
        self,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        secondary_sort_by: Optional[str] = None,
        secondary_sort_order: str = "asc",
    ) -> "QueryBuilder":
        """Add sorting parameters.

        Args:
            sort_by: Primary sort field name.
            sort_order: Primary sort direction ('asc' or 'desc').
            secondary_sort_by: Optional tiebreaker field applied after the
                primary sort. Useful when many rows share the same primary
                value (e.g. identical timestamps).
            secondary_sort_order: Direction for the secondary sort ('asc' or
                'desc'). Defaults to 'asc'.
        """
        if sort_by:
            validate_sort_field(self.model, sort_by)
        validate_sort_order(sort_order)
        if secondary_sort_by:
            validate_sort_field(self.model, secondary_sort_by)
            validate_sort_order(secondary_sort_order)
        self._sort_by = sort_by
        self._sort_order = sort_order.lower()
        self._secondary_sort_by = secondary_sort_by
        self._secondary_sort_order = secondary_sort_order.lower()
        return self

    def with_custom_filter(self, filter_func: Callable[[Query], Query]) -> "QueryBuilder":
        """Apply a custom filter function"""
        self.query = filter_func(self.query)
        return self

    def _apply_sorting(self):
        """Apply sorting if configured"""
        from rhesis.backend.app.utils.count_sort import (
            apply_virtual_count_sort,
            is_virtual_count_sort,
        )
        from rhesis.backend.app.utils.relationship_sort import (
            apply_virtual_relationship_sort,
            is_virtual_relationship_sort,
        )

        if self._sort_by and is_virtual_count_sort(self._sort_by):
            self.query = apply_virtual_count_sort(
                self.query,
                self.model,
                self._sort_by,
                self._sort_order,
            )
        elif self._sort_by and is_virtual_relationship_sort(self._sort_by):
            self.query = apply_virtual_relationship_sort(
                self.query,
                self.model,
                self._sort_by,
                self._sort_order,
            )
        elif self._sort_by:
            order_column = getattr(self.model, self._sort_by)
            if self._sort_order == "desc":
                self.query = self.query.order_by(desc(order_column))
            else:
                self.query = self.query.order_by(order_column)
        if self._secondary_sort_by:
            secondary_column = getattr(self.model, self._secondary_sort_by)
            if self._secondary_sort_order == "desc":
                self.query = self.query.order_by(desc(secondary_column))
            else:
                self.query = self.query.order_by(secondary_column)
        # Always append id ASC as a final unique tiebreaker so results are
        # strictly deterministic even when all other sort keys are equal.
        if self._sort_by and hasattr(self.model, "id"):
            self.query = self.query.order_by(self.model.id)

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
        # Apply soft delete filtering before adding ID filter
        if not self._include_deleted and not self._only_deleted:
            # Add soft delete filter if not already including deleted records
            if hasattr(self.model, "deleted_at"):
                self.query = self.query.filter(self.model.deleted_at.is_(None))

        return self.query.filter(self.model.id == id).first()

    def ids(self) -> List:
        """Execute the built query, returning only matching IDs, in sort order.

        First phase of a two-query pagination split: filter/sort/paginate on a
        query with no eager-load joins, so Postgres only has to materialize
        and sort the bare id column before applying LIMIT/OFFSET -- not every
        joined column of every matching row. Pair with a second query that
        eager-loads relationships scoped to ``model.id.in_(these_ids)``.
        """
        return [row[0] for row in self.build().with_entities(self.model.id).all()]


def has_organization_id(model: Type[T]) -> bool:
    """Check if model has organization_id column"""
    return hasattr(model, "organization_id") or "organization_id" in inspect(model).columns.keys()


def has_project_id(model: Type[T]) -> bool:
    """Check if model has project_id column."""
    return hasattr(model, "project_id") or "project_id" in inspect(model).columns.keys()
