from typing import Dict, Type

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


def derived_field_load_options(model: Type, extra_chains: list | None = None) -> list:
    """Build eager-load options for comments/tasks/files/tags on ``model``, and
    for any many-to-one/one-to-one relationship whose target model also has them.

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
        if issubclass(model, mixin):
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
        target_model = rel_prop.mapper.class_
        for mixin, chain in derived_field_chains:
            key = (rel_name, *chain)
            if key in seen_nested or not issubclass(target_model, mixin):
                continue
            seen_nested.add(key)
            load = joinedload(getattr(model, rel_name))
            nested_model = target_model
            for nested_name in chain:
                load = load.selectinload(getattr(nested_model, nested_name))
                nested_rel_prop = inspect(nested_model).relationships.get(nested_name)
                if nested_rel_prop is not None:
                    nested_model = nested_rel_prop.mapper.class_
            options.append(load)

    return options
