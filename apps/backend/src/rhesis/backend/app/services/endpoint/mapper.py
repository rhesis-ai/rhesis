"""Mapper service integration for SDK endpoints."""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.user import User
from rhesis.backend.app.services.connector.mapping import MappingService
from rhesis.backend.logging import logger


def generate_and_apply_mappings(
    db: Session,
    user: User,
    endpoint: Endpoint,
    function_name: str,
    function_data: Dict[str, Any],
    is_new_endpoint: bool = False,
) -> Dict[str, Any]:
    """
    Generate mappings for an SDK endpoint and apply them.

    Args:
        db: Database session
        user: User for language model access
        endpoint: Endpoint to update with mappings
        function_name: Name of the function
        function_data: Function metadata from SDK
        is_new_endpoint: Whether this is a newly created endpoint

    Returns:
        Dict with mapping result details {
            "source": str,
            "confidence": float,
            "reasoning": str,
            "updated": bool
        }
    """
    mapper_service = MappingService()

    # Generate or use existing mappings
    action = "Generating" if is_new_endpoint else "Generating/validating"
    logger.info(f"[{function_name}] {action} mappings...")

    mapping_result = mapper_service.generate_or_use_existing(
        db=db,
        user=user,
        endpoint=endpoint,
        sdk_metadata=function_data.get("metadata", {}),
        function_data=function_data,
    )

    # Update endpoint if mappings should be updated
    updated = False
    if mapping_result.should_update:
        endpoint.request_mapping = mapping_result.request_mapping
        endpoint.response_mapping = mapping_result.response_mapping
        flag_modified(endpoint, "request_mapping")
        flag_modified(endpoint, "response_mapping")

        # Store mapping metadata for transparency
        if not endpoint.endpoint_metadata:
            endpoint.endpoint_metadata = {}

        endpoint.endpoint_metadata["mapping_info"] = {
            "source": mapping_result.source,
            "confidence": mapping_result.confidence,
            "reasoning": mapping_result.reasoning,
            "generated_at": datetime.utcnow().isoformat(),
        }
        flag_modified(endpoint, "endpoint_metadata")

        logger.info(
            f"[{function_name}] Updated mappings "
            f"(source: {mapping_result.source}, "
            f"confidence: {mapping_result.confidence:.2f})"
        )
        updated = True

    return {
        "source": mapping_result.source,
        "confidence": mapping_result.confidence,
        "reasoning": mapping_result.reasoning,
        "updated": updated,
    }
