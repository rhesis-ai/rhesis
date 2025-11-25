"""
Rhesis API endpoints for Polyphemus service.
Provides /generate endpoint that accepts messages format.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from rhesis.polyphemus.auth import require_api_key
from rhesis.polyphemus.schemas import GenerateRequest
from rhesis.polyphemus.services import generate_text

from rhesis.backend.app.models.user import User

logger = logging.getLogger("rhesis-polyphemus")

router = APIRouter()


@router.post("/generate")
async def generate(request: GenerateRequest, current_user: User = Depends(require_api_key)):
    """
    Generate text using Rhesis API format.

    Requires API key authentication via Bearer token.

    Accepts:
        {
            "messages": [
                { "content": "Hello!", "role": "user" }
            ],
            "temperature": 0.7,
            "max_tokens": 512,
            "model": "huggingface/distilgpt2"  # optional
        }

    Returns:
        Rhesis API response format
    """
    try:
        logger.info(f"Generation request from user: {current_user.email}")
        return await generate_text(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error during generation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")
