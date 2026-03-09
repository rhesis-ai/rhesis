"""
Polyphemus services module.
Exports service functions for Vertex AI generation.
"""

from rhesis.polyphemus.services.services import (
    generate_text_batch_via_vertex_endpoint,
    generate_text_via_vertex_endpoint,
)

__all__ = [
    "generate_text_batch_via_vertex_endpoint",
    "generate_text_via_vertex_endpoint",
]
