"""Pluggable diversity metrics for sorting suggestion embeddings by batch centroid."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

_ROW_NORM_EPS = 1e-12


class EmbeddingDiversityStrategy(ABC):
    """Scores embedding rows; larger score means more diverse (preferred first)."""

    @abstractmethod
    def scores(self, matrix: np.ndarray) -> np.ndarray:
        """Return shape (n,) float scores for *matrix* (n, d), float64."""


class EuclideanCentroidDiversity(EmbeddingDiversityStrategy):
    """Euclidean distance from the arithmetic mean centroid (legacy behavior)."""

    def scores(self, matrix: np.ndarray) -> np.ndarray:
        centroid = np.mean(matrix, axis=0)
        return np.linalg.norm(matrix - centroid, axis=1)


class CosineCentroidDiversity(EmbeddingDiversityStrategy):
    """One minus cosine similarity to the mean direction of L2-normalized rows."""

    def scores(self, matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.maximum(norms, _ROW_NORM_EPS)
        unit = matrix / norms
        mean_dir = np.mean(unit, axis=0)
        mean_norm = np.linalg.norm(mean_dir)
        centroid_unit = mean_dir / np.maximum(mean_norm, _ROW_NORM_EPS)
        cos_sim = unit @ centroid_unit
        return 1.0 - cos_sim


DEFAULT_EMBEDDING_DIVERSITY_STRATEGY: EmbeddingDiversityStrategy = CosineCentroidDiversity()
