"""Build graph structures from stored embeddings (UMAP, clustering, etc.)."""

import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

import numpy as np
from hdbscan import HDBSCAN
from sqlalchemy.orm import Session
from umap import UMAP

from rhesis.backend.app import crud, models
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.embedding import Cluster, Scatter2DGraph, ScatterPoint2D
from rhesis.backend.app.utils.user_model_utils import get_user_generation_model
from rhesis.sdk.models.factory import get_model

logger = logging.getLogger(__name__)


def _embedding_entity_type_key(model_or_name: type | str) -> str:
    return model_or_name if isinstance(model_or_name, str) else model_or_name.__name__


def fetch_embeddings(
    db: Session,
    entity_ids: Sequence[UUID],
    embedded_entity: type | str = Test,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> list[models.Embedding]:
    """Load embeddings for one entity type and a set of IDs."""
    if not entity_ids:
        return []
    return crud.get_active_embeddings_for_entities(
        db,
        entity_ids=list(entity_ids),
        entity_type=_embedding_entity_type_key(embedded_entity),
        organization_id=organization_id,
        user_id=user_id,
    )


def _reduce_dimensions(X: np.ndarray, purpose: str) -> np.ndarray:
    """Reduce the dimensions of the embeddings (requires n_samples >= 3)."""
    n_samples = X.shape[0]

    max_neighbors = max(1, n_samples - 1)

    if purpose == "clustering":
        n_components = max(2, min(50, n_samples - 1))
        n_neighbors = max(3, min(15, int(0.08 * n_samples)))
        n_neighbors = min(n_neighbors, max_neighbors)
        n_neighbors = max(2, n_neighbors)
    elif purpose == "visualization":
        n_components = 2
        n_neighbors = max(2, min(10, int(0.05 * n_samples)))
        n_neighbors = min(n_neighbors, max_neighbors)
        n_neighbors = max(1, n_neighbors)
    else:
        raise ValueError(f"Invalid purpose: {purpose}")

    umap = UMAP(n_components=n_components, n_neighbors=n_neighbors, random_state=42)
    return umap.fit_transform(X)


def _cluster_with_hdbscan(X: np.ndarray) -> tuple[np.ndarray, dict[int, np.ndarray]]:
    """Cluster the embeddings with HDBSCAN."""
    n_samples = X.shape[0]

    # 5-10% of dataset, min 3, max 20, never exceeding n_samples
    min_cluster_size = max(3, min(20, int(0.08 * n_samples)))
    min_cluster_size = min(min_cluster_size, n_samples)
    min_cluster_size = max(2, min_cluster_size)

    # min_samples: typically smaller than min_cluster_size
    min_samples = max(2, min_cluster_size // 2)
    min_samples = min(min_samples, n_samples)

    clusterer = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="euclidean",
        cluster_selection_epsilon=0.5,
    )
    cluster_ids = clusterer.fit_predict(X)

    centroids = {}
    for cluster_id in np.unique(cluster_ids):
        if cluster_id == -1:  # Skip noise points
            continue
        mask = cluster_ids == cluster_id
        centroids[int(cluster_id)] = X[mask].mean(axis=0)

    return cluster_ids, centroids


def _generate_cluster_labels(
    embeddings: list[models.Embedding],
    cluster_ids: np.ndarray,
    umap_50d: np.ndarray,
    centroids: dict[int, np.ndarray],
    db: Session,
    user: User,
) -> dict[int, str]:
    _model = get_user_generation_model(db, user)
    if isinstance(_model, str):
        _model = get_model(_model)

    labels = {}
    for cluster_id, centroid in centroids.items():
        logger.info(f"Generating label for cluster {cluster_id}")

        # Get all embeddings in this cluster
        mask = cluster_ids == cluster_id
        cluster_embeddings = [e for e, m in zip(embeddings, mask) if m]
        cluster_coords = umap_50d[mask]

        # Find closest to centroid
        distances = np.linalg.norm(cluster_coords - centroid, axis=1)
        closest_indices = np.argsort(distances)[:3]

        # Get text from closest
        sample_text = [
            cluster_embeddings[i].searchable_text
            for i in closest_indices
            if cluster_embeddings[i].searchable_text
        ]

        if not sample_text:
            labels[cluster_id] = "Unlabeled"
            continue

        combined_text = "\n".join(sample_text)
        prompt = "Create a very short label for these items (1-2-3 words max): " + combined_text

        try:
            label = _model.generate(prompt)
            labels[cluster_id] = label.strip()
        except Exception as e:
            logger.error(f"Error generating cluster label: {e}", exc_info=True)
            labels[cluster_id] = "Unlabeled"
            continue

    return labels


def _scatter_point(
    embedding: models.Embedding,
    cluster_index: int,
    x: float,
    y: float,
) -> ScatterPoint2D:
    return ScatterPoint2D(
        embedding_id=embedding.id,
        entity_id=embedding.entity_id,
        entity_type=embedding.entity_type,
        cluster_index=cluster_index,
        searchable_text=embedding.searchable_text or "",
        x=x,
        y=y,
    )


def _trivial_single_point_graph(embedding: models.Embedding, now_utc: datetime) -> Scatter2DGraph:
    """One sample: pin at origin, no clusters (noise only). Used when UMAP is ill-defined."""
    return Scatter2DGraph(
        computed_at=now_utc,
        clusters=[],
        points=[_scatter_point(embedding, -1, 0.0, 0.0)],
    )


def _trivial_two_point_graph(
    embeddings_two: list[models.Embedding],
    now_utc: datetime,
) -> Scatter2DGraph:
    """Two samples: fixed symmetric layout without UMAP."""
    left, right = embeddings_two
    return Scatter2DGraph(
        computed_at=now_utc,
        clusters=[],
        points=[
            _scatter_point(left, -1, -0.5, 0.0),
            _scatter_point(right, -1, 0.5, 0.0),
        ],
    )


def build_2d_graph(
    db: Session,
    entity_ids: Sequence[UUID],
    user: User,
    *,
    embedded_entity: type | str = Test,
) -> Scatter2DGraph:
    """Build a graph from embeddings for visualization and clustering."""

    requested_count = len(entity_ids)

    embeddings = fetch_embeddings(
        db,
        entity_ids,
        embedded_entity=embedded_entity,
        organization_id=user.organization_id,
        user_id=user.id,
    )

    entity_type_key = _embedding_entity_type_key(embedded_entity)
    logger.info(
        "Building embedding graph: entity_type=%s requested_entity_ids=%s "
        "active_embeddings_loaded=%s",
        entity_type_key,
        requested_count,
        len(embeddings),
    )

    if requested_count > 0 and not embeddings:
        logger.warning(
            "Embedding graph has no active embeddings for requested entities: "
            "entity_type=%s requested_entity_ids=%s",
            entity_type_key,
            requested_count,
        )

    if not embeddings:
        return Scatter2DGraph(computed_at=datetime.now(timezone.utc), clusters=[], points=[])

    config_hashes = {e.config_hash for e in embeddings}
    seen_entity_ids: set[UUID] = set()
    duplicate_entity = False
    for e in embeddings:
        if e.entity_id in seen_entity_ids:
            duplicate_entity = True
            break
        seen_entity_ids.add(e.entity_id)

    if len(config_hashes) > 1 or duplicate_entity:
        logger.warning(
            "Skipping embedding graph: ambiguous active embeddings "
            "(entity_type=%s mixed_config=%s duplicate_entity=%s)",
            entity_type_key,
            len(config_hashes) > 1,
            duplicate_entity,
        )
        return Scatter2DGraph(computed_at=datetime.now(timezone.utc), clusters=[], points=[])

    now_utc = datetime.now(timezone.utc)
    n_samples = len(embeddings)

    if n_samples == 1:
        return _trivial_single_point_graph(embeddings[0], now_utc)
    if n_samples == 2:
        return _trivial_two_point_graph(embeddings, now_utc)

    X = np.array([e.embedding for e in embeddings], dtype=np.float64)

    umap_50d = _reduce_dimensions(X, purpose="clustering")
    umap_2d = _reduce_dimensions(X, purpose="visualization")

    cluster_ids, centroids = _cluster_with_hdbscan(umap_50d)

    cluster_labels = _generate_cluster_labels(
        embeddings, cluster_ids, umap_50d, centroids, db, user
    )

    # Build scatter points
    points = []
    for embedding, cluster_id, coords_2d in zip(embeddings, cluster_ids, umap_2d):
        points.append(
            _scatter_point(
                embedding,
                int(cluster_id),
                float(coords_2d[0]),
                float(coords_2d[1]),
            )
        )

    # Build clusters
    cluster_counts = {}
    for cluster_id in cluster_ids:
        cluster_id = int(cluster_id)
        if cluster_id == -1:
            continue
        cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1

    clusters = [
        Cluster(
            cluster_index=cluster_id,
            label=cluster_labels.get(cluster_id, "Unlabeled"),
            size=cluster_counts[cluster_id],
        )
        for cluster_id in sorted(cluster_counts.keys())
    ]

    return Scatter2DGraph(
        computed_at=now_utc,
        clusters=clusters,
        points=points,
    )
