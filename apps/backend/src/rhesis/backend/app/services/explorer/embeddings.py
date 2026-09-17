"""Explorer-scoped embedding helpers (SDK vectorization + embedding table)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from rhesis.backend.app.crud import user as user_crud
from rhesis.backend.app.services.explorer.diversity_strategies import (
    DEFAULT_EMBEDDING_DIVERSITY_STRATEGY,
)
from rhesis.backend.app.utils.model_errors import EmbeddingProviderNotConfigured

# Aliased: this module exports its own `resolve_embedder`, the explorer-flavoured
# one that pins the dimension and guards against the native-provider recursion.
from rhesis.backend.app.utils.user_model_utils import resolve_embedder as resolve_user_embedder

if TYPE_CHECKING:
    from rhesis.backend.app.services.explorer.diversity_strategies import (
        EmbeddingDiversityStrategy,
    )

logger = logging.getLogger(__name__)

# Explorer test sets persist to ``embedding`` columns (see EmbeddingConfig.SUPPORTED_DIMENSIONS).
# Force this output size so providers defaulting to large vectors (e.g. Gemini 3072) still store.
EXPLORER_EMBEDDING_DIMENSION = 768


def sort_by_diversity(
    suggestions: List[Dict[str, Any]],
    strategy: Optional[EmbeddingDiversityStrategy] = None,
) -> List[Dict[str, Any]]:
    """Sort suggestions by a centroid-based embedding diversity metric.

    Uses
    :class:`~rhesis.backend.app.services.explorer.diversity_strategies.EmbeddingDiversityStrategy`
    to score rows after building a single batch matrix. The default strategy is
    :class:`~rhesis.backend.app.services.explorer.diversity_strategies.CosineCentroidDiversity`
    (one minus cosine similarity to the mean direction). Larger scores are more
    diverse and sort first. Sets ``diversity_score`` on each item. Items without a
    usable embedding are placed last with ``diversity_score`` set to ``None``.

    Parameters
    ----------
    strategy
        If ``None``, uses :data:`DEFAULT_EMBEDDING_DIVERSITY_STRATEGY` (cosine).
    """
    scorer = strategy if strategy is not None else DEFAULT_EMBEDDING_DIVERSITY_STRATEGY
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
        logger.warning("Inconsistent embedding dimensions in suggestions; skipping diversity sort")
        for item, _ in with_vectors:
            item["diversity_score"] = None
        return suggestions

    matrix = np.asarray([v for _, v in with_vectors], dtype=np.float64)
    diversity_values = scorer.scores(matrix)

    order = np.argsort(-diversity_values)
    sorted_with: List[Dict[str, Any]] = []
    for idx in order:
        item, _ = with_vectors[int(idx)]
        item["diversity_score"] = float(diversity_values[int(idx)])
        sorted_with.append(item)

    return sorted_with + without


def resolve_embedder(db: Session, user_id: str):
    """Resolve the embedding model for a user once.

    Returns a ready-to-use SDK ``BaseEmbedder`` instance configured with
    :data:`EXPLORER_EMBEDDING_DIMENSION`.  Call this once and pass the
    result to :func:`a_generate_embedding_vector` or
    :func:`a_generate_embedding_vectors_batch` to avoid repeated DB lookups.
    """
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise ValueError(f"User not found: {user_id}")

    embedder = resolve_user_embedder(db, user, dimensions=EXPLORER_EMBEDDING_DIMENSION)

    # Same latent recursion as EmbeddingGenerator._resolve_embedder: a
    # misconfigured DEFAULT_EMBEDDING_MODEL resolves to the Rhesis native
    # provider, whose .generate() would call this backend's own
    # /services/generate/embedding endpoint over HTTP. Catch it here, in
    # process, before paying for that doomed round-trip.
    from rhesis.sdk.models.providers.native import RhesisEmbedder

    if isinstance(embedder, RhesisEmbedder):
        raise EmbeddingProviderNotConfigured(
            "Embedding model resolved to the Rhesis native provider, which would call "
            "the embedding endpoint recursively. Set DEFAULT_EMBEDDING_MODEL to an "
            "actual provider (e.g. vertex_ai/text-embedding-005) to enable embeddings."
        )

    return embedder


async def a_generate_embedding_vector(
    text: str,
    db: Session,
    user_id: str,
    *,
    embedder=None,
) -> List[float]:
    """Async embed plain text using the user's configured embedding model or platform default.

    Uses the embedder's async API.

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

    target_dim = EXPLORER_EMBEDDING_DIMENSION
    vector = await embedder.a_generate(text=stripped, dimensions=target_dim)
    out = list(vector)
    if len(out) != target_dim:
        logger.warning(
            "Explorer embedding length %s != requested %s (provider may ignore dimensions); "
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

    target_dim = EXPLORER_EMBEDDING_DIMENSION
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
                        "Explorer embedding length %s != requested %s; persistence may be skipped",
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

    return list(await asyncio.gather(*[asyncio.create_task(_embed_one(t)) for t in texts]))
