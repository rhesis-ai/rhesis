import gc
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from rhesis.polyphemus.models import LazyModelLoader
from rhesis.polyphemus.routers.services import router as services_router
from rhesis.polyphemus.utils.middleware import ProcessTimeMiddleware
from rhesis.polyphemus.utils.rate_limit import limiter

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rhesis-polyphemus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Download model from GCS if needed (faster than HuggingFace Hub)
    logger.info("Polyphemus service starting...")

    # Import here to avoid issues if google-cloud-storage is not installed
    try:
        from rhesis.polyphemus.utils.gcs_model_loader import ensure_model_cached

        # Download model from GCS to local cache (2-5 min on cold start)
        logger.info("Ensuring model is cached from GCS...")
        model_cached = ensure_model_cached()

        if model_cached:
            logger.info("✅ Model successfully cached from GCS")
        else:
            logger.warning(
                "⚠️  Model not cached from GCS. "
                "Will download from HuggingFace on first request (slow)."
            )
    except Exception as e:
        logger.error(f"Failed to cache model from GCS: {e}")
        logger.warning("Will attempt to load from HuggingFace on first request")

    # Create LazyModelLoader (models load on first request)
    model_loader = LazyModelLoader(auto_loading=False)
    app.state.model_loader = model_loader
    logger.info("Polyphemus service ready - models will load on first request")

    yield

    # Shutdown: Clean up resources
    if hasattr(app.state.model_loader, "model") and app.state.model_loader.model is not None:
        app.state.model_loader.model = None
    if (
        hasattr(app.state.model_loader, "tokenizer")
        and app.state.model_loader.tokenizer is not None
    ):
        app.state.model_loader.tokenizer = None
    gc.collect()
    logger.info("Resources cleaned up")


# Initialize FastAPI app
app = FastAPI(
    title="Rhesis Polyphemus",
    description="Polyphemus is a service that provides a REST API for the Rhesis platform.",
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
    return {"service": "Rhesis Polyphemus", "status": "running"}


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run and monitoring."""
    return {"status": "ok"}


# Register routers
app.include_router(services_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
