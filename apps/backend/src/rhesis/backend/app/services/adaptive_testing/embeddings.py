"""Adaptive-testing scoped embedding helpers (SDK vectorization + embedding table)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Union
from uuid import UUID as UUIDType

import numpy as np
from sqlalchemy.orm import Session, joinedload

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.models.embedding import EmbeddingConfig
from rhesis.backend.app.models.enums import EmbeddingStatus, ModelType
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.user_model_utils import get_user_embedding_model
from rhesis.sdk.models.factory import get_model

logger = logging.getLogger(__name__)

# Adaptive testing persists to ``embedding`` columns (see EmbeddingConfig.SUPPORTED_DIMENSIONS).
# Force this output size so providers defaulting to large vectors (e.g. Gemini 3072) still store.
ADAPTIVE_TESTING_EMBEDDING_DIMENSION = 768


def sort_by_diversity(suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort suggestions by Euclidean distance from the centroid of their embeddings.

    Higher distance means more diverse (farther from the batch mean). Sets
    ``diversity_score`` on each item. Items without a usable embedding are placed
    last with ``diversity_score`` set to ``None``.
    """
    if not suggestions:
        return suggestions

    with_vectors: List[tuple[Dict[str, Any], List[float]]] = []
    without: List[Dict[str, Any]] = []

    for item in suggestions:
        emb = item.get("embedding")
        if emb is None or not isinstance(emb, list) or len(emb) == 0:
            item["diversity_score"] = None
            without.append(item)
            continue
        try:
            vec = [float(x) for x in emb]
        except (TypeError, ValueError):
            logger.warning(
                "Suggestion embedding not numeric; skipping diversity score",
                exc_info=False,
            )
            item["diversity_score"] = None
            without.append(item)
            continue
        with_vectors.append((item, vec))

    if not with_vectors:
        return suggestions

    dim = len(with_vectors[0][1])
    if any(len(v) != dim for _, v in with_vectors):
        logger.warning(
            "Inconsistent embedding dimensions in suggestions; skipping diversity sort"
        )
        for item, _ in with_vectors:
            item["diversity_score"] = None
        return suggestions

    matrix = np.asarray([v for _, v in with_vectors], dtype=np.float64)
    centroid = np.mean(matrix, axis=0)
    distances = np.linalg.norm(matrix - centroid, axis=1)

    order = np.argsort(-distances)
    sorted_with: List[Dict[str, Any]] = []
    for idx in order:
        item, _ = with_vectors[int(idx)]
        item["diversity_score"] = float(distances[int(idx)])
        sorted_with.append(item)

    return sorted_with + without


def _compute_hash(data: Union[str, dict]) -> str:
    if isinstance(data, dict):
        data_str = json.dumps(data, sort_keys=True)
    else:
        data_str = data
    return hashlib.sha256(data_str.encode("utf-8")).hexdigest()


