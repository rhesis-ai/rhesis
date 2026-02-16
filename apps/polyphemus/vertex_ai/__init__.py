"""Vertex AI model deployment utilities for Polyphemus."""

from rhesis.polyphemus.vertex_ai.deploy import deploy_model_vllm, get_or_create_endpoint

__all__ = ["deploy_model_vllm", "get_or_create_endpoint"]
