import logging
import gc
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from .models import ModelLoader
from .api import router
from .utils import ProcessTimeMiddleware

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rhesis-polyphemus")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load model
    model_loader = ModelLoader()
    app.state.model_loader = model_loader
    await model_loader.load_model()
    
    yield
    
    # Shutdown: Clean up resources
    app.state.model_loader.model = None
    app.state.model_loader.tokenizer = None
    gc.collect()
    logger.info("Resources cleaned up")

# Initialize FastAPI app
app = FastAPI(
    title="Rhesis Polyphemus", 
    description="Dolphin 3.0 Llama 3.1 8B Inference API",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(ProcessTimeMiddleware)

# Register router
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080) 