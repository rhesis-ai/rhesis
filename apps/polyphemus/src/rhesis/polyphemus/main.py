import gc
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from rhesis.polyphemus.models import ModelLoader
from rhesis.polyphemus.routers.health import router as health_router
from rhesis.polyphemus.routers.services import router as services_router
from rhesis.polyphemus.utils import ProcessTimeMiddleware

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rhesis-polyphemus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ModelLoader is kept for health endpoint compatibility
    # Actual model loading happens in InferenceEngine when first used
    model_loader = ModelLoader()
    app.state.model_loader = model_loader
    # Note: Model loading is now handled by InferenceEngine (HuggingFaceLLM)
    # We keep ModelLoader for health endpoint compatibility
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

# Add middleware
app.add_middleware(ProcessTimeMiddleware)

# Register routers
app.include_router(health_router)
app.include_router(services_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
