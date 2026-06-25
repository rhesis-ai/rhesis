"""Tests for embedding 2D graph builder (UMAP + HDBSCAN pipeline)."""

import uuid
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from rhesis.backend.app.models.test import Test
from rhesis.backend.app.services.embedding import graph_builder
from rhesis.backend.app.services.embedding.graph_builder import (
    _generate_cluster_labels,
    _reduce_dimensions,
    build_2d_graph,
)
from rhesis.backend.app.utils.model_errors import ModelConfigurationError


def _mock_user(org_id: str, user_id: str) -> MagicMock:
    user = MagicMock()
    user.organization_id = org_id
    user.id = user_id
    return user


def _mock_embedding(
    *,
    entity_id: uuid.UUID | None = None,
    config_hash: str = "cfg-a",
    vector: list[float] | None = None,
    searchable_text: str = "sample",
) -> MagicMock:
    e = MagicMock()
    e.id = uuid.uuid4()
    e.entity_id = entity_id or uuid.uuid4()
    e.entity_type = "Test"
    e.config_hash = config_hash
    e.embedding = vector if vector is not None else [0.0, 0.0, 0.0]
    e.searchable_text = searchable_text
    return e


@pytest.mark.unit
class TestGenerateClusterLabels:
    @patch.object(graph_builder, "get_model")
    @patch.object(graph_builder, "get_user_generation_model")
    def test_empty_centroids_skips_model_resolution(
        self, mock_get_user_model, mock_get_model, test_db
    ):
        user = MagicMock()
        embeddings = [_mock_embedding(), _mock_embedding()]
        cluster_ids = np.array([-1, -1])
        umap_50d = np.array([[0.0, 0.0], [1.0, 1.0]], dtype=np.float64)

        result = _generate_cluster_labels(embeddings, cluster_ids, umap_50d, {}, test_db, user)

        assert result == {}
        mock_get_user_model.assert_not_called()
        mock_get_model.assert_not_called()

    @patch.object(graph_builder, "get_user_generation_model")
    def test_model_resolution_failure_returns_empty(self, mock_get_user_model, test_db):
        mock_get_user_model.side_effect = ModelConfigurationError("misconfigured")
        user = MagicMock()
        emb = _mock_embedding(searchable_text="hello")
        cluster_ids = np.array([0])
        umap_50d = np.array([[0.0, 0.0]], dtype=np.float64)
        centroids = {0: np.array([0.0, 0.0])}

        result = _generate_cluster_labels([emb], cluster_ids, umap_50d, centroids, test_db, user)

        assert result == {}


@pytest.mark.unit
class TestReduceDimensions:
    def test_invalid_purpose_raises(self):
        X = np.array([[0.0, 1.0], [1.0, 0.0], [0.5, 0.5]])
        with pytest.raises(ValueError, match="Invalid purpose"):
            _reduce_dimensions(X, purpose="other")


