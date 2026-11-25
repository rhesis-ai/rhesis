"""Batched comment/task/file counts for ``CountsMixin`` rows.

``CountsMixin.counts`` used to be ``len(self.comments)`` and friends, so a page of
50 rows loaded every comment, task and file row of those 50 entities just to count
them. A query carrying the ``BatchCounts`` option instead runs one grouped COUNT per
related table (comment, task, file) over every ``CountsMixin`` object it loaded, and
stores the numbers on each object for ``CountsMixin`` to read.

Covered objects are the query's own rows plus what is already loaded on them, up to
``_MAX_DEPTH`` relationship hops (e.g. ``TestResult.test.prompt``), so nested
reference schemas that also serialize ``counts`` need no load of their own. An
object without stored counts (built elsewhere, or expired since) falls back to
counting its relationship as before.
"""

from collections import defaultdict
from itertools import chain
from typing import Iterable, Iterator

from sqlalchemy import and_, any_, bindparam, event, func, inspect, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Session
from sqlalchemy.orm.interfaces import UserDefinedOption

from rhesis.backend.app.models.comment import Comment
from rhesis.backend.app.models.file import File
from rhesis.backend.app.models.mixins import (
    BATCHED_COUNTS_KEY,
    CommentsMixin,
    CountsMixin,
    FilesMixin,
    TasksMixin,
)
from rhesis.backend.app.models.task import Task

# TestResult -> test -> prompt is the deepest nesting a response schema reads counts at.
_MAX_DEPTH = 2

# The counted relationships themselves, and tags, never lead to another counted row.
_SKIP_RELATIONSHIPS = frozenset({"comments", "tasks", "files", "_tags_relationship"})

_listeners_registered = False


class BatchCounts(UserDefinedOption):
    """Query option: attach batched counts to the loaded ``CountsMixin`` rows."""


def batch_counts() -> BatchCounts:
    return BatchCounts()


# Same keys, order and presence rules as CountsMixin.counts.
_COUNTED_RELATIONS = (
    ("comments", CommentsMixin, Comment),
    ("tasks", TasksMixin, Task),
    ("files", FilesMixin, File),
)


def _loaded_related(obj) -> Iterator:
    """Objects already loaded on ``obj``'s relationships; never triggers a load."""
    state = inspect(obj, raiseerr=False)
    if state is None:
        return
    for rel in state.mapper.relationships:
        if rel.key in _SKIP_RELATIONSHIPS:
            continue
        value = state.dict.get(rel.key)
        if value is None:
            continue
        if rel.uselist:
            yield from value
        else:
            yield value


def _collect(roots: Iterable) -> list:
    seen: dict[int, object] = {}
    frontier = list(roots)
    for depth in range(_MAX_DEPTH + 1):
        next_frontier = []
        for obj in frontier:
            if id(obj) in seen:
                continue
            seen[id(obj)] = obj
            if depth < _MAX_DEPTH:
                next_frontier.extend(_loaded_related(obj))
        frontier = next_frontier
    return [obj for obj in seen.values() if isinstance(obj, CountsMixin) and obj.id is not None]


def _grouped_counts(session: Session, related_model, ids_by_type: dict) -> dict:
    """``{(entity_type, entity_id): count}`` for the given entities, one query.

    Selects model columns (not a bare ``func.count()``) so the tenant auto-filter
    still recognises ``related_model`` and adds its org/project criteria.
    """
    stmt = (
        select(related_model.entity_type, related_model.entity_id, func.count(related_model.id))
        .where(
            related_model.deleted_at.is_(None),
            or_(
                *(
                    and_(
                        related_model.entity_type == entity_type,
                        # One array bind, not one bind per id (Postgres caps binds at 65535).
                        related_model.entity_id
                        == any_(bindparam(None, list(ids), type_=ARRAY(UUID(as_uuid=True)))),
                    )
                    for entity_type, ids in ids_by_type.items()
                )
            ),
        )
        .group_by(related_model.entity_type, related_model.entity_id)
    )
    return {(entity_type, entity_id): n for entity_type, entity_id, n in session.execute(stmt)}


def attach_counts(session: Session, objects: Iterable) -> None:
    """Store comment/task/file counts on each ``CountsMixin`` object in ``objects``."""
    targets = [obj for obj in objects if isinstance(obj, CountsMixin) and obj.id is not None]
    if not targets:
        return

    found: dict[str, dict] = {}
    for key, mixin, related_model in _COUNTED_RELATIONS:
        ids_by_type = defaultdict(set)
        for obj in targets:
            if isinstance(obj, mixin):
                ids_by_type[type(obj).__name__].add(obj.id)
        if ids_by_type:
            found[key] = _grouped_counts(session, related_model, ids_by_type)

    for obj in targets:
        entity_type = type(obj).__name__
        obj.__dict__[BATCHED_COUNTS_KEY] = {
            key: found[key].get((entity_type, obj.id), 0)
            for key, mixin, _model in _COUNTED_RELATIONS
            if isinstance(obj, mixin)
        }


def _returns_one_entity(statement) -> bool:
    # A multi-column result with a joined collection must be unique()d by the caller
    # before it can be fetched, so freezing it here would raise.
    descriptions = statement.column_descriptions
    return len(descriptions) == 1 and descriptions[0]["expr"] is descriptions[0].get("entity")


def _wants_batch_counts(orm_execute_state) -> bool:
    if not orm_execute_state.is_select:
        return False
    if orm_execute_state.is_relationship_load or orm_execute_state.is_column_load:
        return False
    # Freezing the result would buffer a streamed query in full.
    if orm_execute_state.load_options._yield_per:
        return False
    if orm_execute_state.execution_options.get("yield_per"):
        return False
    if not any(isinstance(opt, BatchCounts) for opt in orm_execute_state.user_defined_options):
        return False
    return _returns_one_entity(orm_execute_state.statement)


def _on_execute(orm_execute_state):
    if not _wants_batch_counts(orm_execute_state):
        return None
    frozen = orm_execute_state.invoke_statement().freeze()
    roots = [value for row in frozen() for value in row if hasattr(value, "_sa_instance_state")]
    attach_counts(orm_execute_state.session, _collect(roots))
    return frozen()


def _drop_batched_counts(state, *_args) -> None:
    # Expired rows may have gained comments/tasks/files; count them afresh. raw=True
    # gives the state, since the object itself may already be garbage-collected.
    state.dict.pop(BATCHED_COUNTS_KEY, None)


_COUNTED_MODELS = tuple(model for _key, _mixin, model in _COUNTED_RELATIONS)


def _drop_counts_after_flush(session: Session, _flush_context) -> None:
    # A comment/task/file written in this session changes its entity's count.
    touched = {
        (obj.entity_type, obj.entity_id)
        for obj in chain(session.new, session.dirty, session.deleted)
        if isinstance(obj, _COUNTED_MODELS)
    }
    if not touched:
        return
    for state in session.identity_map.all_states():
        if state.identity and (state.class_.__name__, state.identity[0]) in touched:
            state.dict.pop(BATCHED_COUNTS_KEY, None)


def setup_entity_counts_listeners() -> None:
    """Register the listeners. Called once from ``models/__init__.py``."""
    global _listeners_registered
    if _listeners_registered:
        return
    event.listen(Session, "do_orm_execute", _on_execute)
    event.listen(CountsMixin, "expire", _drop_batched_counts, propagate=True, raw=True)
    event.listen(Session, "after_flush", _drop_counts_after_flush)
    _listeners_registered = True
