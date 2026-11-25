from typing import Collection, Dict, Type

from sqlalchemy import inspect
from sqlalchemy.orm import RelationshipProperty, joinedload

from rhesis.backend.app.utils.query_utils import include, resolve_chain


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


def derived_field_load_options(
    model: Type, extra_chains: list | None = None, cascade: Collection[str] | None = None
) -> list:
    """Build eager-load options for comments/tasks/files/tags on ``model``, and
    for any many-to-one/one-to-one relationship whose target model also has them.

    A ``CountsMixin`` model only reads comments/tasks/files to count them, so for
    those the full-row loads are replaced by one ``BatchCounts`` option, which
    counts every loaded row and its loaded relations in grouped queries (see
    ``models/entity_counts.py``). Tags still load as rows.

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

    ``cascade`` limits only the cascade into related models, to the named
    relationships, for a response schema that nests only some of them; ``None``
    cascades into all of them. The model's own derived fields always load, so
    ``cascade=()`` means "this model's fields only", not "no derived loads".
    """
    from rhesis.backend.app.models.entity_counts import batch_counts
    from rhesis.backend.app.models.mixins import (
        CommentsMixin,
        CountsMixin,
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

    def _needed(target_model, mixin) -> bool:
        if not issubclass(target_model, mixin):
            return False
        # Counted by BatchCounts instead; a model without CountsMixin (Trace) still
        # serializes the rows themselves.
        return mixin is TagsMixin or not issubclass(target_model, CountsMixin)

    for mixin, chain in derived_field_chains:
        if _needed(model, mixin):
            _add(list(chain))

    # resolve_chain turns the runtime [name, ...] chain into a tuple of real
    # attributes; include() picks joinedload vs. selectinload per hop from
    # each one's own cardinality, whether the chain is a single hop
    # (comments/tasks/files/tags) or multi-hop (_tags_relationship -> tag) --
    # no special-casing needed for either length.
    options = [include(*resolve_chain(model, chain)) for chain in chains]

    # Cascade one level into joined-in single-object relations (the ones
    # with_related eager-loads via joinedload) whose target model also
    # carries these mixins. These relationships are already
    # strategy=joinedload (by convention, whether set by this call or by the
    # caller) -- selectinload-ing the same attribute independently raises a
    # loader-strategy conflict, so the nested load is chained off the
    # existing joinedload instead of starting fresh.
    seen_nested = set()
    for rel_name, rel_prop in get_model_relationships(
        model, skip_many_to_many=True, skip_one_to_many=True
    ).items():
        if cascade is not None and rel_name not in cascade:
            continue
        target_model = rel_prop.mapper.class_
        emitted = False
        for mixin, chain in derived_field_chains:
            key = (rel_name, *chain)
            if key in seen_nested or not _needed(target_model, mixin):
                continue
            seen_nested.add(key)
            emitted = True
            load = joinedload(getattr(model, rel_name))
            nested_model = target_model
            for nested_name in chain:
                load = load.selectinload(getattr(nested_model, nested_name))
                nested_rel_prop = inspect(nested_model).relationships.get(nested_name)
                if nested_rel_prop is not None:
                    nested_model = nested_rel_prop.mapper.class_
            options.append(load)
        if not emitted and issubclass(target_model, CountsMixin):
            # Still join it in, so BatchCounts finds it loaded (Category has no tags).
            options.append(joinedload(getattr(model, rel_name)))

    # One option covers this model and every loaded relation, whatever the cascade.
    options.append(batch_counts())
    return options