@pytest.mark.unit
class TestBuild2DGraph:
    def test_empty_entity_list_returns_empty_graph(
        self, test_db, test_org_id, authenticated_user_id
    ):
        user = _mock_user(test_org_id, authenticated_user_id)
        graph = build_2d_graph(test_db, [], user)
        assert graph.points == []
        assert graph.clusters == []

    def test_no_embeddings_fetched_returns_empty_graph(
        self, test_db, test_org_id, authenticated_user_id
    ):
        user = _mock_user(test_org_id, authenticated_user_id)
        eid = uuid.uuid4()
        with patch.object(graph_builder, "fetch_embeddings", return_value=[]):
            graph = build_2d_graph(test_db, [eid], user)
        assert graph.points == []

    def test_mixed_config_hash_returns_empty_graph(
        self, test_db, test_org_id, authenticated_user_id
    ):
        user = _mock_user(test_org_id, authenticated_user_id)
        a = _mock_embedding(config_hash="h1")
        b = _mock_embedding(config_hash="h2")
        eids = [a.entity_id, b.entity_id]
        with patch.object(graph_builder, "fetch_embeddings", return_value=[a, b]):
            graph = build_2d_graph(test_db, eids, user, embedded_entity=Test)
        assert graph.points == []

    def test_duplicate_entity_in_fetched_embeddings_returns_empty_graph(
        self, test_db, test_org_id, authenticated_user_id
    ):
        user = _mock_user(test_org_id, authenticated_user_id)
        shared = uuid.uuid4()
        a = _mock_embedding(entity_id=shared)
        b = _mock_embedding(entity_id=shared)
        with patch.object(graph_builder, "fetch_embeddings", return_value=[a, b]):
            graph = build_2d_graph(test_db, [shared], user)
        assert graph.points == []

    def test_single_point_trivial_layout(self, test_db, test_org_id, authenticated_user_id):
        user = _mock_user(test_org_id, authenticated_user_id)
        emb = _mock_embedding(vector=[0.1, 0.2])
        with patch.object(graph_builder, "fetch_embeddings", return_value=[emb]):
            graph = build_2d_graph(test_db, [emb.entity_id], user)
        assert len(graph.points) == 1
        assert graph.points[0].x == pytest.approx(0.0)
        assert graph.points[0].y == pytest.approx(0.0)
        assert graph.points[0].cluster_index == -1
        assert graph.points[0].embedding_id == emb.id
        assert graph.clusters == []

    def test_two_points_trivial_layout(self, test_db, test_org_id, authenticated_user_id):
        user = _mock_user(test_org_id, authenticated_user_id)
        left = _mock_embedding(vector=[0.0, 0.0])
        right = _mock_embedding(vector=[1.0, 1.0])
        with patch.object(graph_builder, "fetch_embeddings", return_value=[left, right]):
            graph = build_2d_graph(test_db, [left.entity_id, right.entity_id], user)
        assert len(graph.points) == 2
        xs = sorted(p.x for p in graph.points)
        assert xs[0] == pytest.approx(-0.5)
        assert xs[1] == pytest.approx(0.5)
        assert all(p.cluster_index == -1 for p in graph.points)

    @patch.object(graph_builder, "_generate_cluster_labels")
    @patch.object(graph_builder, "_cluster_with_hdbscan")
    @patch.object(graph_builder, "_reduce_dimensions")
    def test_three_plus_points_pipeline(
        self,
        mock_reduce,
        mock_cluster,
        mock_labels,
        test_db,
        test_org_id,
        authenticated_user_id,
    ):
        user = _mock_user(test_org_id, authenticated_user_id)
        uids = [uuid.uuid4() for _ in range(3)]
        embs = [
            _mock_embedding(entity_id=uids[0], vector=[0.0] * 8, searchable_text="a"),
            _mock_embedding(entity_id=uids[1], vector=[1.0] * 8, searchable_text="b"),
            _mock_embedding(entity_id=uids[2], vector=[0.5] * 8, searchable_text="c"),
        ]
        # Clustering UMAP must be >2D so build_2d_graph runs the visualization pass.
        umap_50 = np.array(
            [[0.0, 0.0, 0.1], [1.0, 0.0, 0.2], [0.5, 1.0, 0.3]],
            dtype=np.float64,
        )
        umap_2 = np.array([[0.0, 0.0], [2.0, 0.0], [1.0, 3.0]], dtype=np.float64)
        mock_reduce.side_effect = [umap_50, umap_2]
        mock_cluster.return_value = (
            np.array([0, 0, -1]),
            {0: np.array([0.33, 0.33, 0.15])},
        )
        mock_labels.return_value = {0: "Alpha"}

        with patch.object(graph_builder, "fetch_embeddings", return_value=embs):
            graph = build_2d_graph(test_db, uids, user)

        assert mock_reduce.call_count == 2
        mock_cluster.assert_called_once()
        mock_labels.assert_called_once()

        assert len(graph.points) == 3
        assert {p.searchable_text for p in graph.points} == {"a", "b", "c"}
        by_text = {p.searchable_text: p for p in graph.points}
        assert by_text["a"].cluster_index == 0
        assert by_text["b"].cluster_index == 0
        assert by_text["c"].cluster_index == -1

        assert len(graph.clusters) == 1
        assert graph.clusters[0].cluster_index == 0
        assert graph.clusters[0].label == "Alpha"
        assert graph.clusters[0].size == 2

    @patch.object(graph_builder, "get_user_generation_model")
    @patch.object(graph_builder, "_cluster_with_hdbscan")
    @patch.object(graph_builder, "_reduce_dimensions")
    def test_graph_uses_unlabeled_when_label_model_unavailable(
        self,
        mock_reduce,
        mock_cluster,
        mock_get_user_model,
        test_db,
        test_org_id,
        authenticated_user_id,
    ):
        mock_get_user_model.side_effect = ModelConfigurationError("misconfigured")
        user = _mock_user(test_org_id, authenticated_user_id)
        uids = [uuid.uuid4() for _ in range(3)]
        embs = [
            _mock_embedding(entity_id=uids[0], vector=[0.0] * 8),
            _mock_embedding(entity_id=uids[1], vector=[1.0] * 8),
            _mock_embedding(entity_id=uids[2], vector=[0.5] * 8),
        ]
        umap_50 = np.array(
            [[0.0, 0.0, 0.1], [1.0, 0.0, 0.2], [0.5, 1.0, 0.3]],
            dtype=np.float64,
        )
        umap_2 = np.array([[0.0, 0.0], [2.0, 0.0], [1.0, 3.0]], dtype=np.float64)
        mock_reduce.side_effect = [umap_50, umap_2]
        mock_cluster.return_value = (
            np.array([0, 0, -1]),
            {0: np.array([0.33, 0.33, 0.15])},
        )

        with patch.object(graph_builder, "fetch_embeddings", return_value=embs):
            graph = build_2d_graph(test_db, uids, user)

        assert mock_reduce.call_count == 2
        assert len(graph.points) == 3
        assert len(graph.clusters) == 1
        assert graph.clusters[0].label == "Unlabeled"
        assert graph.clusters[0].size == 2
