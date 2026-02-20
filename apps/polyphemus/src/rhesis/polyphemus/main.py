import logging

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from rhesis.polyphemus.routers.services import router as services_router
from rhesis.polyphemus.utils.middleware import ProcessTimeMiddleware
from rhesis.polyphemus.utils.rate_limit import limiter

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rhesis-polyphemus")


# Initialize FastAPI app
app = FastAPI(
    title="Rhesis Polyphemus",
    description="Polyphemus is a Vertex AI proxy service for the Rhesis platform.",
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
