"""Mapping generation service for SDK endpoints."""

from .auto_mapper import AutoMapper
from .llm_mapper import LLMMapper
from .mapper_service import MappingResult, MappingService
from .mapping_validator import MappingValidator


# Import endpoint_validator separately to avoid circular imports
def get_endpoint_validation_service():
    """Get the endpoint validation service instance (lazy import)."""
    from .endpoint_validator import endpoint_validation_service

    return endpoint_validation_service


__all__ = [
    "AutoMapper",
    "LLMMapper",
    "MappingResult",
    "MappingService",
    "MappingValidator",
    "get_endpoint_validation_service",
]
