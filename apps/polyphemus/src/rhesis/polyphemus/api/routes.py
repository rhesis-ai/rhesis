import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..models import InferenceEngine
from .schemas import InferenceRequest

logger = logging.getLogger("rhesis-polyphemus")

router = APIRouter()


@router.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "model": os.environ.get("HF_MODEL", "distilgpt2")}


@router.get("/health")
async def health(request: Request):
    """Health check endpoint with GPU status"""
    model_loader = request.app.state.model_loader

    # ModelLoader may not have model loaded since InferenceEngine handles it
    # Check if we can get GPU info
    gpu_info = {}
    try:
        gpu_info = model_loader.get_gpu_info()
    except:
        pass

    return {
        "status": "healthy",
        "model": os.environ.get("HF_MODEL", "distilgpt2"),
        "gpu": gpu_info,
        "note": "Model loads on first inference request via HuggingFaceLLM",
    }


@router.post("/generate")
async def generate(request: InferenceRequest, req: Request):
    """Generate text from prompt"""
    try:
        # Initialize InferenceEngine (uses HuggingFaceLLM internally)
        engine = InferenceEngine()

        # Check if streaming is requested
        if request.stream:
            return StreamingResponse(
                engine.generate_stream(
                    prompt=request.prompt,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    top_k=request.top_k,
                    repetition_penalty=request.repetition_penalty,
                    system_prompt=request.system_prompt,
                ),
                media_type="text/event-stream",
            )

        # Non-streaming request
        result = await engine.generate_text(
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            repetition_penalty=request.repetition_penalty,
            system_prompt=request.system_prompt,
        )

        return result

    except Exception as e:
        logger.error(f"Error during generation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")