def resolve_embedder(db: Session, user_id: str):
    """Resolve the embedding model for a user once.

    Returns a ready-to-use SDK ``BaseEmbedder`` instance configured with
    :data:`ADAPTIVE_TESTING_EMBEDDING_DIMENSION`.  Call this once and pass the
    result to :func:`generate_embedding_vector`, :func:`a_generate_embedding_vector`,
    or :func:`a_generate_embedding_vectors_batch` to avoid repeated DB lookups.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User not found: {user_id}")

    target_dim = ADAPTIVE_TESTING_EMBEDDING_DIMENSION
    resolved = get_user_embedding_model(db, user)
    if isinstance(resolved, str):
        return get_model(resolved, model_type="embedding", dimensions=target_dim)
    return resolved


def generate_embedding_vector(
    text: str,
    db: Session,
    user_id: str,
    *,
    embedder=None,
) -> List[float]:
    """Embed plain text using the user's configured embedding model or platform default.

    Always requests :data:`ADAPTIVE_TESTING_EMBEDDING_DIMENSION` (768) so vectors match
    supported ``embedding`` table columns regardless of provider defaults.

    Parameters
    ----------
    embedder : BaseEmbedder, optional
        Pre-resolved embedder from :func:`resolve_embedder`.  When provided the
        ``db`` / ``user_id`` lookup is skipped.
    """
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("Cannot embed empty text")

    if embedder is None:
        embedder = resolve_embedder(db, user_id)

    target_dim = ADAPTIVE_TESTING_EMBEDDING_DIMENSION
    vector = embedder.generate(text=stripped, dimensions=target_dim)
    out = list(vector)
    if len(out) != target_dim:
        logger.warning(
            "Adaptive embedding length %s != requested %s (provider may ignore dimensions); "
            "persistence may be skipped",
            len(out),
            target_dim,
        )
    return out


async def a_generate_embedding_vector(
    text: str,
    db: Session,
    user_id: str,
    *,
    embedder=None,
) -> List[float]:
    """Async embed plain text using the user's configured embedding model or platform default.

    Same behavior as :func:`generate_embedding_vector` but uses the embedder's async API.

    Parameters
    ----------
    embedder : BaseEmbedder, optional
        Pre-resolved embedder from :func:`resolve_embedder`.  When provided the
        ``db`` / ``user_id`` lookup is skipped.
    """
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("Cannot embed empty text")

    if embedder is None:
        embedder = resolve_embedder(db, user_id)

    target_dim = ADAPTIVE_TESTING_EMBEDDING_DIMENSION
    vector = await embedder.a_generate(text=stripped, dimensions=target_dim)
    out = list(vector)
    if len(out) != target_dim:
        logger.warning(
            "Adaptive embedding length %s != requested %s (provider may ignore dimensions); "
            "persistence may be skipped",
            len(out),
            target_dim,
        )
    return out


async def a_generate_embedding_vectors_batch(
    texts: List[str],
    db: Session,
    user_id: str,
    *,
    embedder=None,
    concurrency: int = 10,
) -> List[Optional[List[float]]]:
    """Embed multiple texts concurrently, resolving the embedder only once.

    Returns a list aligned with *texts*: each element is either the embedding
    vector or ``None`` when the text was empty or the call failed.

    Parameters
    ----------
    embedder : BaseEmbedder, optional
        Pre-resolved embedder from :func:`resolve_embedder`.
    concurrency : int
        Maximum number of parallel embedding API calls.
    """
    if embedder is None:
        embedder = resolve_embedder(db, user_id)

    target_dim = ADAPTIVE_TESTING_EMBEDDING_DIMENSION
    semaphore = asyncio.Semaphore(concurrency)

    async def _embed_one(text: str) -> Optional[List[float]]:
        stripped = (text or "").strip()
        if not stripped:
            return None
        async with semaphore:
            try:
                vector = await embedder.a_generate(text=stripped, dimensions=target_dim)
                out = list(vector)
                if len(out) != target_dim:
                    logger.warning(
                        "Adaptive embedding length %s != requested %s; "
                        "persistence may be skipped",
                        len(out),
                        target_dim,
                    )
                return out
            except Exception as e:
                logger.warning(
                    "Embedding failed (input preview %.80r): %s",
                    stripped,
                    e,
                    exc_info=True,
                )
                return None

    return list(
        await asyncio.gather(*[asyncio.create_task(_embed_one(t)) for t in texts])
    )


def load_test_for_embedding(db: Session, test_id: str, organization_id: str) -> Optional[Test]:
    """Load a Test with relationships required for ``to_searchable_text()``."""
    return (
        db.query(Test)
        .options(
            joinedload(Test.prompt),
            joinedload(Test.topic),
            joinedload(Test.behavior),
            joinedload(Test.category),
            joinedload(Test.test_type),
        )
        .filter(Test.id == test_id, Test.organization_id == organization_id)
        .first()
    )


def _organization_default_embedding_model(
    db: Session, organization_id: str
) -> Optional[models.Model]:
    """Fallback row for embedding.model_id when user settings omit embedding model_id."""
    org_uuid = UUIDType(organization_id)
    by_name = (
        db.query(models.Model)
        .filter(
            models.Model.organization_id == org_uuid,
            models.Model.name == "Rhesis Default Embedding",
            models.Model.model_type == ModelType.EMBEDDING.value,
        )
        .first()
    )
    if by_name:
        return by_name
    return (
        db.query(models.Model)
        .join(models.TypeLookup, models.Model.provider_type_id == models.TypeLookup.id)
        .filter(
            models.Model.organization_id == org_uuid,
            models.TypeLookup.type_value == "rhesis",
            models.Model.is_protected.is_(True),
            models.Model.model_type == ModelType.EMBEDDING.value,
        )
        .first()
    )


def create_test_embedding(
    db: Session,
    test: Test,
    vector: List[float],
    user: User,
) -> Optional[models.Embedding]:
    """
    Persist an embedding row for a Test.

    Uses the user's embedding model_id from settings when set; otherwise the org's
    default Rhesis embedding model row (same as onboarding/migrations). The stored
    dimension follows the actual vector length when it fits a supported ``embedding_*``
    column (384, 768, 1024, 1536), even if the model row's ``dimension`` field differs.
    """
    model_id_setting = None
    if user.settings and user.settings.models and user.settings.models.embedding:
        model_id_setting = user.settings.models.embedding.model_id

    organization_id = str(user.organization_id)
    user_id = str(user.id)

    if model_id_setting:
        model_id = str(model_id_setting)
    else:
        fallback = _organization_default_embedding_model(db, organization_id)
        if not fallback:
            logger.info(
                "Skipping adaptive test embedding persistence: no embedding model_id in user "
                f"settings and no org default embedding model (user_id={user.id})"
            )
            return None
        model_id = str(fallback.id)
        logger.debug(
            "Using organization default embedding model for adaptive test persistence "
            f"(user_id={user.id}, model_id={model_id})"
        )

    model = crud.get_model(db, UUIDType(model_id), organization_id, user_id)
    if not model:
        logger.warning(
            "Skipping adaptive test embedding persistence: model not found "
            f"(model_id={model_id}, user_id={user_id})"
        )
        return None

    provider = model.provider_type.type_value if model.provider_type else None
    model_name = model.model_name
    vec_len = len(vector)

    if model.dimension is not None and vec_len == model.dimension:
        dimension = model.dimension
    elif vec_len in EmbeddingConfig.SUPPORTED_DIMENSIONS:
        dimension = vec_len
        if model.dimension is not None and model.dimension != vec_len:
            logger.info(
                "Adaptive test embedding: storing vector length %s; model.dimension is %s "
                "(adaptive testing may request a fixed output size)",
                vec_len,
                model.dimension,
            )
    else:
        logger.warning(
            "Skipping adaptive test embedding persistence: vector length %s is not supported "
            "(supported: %s; model.dimension=%s)",
            vec_len,
            tuple(sorted(EmbeddingConfig.SUPPORTED_DIMENSIONS.keys())),
            model.dimension,
        )
        return None

    searchable_text = test.to_searchable_text()
    stripped = (searchable_text or "").strip()
    if not stripped:
        logger.info("Skipping adaptive test embedding persistence: empty searchable text")
        return None

    config = {
        "provider": provider,
        "model_name": model_name,
        "dimension": dimension,
        "model_id": model_id,
        "source": "adaptive_testing",
    }
    config_hash = _compute_hash(config)
    text_hash = _compute_hash(stripped)
    entity_id = str(test.id)
    entity_type = "Test"

    from rhesis.backend.app.utils.crud_utils import get_or_create_status

    active_status = get_or_create_status(
        db,
        name=EmbeddingStatus.ACTIVE.value,
        entity_type="Embedding",
        organization_id=organization_id,
        user_id=user_id,
        commit=False,
    )
    if not active_status:
        logger.error("Failed to get Active status for Embedding")
        return None

    stale_status = get_or_create_status(
        db,
        name=EmbeddingStatus.STALE.value,
        entity_type="Embedding",
        organization_id=organization_id,
        user_id=user_id,
        commit=False,
    )
    if not stale_status:
        logger.error("Failed to get Stale status for Embedding")
        return None

    existing = crud.get_embedding_by_hash(
        db,
        entity_id=entity_id,
        entity_type=entity_type,
        organization_id=organization_id,
        config_hash=config_hash,
        text_hash=text_hash,
        status_id=active_status.id,
    )
    if existing:
        logger.debug("Adaptive test embedding already exists for test_id=%s", entity_id)
        return existing

    embedding_vector = vector
    if not embedding_vector:
        return None

    stale_count = crud.mark_embeddings_stale(
        db,
        entity_id=entity_id,
        entity_type=entity_type,
        organization_id=organization_id,
        active_status_id=active_status.id,
        stale_status_id=stale_status.id,
    )
    if stale_count > 0:
        logger.info("Marked %s old embedding(s) stale for test_id=%s", stale_count, entity_id)

    embedding_create = schemas.EmbeddingCreate(
        entity_id=entity_id,
        entity_type=entity_type,
        model_id=model_id,
        embedding_config=config,
        config_hash=config_hash,
        searchable_text=stripped,
        text_hash=text_hash,
        status_id=active_status.id,
        embedding=embedding_vector,
    )

    from sqlalchemy.exc import IntegrityError

    try:
        with db.begin_nested():
            return crud.create_embedding(
                db,
                embedding=embedding_create,
                organization_id=organization_id,
                user_id=user_id,
            )
    except IntegrityError:
        existing_after = crud.get_embedding_by_hash(
            db,
            entity_id=entity_id,
            entity_type=entity_type,
            organization_id=organization_id,
            config_hash=config_hash,
            text_hash=text_hash,
            status_id=active_status.id,
        )
        if existing_after:
            return existing_after
        raise
