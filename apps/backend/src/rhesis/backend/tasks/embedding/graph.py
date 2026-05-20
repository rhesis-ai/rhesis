"""Celery tasks for computing embedding graphs (2D scatter + clusters)."""

import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from rhesis.backend.celery.core import app
from rhesis.backend.tasks.base import SilentTask

logger = logging.getLogger(__name__)

_GRAPH_KEY = "graph"
_PAGE_SIZE = 100


def _embedding_entity_type_key(model_or_name: type | str) -> str:
    return model_or_name if isinstance(model_or_name, str) else model_or_name.__name__


def _ensure_embeddings_for_entities(
    db,
    *,
    entity_ids: list[UUID],
    user,
    embedded_entity: type | str,
) -> None:
    """Generate and persist active embeddings for entities that do not have one yet."""
    if not entity_ids:
        return

    from rhesis.backend.app.services.embedding.generator import EmbeddingGenerator
    from rhesis.backend.app.services.embedding.graph_builder import fetch_embeddings
    from rhesis.backend.app.services.embedding.services import EmbeddingService

    entity_type = _embedding_entity_type_key(embedded_entity)
    org_id = str(user.organization_id)
    user_id = str(user.id)

    existing = fetch_embeddings(
        db,
        entity_ids,
        embedded_entity=embedded_entity,
        organization_id=org_id,
        user_id=user_id,
    )
    covered = {e.entity_id for e in existing}
    missing_ids = [entity_id for entity_id in entity_ids if entity_id not in covered]
    if not missing_ids:
        logger.info(
            "Embedding backfill: all %s %s entities already have active embeddings",
            len(entity_ids),
            entity_type,
        )
        return

    try:
        model_id = EmbeddingService(db)._resolve_model_id(user_id)
    except ValueError as exc:
        logger.warning(
            "Embedding backfill skipped for %s entities: no embedding model (%s)",
            len(missing_ids),
            exc,
        )
        return

    generator = EmbeddingGenerator(db)
    generated = 0
    skipped_empty = 0
    failed = 0
    for entity_id in missing_ids:
        try:
            result = generator.generate(
                entity_id=str(entity_id),
                entity_type=entity_type,
                organization_id=org_id,
                user_id=user_id,
                model_id=model_id,
            )
        except Exception as exc:
            failed += 1
            logger.warning(
                "Embedding backfill failed for %s:%s: %s",
                entity_type,
                entity_id,
                exc,
                exc_info=True,
            )
            continue

        status = result.get("status")
        if status == "success":
            generated += 1
        elif status == "skipped_empty_text":
            skipped_empty += 1
        else:
            failed += 1

    logger.info(
        "Embedding backfill for %s: missing=%s generated=%s skipped_empty=%s failed=%s",
        entity_type,
        len(missing_ids),
        generated,
        skipped_empty,
        failed,
    )


def _collect_test_set_entity_ids(db, test_set_id: UUID) -> list[UUID]:
    """Return visible test IDs for a test set (excludes soft-deleted tests)."""
    from rhesis.backend.app import crud

    entity_ids: list[UUID] = []
    skip = 0
    while True:
        items, _count = crud.get_test_set_tests(
            db=db,
            test_set_id=test_set_id,
            skip=skip,
            limit=_PAGE_SIZE,
            sort_by="created_at",
            sort_order="desc",
        )
        entity_ids.extend(test.id for test in items)
        if len(items) < _PAGE_SIZE:
            break
        skip += _PAGE_SIZE
    return entity_ids


def _collect_source_chunk_entity_ids(db, source_id: UUID, organization_id: str) -> list[UUID]:
    """Paginate non-deleted chunk IDs for a source in ``chunk_index`` order."""
    from rhesis.backend.app import models
    from rhesis.backend.app.utils.query_utils import QueryBuilder

    entity_ids: list[UUID] = []
    skip = 0
    while True:
        chunks = (
            QueryBuilder(db, models.Chunk)
            .with_organization_filter(organization_id)
            .with_visibility_filter()
            .with_custom_filter(lambda q: q.filter(models.Chunk.source_id == source_id))
            .with_sorting(sort_by="chunk_index", sort_order="asc")
            .with_pagination(skip=skip, limit=_PAGE_SIZE)
            .all()
        )
        entity_ids.extend(c.id for c in chunks)
        if len(chunks) < _PAGE_SIZE:
            break
        skip += _PAGE_SIZE
    return entity_ids


