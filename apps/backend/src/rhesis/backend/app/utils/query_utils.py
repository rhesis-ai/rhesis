import logging
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

        include(Test.behavior, cols=[Behavior.id, Behavior.name])
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
        module level) -- e.g. ``include(Test.behavior, cols=[Behavior.id,
        Behavior.name])`` or a multi-hop chain: ``include(Test.test_configuration,
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
        """Selectin-load comments/tasks/files/tags for this model, and for any
        many-to-one/one-to-one relationship whose target model also has them.

        Detail response schemas nest a related model's own derived fields
        too (e.g. Test.prompt -> the nested PromptReference schema also gets
        a "counts"/"tags" field, since Prompt has the same mixins), so those
        need eager-loading as well -- not just this model's own. This is what
        makes Test.prompt (near-1:1 with Test, so effectively N distinct
        prompts per page) safe: without this, each row's prompt lazy-loads
        its own comments/tasks/tags individually.

        Checks the actual mixin class, not just attribute presence -- some
        models (e.g. User.comments, "comments authored by this user") have an
        unrelated attribute with the same name as a mixin's, which a plain
        ``hasattr`` would wrongly match.

        Safe to call unconditionally -- skips models/relationships that don't
        have these mixins. Merges in any caller-supplied ``extra_chains`` too
        (each a flat ``[name, ...]`` path, e.g. ``["_tags_relationship", "tag"]``),
        deduped by full chain.
        """
        from rhesis.backend.app.models.mixins import (
            CommentsMixin,
            FilesMixin,
            TagsMixin,
            TasksMixin,
        )

        derived_field_chains = (
            (CommentsMixin, ("comments",)),
            (TasksMixin, ("tasks",)),
            (FilesMixin, ("files",)),
            (TagsMixin, ("_tags_relationship", "tag")),
        )

        chains = list(extra_chains or [])
        seen = {tuple(chain) for chain in chains}

        def _add(chain: list) -> None:
            key = tuple(chain)
            if key not in seen:
                seen.add(key)
                chains.append(list(chain))

        for mixin, chain in derived_field_chains:
            if issubclass(self.model, mixin):
                _add(list(chain))
        for chain in chains:
            # resolve_chain turns the runtime [name, ...] chain into a tuple of
            # real attributes; include() picks joinedload vs. selectinload per hop
            # from each one's own cardinality, whether the chain is a single hop
            # (comments/tasks/files/tags) or multi-hop (_tags_relationship -> tag)
            # -- no special-casing needed for either length.
            self.with_related(include(*resolve_chain(self.model, chain)))

        # Cascade one level into joined-in single-object relations (the ones
        # with_optimized_loads/with_related eager-load via joinedload) whose
        # target model also carries these mixins. These relationships are
        # already strategy=joinedload (by convention, whether set by this
        # call or by the caller) -- selectinload-ing the same attribute
        # independently raises a loader-strategy conflict, so the nested load
        # is chained off the existing joinedload instead of starting fresh.
        seen_nested = set()
        for rel_name, rel_prop in get_model_relationships(
            self.model, skip_many_to_many=True, skip_one_to_many=True
        ).items():
            target_model = rel_prop.mapper.class_
            for mixin, chain in derived_field_chains:
                key = (rel_name, *chain)
                if key in seen_nested or not issubclass(target_model, mixin):
                    continue
                seen_nested.add(key)
                load = joinedload(getattr(self.model, rel_name))
                nested_model = target_model
                for nested_name in chain:
                    load = load.selectinload(getattr(nested_model, nested_name))
                    nested_rel_prop = inspect(nested_model).relationships.get(nested_name)
                    if nested_rel_prop is not None:
                        nested_model = nested_rel_prop.mapper.class_
                self.query = self.query.options(load)
        return self

    def _maybe_warn_load_count(self) -> None:
        if self._eager_load_count >= _MAX_EAGER_LOADS_WARN:
            logger.warning(
                "QueryBuilder(%s) has accumulated %d eager loads; consider "
                "whether the response schema actually needs all of these.",
                self.model.__name__,
                self._eager_load_count,
            )

    def with_optimized_loads(
        self,
        skip_many_to_many: bool = True,
        skip_one_to_many: bool = True,
        nested_relationships: dict = None,
    ) -> "QueryBuilder":
        """Apply optimized loading strategy.

        Uses selectinload for many-to-many, joinedload for others."""
        self.query = apply_optimized_loads(
            self.query, self.model, skip_many_to_many, skip_one_to_many, nested_relationships
        )
        return self

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

    def with_organization_filter(self, organization_id: str = None) -> "QueryBuilder":
        """
        Filter query by organization_id for tenant isolation.

        Raises:
            ValueError: If organization_id is required but not provided
        """
        if has_organization_id(self.model):
            # Check if model is exempt from organization filtering
            exempt_models = ["User", "Organization", "Token"]
            if self.model.__name__ in exempt_models:
                # For exempt models, apply organization filter if provided, but don't require it
                if organization_id and (
                    isinstance(organization_id, str)
                    and organization_id.strip()
                    or not isinstance(organization_id, str)
                ):
                    self.query = self.query.filter(self.model.organization_id == organization_id)
            else:
                # For non-exempt models, organization_id is required
                if organization_id and (
                    isinstance(organization_id, str)
                    and organization_id.strip()
                    or not isinstance(organization_id, str)
                ):
                    # Use direct organization_id filtering (optimized)
                    self.query = self.query.filter(self.model.organization_id == organization_id)
                else:
                    # SECURITY: organization_id must be provided for models that have it
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

    def with_field_inclusion(self, include_fields: str) -> "QueryBuilder":
        """Apply field inclusion using SQLAlchemy undefer for deferred fields"""
        if not include_fields:
            return self

        # Parse comma-separated fields
        fields = [field.strip() for field in include_fields.split(",") if field.strip()]

        # Apply undefer for each field that exists on the model
        for field in fields:
            if hasattr(self.model, field):
                # Use SQLAlchemy's undefer to force load deferred fields
                from sqlalchemy.orm import undefer

                self.query = self.query.options(undefer(field))

        return self

    def _apply_sorting(self):
        """Apply sorting if configured"""
        from rhesis.backend.app.utils.count_sort import (
            apply_virtual_count_sort,
            is_virtual_count_sort,
        )

        if self._sort_by and is_virtual_count_sort(self._sort_by):
            self.query = apply_virtual_count_sort(
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


def has_visibility(model: Type[T]) -> bool:
    """Check if model supports visibility filtering.

    Requires a ``visibility`` column and an owner column (``user_id`` or
    ``owner_user_id``).
    """
    columns = inspect(model).columns.keys()
    has_owner = "user_id" in columns or "owner_user_id" in columns
    return "visibility" in columns and has_owner


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


def _build_nested_load_options(
    parent_load,
    parent_rel_prop: RelationshipProperty,
    nested_spec,
) -> List:
    """
    Recursively build chained load options for nested relationships.

    Args:
        parent_load: The parent load option (e.g. joinedload(Model.rel))
        parent_rel_prop: The SQLAlchemy RelationshipProperty for the parent
        nested_spec: Either a list of relationship names or a dict for deeper nesting.
                     List format:  ["endpoint", "test_set"]
                     Dict format:  {"endpoint": ["project"], "test_set": ["test_set_type"]}

    Returns:
        List of chained load options to apply to the query.
    """
    target_model = parent_rel_prop.mapper.class_
    options = []

    if isinstance(nested_spec, list):
        for nested_rel_name in nested_spec:
            if hasattr(target_model, nested_rel_name):
                nested_attr = getattr(target_model, nested_rel_name)
                options.append(parent_load.joinedload(nested_attr))
    elif isinstance(nested_spec, dict):
        for nested_rel_name, deeper_spec in nested_spec.items():
            if hasattr(target_model, nested_rel_name):
                nested_attr = getattr(target_model, nested_rel_name)
                nested_load = parent_load.joinedload(nested_attr)
                options.append(nested_load)
                nested_rel_prop = inspect(target_model).relationships[nested_rel_name]
                options.extend(
                    _build_nested_load_options(nested_load, nested_rel_prop, deeper_spec)
                )

    return options


def apply_optimized_loads(
    query: Query,
    model: Type,
    skip_many_to_many: bool = True,
    skip_one_to_many: bool = True,
    nested_relationships: dict = None,
) -> Query:
    """
    Apply optimized loading strategy using selectinload for many-to-many relationships
    and joinedload for one-to-many/many-to-one relationships.

    This avoids the cartesian product problem that occurs with joinedload on many-to-many.

    Args:
        nested_relationships: Dict specifying nested relationships to load.
            Supports both flat and deep nesting formats:
            - Flat:  {"tags": ["status"]}
            - Deep:  {"test_configuration": {"endpoint": ["project"],
                                             "test_set": ["test_set_type"]}}
    """
    relationships = get_model_relationships(
        model, skip_many_to_many=False, skip_one_to_many=skip_one_to_many
    )

    for rel_name, rel_prop in relationships.items():
        relationship_attr = getattr(model, rel_name)
        has_nested = nested_relationships and rel_name in nested_relationships

        if rel_prop.direction.name in ["MANYTOMANY"]:
            if not skip_many_to_many:
                if has_nested:
                    base_load = selectinload(relationship_attr)
                    query = query.options(base_load)
                    for nested_rel in nested_relationships[rel_name]:
                        nested_attr = getattr(rel_prop.mapper.class_, nested_rel)
                        query = query.options(base_load.selectinload(nested_attr))
                else:
                    query = query.options(selectinload(relationship_attr))
        else:
            base_load = joinedload(relationship_attr)
            query = query.options(base_load)
            if has_nested:
                for opt in _build_nested_load_options(
                    base_load, rel_prop, nested_relationships[rel_name]
                ):
                    query = query.options(opt)

    return query
