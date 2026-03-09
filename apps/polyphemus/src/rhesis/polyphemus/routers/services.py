"""
Rhesis API endpoints for Polyphemus service.
Provides /generate endpoint that accepts messages format and forwards to Vertex AI.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request

from rhesis.backend.app.models.user import User
from rhesis.polyphemus.schemas import (
    BatchGenerationResponse,
    BatchItemResponse,
    GenerateBatchRequest,
    GenerateRequest,
)
from rhesis.polyphemus.services import (
    generate_text_batch_via_vertex_endpoint,
    generate_text_via_vertex_endpoint,
)
from rhesis.polyphemus.utils.rate_limit import check_rate_limit

logger = logging.getLogger("rhesis-polyphemus")

router = APIRouter()


@router.post("/generate")
async def generate(
    request: Request,
    generate_request: GenerateRequest,
    current_user: User = Depends(check_rate_limit),
):
    """
    Generate text by calling Vertex AI endpoint.

    Requires API key authentication via Bearer token.
    Rate limited to 10000 requests per day per authenticated user.

    Accepts:
        {
            "messages": [
                { "content": "Hello!", "role": "user" }
            ],
            "temperature": 0.7,
            "max_tokens": 2048,  // optional; omit to leave unbounded
            "top_p": 1.0,
            "top_k": 50,
            "json_schema": { ... }  // optional, for structured output
        }

    Returns:
        Rhesis API response format
    """
    try:
        logger.info(f"Generation request from user: {current_user.email}")

        # Get Vertex AI config from environment
        endpoint_id = os.getenv("POLYPHEMUS_ENDPOINT_ID")
        project_id = os.getenv("POLYPHEMUS_PROJECT_ID")
        location = os.getenv("POLYPHEMUS_LOCATION", "us-central1")

        if not endpoint_id or not project_id:
            raise ValueError(
                "Vertex AI endpoint not configured. "
                "Set POLYPHEMUS_ENDPOINT_ID and POLYPHEMUS_PROJECT_ID."
            )

        return await generate_text_via_vertex_endpoint(
            generate_request,
            endpoint_id=endpoint_id,
            project_id=project_id,
            location=location,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error during generation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")


@router.post("/generate_batch")
async def generate_batch(
    request: Request,
    batch_request: GenerateBatchRequest,
    current_user: User = Depends(check_rate_limit),
):
    """
    Generate text for multiple requests by calling Vertex AI endpoint concurrently.

    Requires API key authentication via Bearer token.
    Rate limited to 10000 batch requests per day per authenticated user. Each batch
    call counts as one request regardless of how many items it contains. Use
    MAX_BATCH_SIZE (currently 50) to control the maximum number of items per call.

    Accepts:
        {
            "requests": [
                {
                    "messages": [ { "content": "Hello!", "role": "user" } ],
                    "temperature": 0.7,
                    ...
                },
                ...
            ]
        }

    Returns:
        BatchGenerationResponse with one response (or error) per request.
    """
    try:
        logger.info(
            "Batch generation request from user: %s (%d items)",
            current_user.email,
            len(batch_request.requests),
        )

        endpoint_id = os.getenv("POLYPHEMUS_ENDPOINT_ID")
        project_id = os.getenv("POLYPHEMUS_PROJECT_ID")
        location = os.getenv("POLYPHEMUS_LOCATION", "us-central1")

        if not endpoint_id or not project_id:
            raise ValueError(
                "Vertex AI endpoint not configured. "
                "Set POLYPHEMUS_ENDPOINT_ID and POLYPHEMUS_PROJECT_ID."
            )

        results = await generate_text_batch_via_vertex_endpoint(
            batch_request.requests,
            endpoint_id=endpoint_id,
            project_id=project_id,
            location=location,
        )

        responses = [BatchItemResponse(**r) for r in results]
        return BatchGenerationResponse(responses=responses)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Error during batch generation: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch generation error: {str(e)}")
