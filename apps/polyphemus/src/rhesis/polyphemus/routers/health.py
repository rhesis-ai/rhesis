"""
Health check endpoints for Polyphemus service.
Provides / and /health endpoints for Cloud Run health checks and monitoring.
"""

import logging
import os

import torch
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..services import is_model_loaded

logger = logging.getLogger("rhesis-polyphemus")

router = APIRouter()

# Get model name for responses
modelname = os.environ.get("HF_MODEL", "distilgpt2")


@router.get("/")
async def root():
    """
    Root endpoint - basic service information.
    Returns service name and status.
    """
    return {
        "service": "Rhesis Polyphemus",
        "status": "running",
        "model": modelname,
    }


@router.get("/health")
async def health():
    """
    Health check endpoint for Cloud Run and monitoring.

    Checks:
    - Service is running
    - Model loading status (may be unloaded if lazy loading)
    - GPU availability and status

    Returns 200 if service is healthy, even if model is not yet loaded
    (since model loads lazily on first request).
    """
    try:
        # Get GPU info
        gpu_info = {}
        if torch.cuda.is_available():
            try:
                gpu_info = {
                    "device_name": torch.cuda.get_device_name(0),
                    "device_count": torch.cuda.device_count(),
                    "memory_allocated_MB": round(torch.cuda.memory_allocated(0) / 1024**2, 2),
                    "memory_reserved_MB": round(torch.cuda.memory_reserved(0) / 1024**2, 2),
                    "max_memory_MB": round(
                        torch.cuda.get_device_properties(0).total_memory / 1024**2, 2
                    ),
                }
            except Exception as e:
                gpu_info = {"error": str(e)}
        else:
            gpu_info = {"available": False}

        # Check model loading status (non-blocking check)
        # Since model loads lazily, it may not be loaded yet
        model_loaded = is_model_loaded()

        # Service is healthy if it's running, even if model isn't loaded yet
        # (model loads on first request)
        health_status = {
            "status": "healthy",
            "service": "Rhesis Polyphemus",
            "model": modelname,
            "model_loaded": model_loaded,
            "gpu": gpu_info,
        }

        return JSONResponse(content=health_status, status_code=200)

    except Exception as e:
        logger.error(f"Health check error: {str(e)}", exc_info=True)
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": str(e),
            },
            status_code=503,
        )
