"""Unit tests for adaptive-testing embedding diversity strategies."""

import numpy as np
import pytest

from rhesis.backend.app.services.adaptive_testing.diversity_strategies import (
    CosineCentroidDiversity,
    DEFAULT_EMBEDDING_DIVERSITY_STRATEGY,
    EuclideanCentroidDiversity,
)
from rhesis.backend.app.services.adaptive_testing.embeddings import sort_by_diversity


def test_euclidean_centroid_middle_is_least_diverse() -> None:
    """Collinear points: middle is closest to centroid → lowest Euclidean score."""
    matrix = np.array([[0.0], [1.0], [2.0]], dtype=np.float64)
    scores = EuclideanCentroidDiversity().scores(matrix)
    assert scores[1] < scores[0] == scores[2]


def test_cosine_centroid_opposite_direction_most_diverse() -> None:
    """One unit vector opposite the majority mean direction gets highest 1 − cos score."""
    matrix = np.array(
        [
            [1.0, 0.0],
            [1.0, 0.0],
            [1.0, 0.0],
            [-1.0, 0.0],
        ],
        dtype=np.float64,
    )
    scores = CosineCentroidDiversity().scores(matrix)
    assert scores[3] > scores[0]
    assert scores[0] == pytest.approx(scores[1])
    assert scores[1] == pytest.approx(scores[2])


def test_sort_by_diversity_default_sets_scores_and_order() -> None:
    suggestions = [
        {"input": "a", "embedding": [1.0, 0.0]},
        {"input": "b", "embedding": [1.0, 0.0]},
        {"input": "c", "embedding": [-1.0, 0.0]},
    ]
    out = sort_by_diversity(suggestions)
    assert [s["input"] for s in out] == ["c", "a", "b"]
    assert out[0]["diversity_score"] is not None
    assert out[0]["diversity_score"] > out[1]["diversity_score"]


def test_sort_by_diversity_euclidean_strategy_changes_order_vs_default() -> None:
    """Crafted batch where centroid distance and cosine-to-mean-direction disagree."""
    base = [
        {"input": "a", "embedding": [1.0, 0.0]},
        {"input": "b", "embedding": [10.0, 0.0]},
        {"input": "c", "embedding": [2.0, 8.0]},
    ]
    cos_sorted = sort_by_diversity([dict(x) for x in base])
    euc_sorted = sort_by_diversity(
        [dict(x) for x in base],
        strategy=EuclideanCentroidDiversity(),
    )
    assert [s["input"] for s in cos_sorted] == ["c", "a", "b"]
    assert [s["input"] for s in euc_sorted] == ["b", "c", "a"]


def test_default_strategy_is_cosine() -> None:
    assert isinstance(DEFAULT_EMBEDDING_DIVERSITY_STRATEGY, CosineCentroidDiversity)
