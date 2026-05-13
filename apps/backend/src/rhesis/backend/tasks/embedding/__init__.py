"""Embedding generation tasks."""

from .generate import generate_embedding_task
from .graph import compute_graph_task

__all__ = ["compute_graph_task", "generate_embedding_task"]
