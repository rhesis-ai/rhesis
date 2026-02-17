"""
Polyphemus services module.
Exports service functions for model instance management and generation.
"""

from rhesis.polyphemus.services.services import (
    generate_text,
    generate_text_via_vertex_endpoint,
    get_polyphemus_instance,
    is_model_loaded,
)

__all__ = [
    "get_polyphemus_instance",
    "is_model_loaded",
    "generate_text",
    "generate_text_via_vertex_endpoint",
]