def _run_embedding_graph(
    db,
    *,
    user_id: str,
    resolve_entity_ids: Callable[[Any, Any, Any], list[UUID]],
    embedded_entity: type,
    load_parent: Callable[[Any, Any], Any | None],
    persist_graph: Callable[[Any, Any], None],
    parent_name: str,
) -> None:
    from rhesis.backend.app import crud
    from rhesis.backend.app.services.embedding.graph_builder import build_2d_graph

    user = crud.get_user_by_id(db, user_id)
    if user is None:
        logger.warning("Skipping graph computation: user not found", extra={"user_id": user_id})
        return

    parent = load_parent(db, user)
    if parent is None:
        logger.warning(f"Skipping graph computation: {parent_name} not found")
        return

    entity_ids = resolve_entity_ids(db, user, parent)
    _ensure_embeddings_for_entities(
        db,
        entity_ids=entity_ids,
        user=user,
        embedded_entity=embedded_entity,
    )
    graph = build_2d_graph(db, entity_ids, user, embedded_entity=embedded_entity)
    persist_graph(parent, graph)
    db.add(parent)
    db.commit()


def _run_test_set_embedding_graph(db, *, test_set_id: str, user_id: str) -> None:
    from rhesis.backend.app import crud, models

    test_set_uuid = UUID(test_set_id)

    def load_parent(db_session, user):
        return crud.get_test_set(
            db_session,
            test_set_uuid,
            str(user.organization_id),
            str(user.id),
        )

    def resolve_entity_ids(db_session, _user, _test_set):
        return _collect_test_set_entity_ids(db_session, test_set_uuid)

    def persist_graph(test_set, graph):
        attrs = dict(test_set.attributes or {})
        attrs[_GRAPH_KEY] = graph.model_dump(mode="json")
        test_set.attributes = attrs

    _run_embedding_graph(
        db,
        user_id=user_id,
        resolve_entity_ids=resolve_entity_ids,
        embedded_entity=models.Test,
        load_parent=load_parent,
        persist_graph=persist_graph,
        parent_name="test set",
    )


def _run_source_embedding_graph(db, *, source_id: str, user_id: str) -> None:
    from rhesis.backend.app import crud, models

    source_uuid = UUID(source_id)

    def load_parent(db_session, user):
        return crud.get_source(
            db_session,
            source_uuid,
            str(user.organization_id),
            str(user.id),
        )

    def resolve_entity_ids(db_session, user, _db_source):
        return _collect_source_chunk_entity_ids(db_session, source_uuid, str(user.organization_id))

    def persist_graph(db_source, graph):
        meta = dict(db_source.source_metadata or {})
        meta[_GRAPH_KEY] = graph.model_dump(mode="json")
        db_source.source_metadata = meta

    _run_embedding_graph(
        db,
        user_id=user_id,
        resolve_entity_ids=resolve_entity_ids,
        embedded_entity=models.Chunk,
        load_parent=load_parent,
        persist_graph=persist_graph,
        parent_name="source",
    )


@app.task(
    base=SilentTask,
    name="rhesis.backend.tasks.embedding.compute_graph_test_set",
    bind=True,
    display_name="Embedding Graph Computation (test set)",
)
def compute_test_set_graph_task(self, test_set_id: str, user_id: str):
    """Compute embedding graph for a test set and store on ``attributes`` JSON."""
    with self.get_db_session() as db:
        _run_test_set_embedding_graph(db, test_set_id=test_set_id, user_id=user_id)


@app.task(
    base=SilentTask,
    name="rhesis.backend.tasks.embedding.compute_graph_source",
    bind=True,
    display_name="Embedding Graph Computation (source chunks)",
)
def compute_source_graph_task(self, source_id: str, user_id: str):
    """Compute embedding graph for a source and store under ``source_metadata`` JSON."""
    with self.get_db_session() as db:
        _run_source_embedding_graph(db, source_id=source_id, user_id=user_id)
