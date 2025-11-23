"""Mapping service orchestrator with 4-tier priority system."""

from typing import Any, Dict, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.user import User
from rhesis.backend.logging import logger

from .auto_mapper import AutoMapper
from .llm_mapper import LLMMapper


class MappingResult(BaseModel):
    """Result of mapping generation with metadata."""

    request_mapping: Dict[str, str] = Field(
        description="Jinja2 template mapping standard fields to function parameters"
    )
    response_mapping: Dict[str, str] = Field(
        description="Mapping from function output to standard fields"
    )
    source: Literal[
        "sdk_manual", "sdk_manual_partial", "existing_db", "auto_mapped", "llm_generated"
    ] = Field(description="Source of the mappings")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score for the mappings")
    should_update: bool = Field(
        description="Whether the endpoint should be updated with these mappings"
    )
    reasoning: str = Field(default="", description="Explanation of mapping choices and source")


class MappingService:
    """Orchestrates mapping generation with 4-tier priority system."""

    def __init__(self):
        """Initialize mapping service with auto and LLM mappers."""
        self.auto_mapper = AutoMapper()
        self.llm_mapper = LLMMapper()

    def generate_or_use_existing(
        self,
        db: Session,
        user: User,
        endpoint: Endpoint,
        sdk_metadata: Dict[str, Any],
        function_data: Dict[str, Any],
    ) -> MappingResult:
        """
        Generate mappings with 4-tier priority system.

        Priority:
        1. SDK manual mappings (from @collaborate decorator)
        2. Existing DB mappings (preserve manual edits)
        3. Auto-mapping (heuristic-based)
        4. LLM fallback (when auto-mapping confidence < 0.7)

        Args:
            db: Database session
            user: User for LLM model access
            endpoint: Endpoint being synced
            sdk_metadata: Metadata from SDK registration
            function_data: Function information

        Returns:
            MappingResult with request_mapping, response_mapping, source, confidence,
            should_update flag, and reasoning
        """
        function_name = function_data.get("name", "unknown")

        # Priority 1: SDK manual mappings from @collaborate decorator
        sdk_request = sdk_metadata.get("request_mapping")
        sdk_response = sdk_metadata.get("response_mapping")

        # Allow partial manual mappings - use SDK provided ones and auto-generate the rest
        if sdk_request or sdk_response:
            logger.info(
                f"[{function_name}] Using SDK manual mappings "
                f"(request: {bool(sdk_request)}, response: {bool(sdk_response)})"
            )

            # If only partial mappings provided, generate the missing ones
            final_request_mapping = sdk_request
            final_response_mapping = sdk_response
            source = "sdk_manual"

            if not final_request_mapping or not final_response_mapping:
                # Need to auto-generate missing mapping
                logger.info(f"[{function_name}] Auto-generating missing mapping component")
                auto_result = self.auto_mapper.generate_mappings(
                    function_name=function_name,
                    parameters=function_data.get("parameters", {}),
                    return_type=function_data.get("return_type", "any"),
                    description=sdk_metadata.get("description", ""),
                )

                if not final_request_mapping:
                    final_request_mapping = auto_result["request_mapping"]
                    source = "sdk_manual_partial"
                if not final_response_mapping:
                    final_response_mapping = auto_result["response_mapping"]
                    source = "sdk_manual_partial"

            return MappingResult(
                request_mapping=final_request_mapping,
                response_mapping=final_response_mapping,
                source=source,
                confidence=1.0,
                should_update=True,
                reasoning=(
                    "Explicit mappings from @collaborate decorator"
                    + (" with auto-generated components" if source == "sdk_manual_partial" else "")
                ),
            )

        # Priority 2: Existing DB mappings (preserve manual edits on reconnection)
        if endpoint.request_mapping and endpoint.response_mapping:
            logger.info(f"[{function_name}] Using existing DB mappings (preserving manual edits)")
            return MappingResult(
                request_mapping=endpoint.request_mapping,
                response_mapping=endpoint.response_mapping,
                source="existing_db",
                confidence=1.0,
                should_update=False,
                reasoning="Existing mappings preserved from database",
            )

        # Priority 3: Auto-mapping with heuristics
        logger.info(f"[{function_name}] Attempting auto-mapping")
        auto_result = self.auto_mapper.generate_mappings(
            function_name=function_name,
            parameters=function_data.get("parameters", {}),
            return_type=function_data.get("return_type", "any"),
            description=sdk_metadata.get("description", ""),
        )

        # Check if auto-mapping confidence is sufficient
        if auto_result["confidence"] >= 0.7:
            logger.info(
                f"[{function_name}] Auto-mapping successful "
                f"(confidence: {auto_result['confidence']:.2f})"
            )
            return MappingResult(
                request_mapping=auto_result["request_mapping"],
                response_mapping=auto_result["response_mapping"],
                source="auto_mapped",
                confidence=auto_result["confidence"],
                should_update=True,
                reasoning=(
                    f"Auto-detected from function signature. "
                    f"Matched: {auto_result['matched_fields']}"
                ),
            )

        # Priority 4: LLM fallback
        logger.info(
            f"[{function_name}] Auto-mapping confidence low "
            f"({auto_result['confidence']:.2f}), using LLM fallback"
        )

        llm_result = self.llm_mapper.generate_mappings(
            db=db,
            user=user,
            function_name=function_name,
            parameters=function_data.get("parameters", {}),
            return_type=function_data.get("return_type", "any"),
            description=sdk_metadata.get("description", ""),
        )

        return MappingResult(
            request_mapping=llm_result["request_mapping"],
            response_mapping=llm_result["response_mapping"],
            source="llm_generated",
            confidence=llm_result["confidence"],
            should_update=True,
            reasoning=llm_result.get("reasoning", "Generated by LLM"),
        )
