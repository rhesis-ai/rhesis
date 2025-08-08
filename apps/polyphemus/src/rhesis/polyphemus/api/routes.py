import os
import logging
import time
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from ..models import InferenceEngine
from .schemas import InferenceRequest

logger = logging.getLogger("rhesis-polyphemus")

router = APIRouter()

@router.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "model": os.environ.get("HF_MODEL", "cognitivecomputations/Dolphin3.0-Llama3.1-8B")}

@router.get("/health")
async def health(request: Request):
    """Health check endpoint with GPU status"""
    model_loader = request.app.state.model_loader
    
    if model_loader.model is None or model_loader.tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    return {
        "status": "healthy",
        "model": os.environ.get("HF_MODEL", "cognitivecomputations/Dolphin3.0-Llama3.1-8B"),
        "gpu": model_loader.get_gpu_info()
    }

@router.post("/generate")
async def generate(request: InferenceRequest, req: Request):
    """Generate text from prompt"""
    model_loader = req.app.state.model_loader
    
    if model_loader.model is None or model_loader.tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        # Get model and tokenizer from app state
        engine = InferenceEngine(model_loader.model, model_loader.tokenizer)
        
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
                    system_prompt=request.system_prompt
                ),
                media_type="text/event-stream"
            )
        
        # Non-streaming request
        result = await engine.generate_text(
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            repetition_penalty=request.repetition_penalty,
            system_prompt=request.system_prompt
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Error during generation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}") 