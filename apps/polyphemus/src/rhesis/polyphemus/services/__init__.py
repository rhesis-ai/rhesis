"""
Polyphemus services module.
Exports service functions for model instance management.
"""

from .services import get_polyphemus_instance, is_model_loaded

__all__ = ["get_polyphemus_instance", "is_model_loaded"]
