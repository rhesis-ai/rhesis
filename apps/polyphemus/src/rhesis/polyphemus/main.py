import gc
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from rhesis.polyphemus.models import LazyModelLoader
from rhesis.polyphemus.routers.services import router as services_router

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rhesis-polyphemus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Don't load model during startup - models load lazily on first request
    # Creating LazyModelLoader with auto_loading=False to avoid blocking startup
    # The actual model instances are managed by the service cache
    model_loader = LazyModelLoader(auto_loading=False)
    app.state.model_loader = model_loader
    # Note: Model loading is now handled by LazyModelLoader via service cache
    # Models are cached and reused across requests
    logger.info("Polyphemus service starting - models will load on first request")

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
    description="Dolphin 3.0 Llama 3.1 8B Inference API",
    lifespan=lifespan,
)


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
