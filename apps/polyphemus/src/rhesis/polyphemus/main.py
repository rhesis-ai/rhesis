import gc
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Load polyphemus .env first so INFERENCE_ENGINE, MODEL_PATH, etc. are set
# when running via ./rh dev polyphemus (no need to cd to apps/polyphemus)
_polyphemus_root = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_polyphemus_root / ".env")

from rhesis.polyphemus.models import INFERENCE_ENGINE  # noqa: E402
from rhesis.polyphemus.routers.services import router as services_router  # noqa: E402
from rhesis.polyphemus.utils.middleware import ProcessTimeMiddleware  # noqa: E402
from rhesis.polyphemus.utils.rate_limit import limiter  # noqa: E402

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rhesis-polyphemus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Log configuration, models load lazily on first request
    logger.info(f"Polyphemus service starting - inference engine: {INFERENCE_ENGINE}")
    logger.info("Models will load on first request (lazy loading)")

    if INFERENCE_ENGINE == "vllm":
        logger.info("vLLM engine configured - expect 10-20x speedup over standard transformers")

    yield

    # Shutdown: Clean up resources
    logger.info("Shutting down Polyphemus service...")

    # Clean up model cache
    from rhesis.polyphemus.services.services import _model_cache

    for model_id, model in list(_model_cache.items()):
        logger.info(f"Cleaning up model: {model_id}")
        # vLLM cleanup
        if hasattr(model, "_llm") and model._llm is not None:
            del model._llm
            model._llm = None
        # Transformers cleanup
        if hasattr(model, "model") and model.model is not None:
            model.model = None
        if hasattr(model, "tokenizer") and model.tokenizer is not None:
            model.tokenizer = None
        if hasattr(model, "_internal_model"):
            model._internal_model = None

    _model_cache.clear()

    # Force garbage collection to free GPU memory
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("GPU cache cleared")
    except ImportError:
        pass

    logger.info("Resources cleaned up")


# Initialize FastAPI app
app = FastAPI(
    title="Rhesis Polyphemus",
    description=(
        "Polyphemus is a high-performance LLM inference service "
        "for the Rhesis platform. Powered by vLLM for optimized "
        "GPU inference."
    ),
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add middleware
app.add_middleware(ProcessTimeMiddleware)


# Health check endpoints
@app.get("/")
async def root():
    """Root endpoint - basic service information."""
    return {
        "service": "Rhesis Polyphemus",
        "status": "running",
        "inference_engine": INFERENCE_ENGINE,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run and monitoring."""
    return {
        "status": "ok",
        "inference_engine": INFERENCE_ENGINE,
    }


# Register routers
app.include_router(services_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "rhesis.polyphemus.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="debug",
    )
