"""
FastAPI Server with Rhesis Telemetry

This example demonstrates observability in a real FastAPI application.
All API endpoints are automatically traced using the @observe decorator.

Prerequisites:
    1. Start the backend: docker compose up -d
    2. Set environment variables:
       export RHESIS_API_KEY=your-api-key
       export RHESIS_PROJECT_ID=your-project-id

Run with:
    uv run --extra fastapi fastapi_example.py

Then test with:
    curl http://localhost:8000/chat -X POST -H "Content-Type: application/json" \\
      -d '{"input": "Hello!", "session_id": "test-123"}'
    curl http://localhost:8000/health
    
Or visit http://localhost:8000/docs for interactive API documentation.
"""

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from rhesis.sdk import RhesisClient, observe
from rhesis.sdk.telemetry.schemas import AIOperationType

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Initialize Rhesis client to set up telemetry infrastructure
# This must happen before defining any @observe decorated functions
client = RhesisClient(
    api_key=os.getenv("RHESIS_API_KEY", "demo-key"),
    project_id=os.getenv("RHESIS_PROJECT_ID", "demo-project"),
    environment="development",
)


# Request/Response models
class ChatRequest(BaseModel):
    input: str
    session_id: Optional[str] = None
    temperature: Optional[float] = 0.7


class ChatResponse(BaseModel):
    output: str
    session_id: str
    model: str
    tokens: dict


class HealthResponse(BaseModel):
    status: str
    service: str
    telemetry: str


# Traced helper functions
@observe(span_name=AIOperationType.RETRIEVAL)
def fetch_user_context(session_id: str) -> dict:
    """Fetch conversation context from database/vector store."""
    print(f"📊 Fetching context for session: {session_id}")
    time.sleep(0.1)  # Simulate DB query

    return {
        "session_id": session_id,
        "previous_messages": 3,
        "user_preferences": ["concise", "technical"],
    }


@observe(span_name=AIOperationType.TOOL_INVOKE, tool_name="weather_api")
def check_weather(location: str = "San Francisco") -> dict:
    """Check weather via external API."""
    print(f"🌤️  Checking weather for: {location}")
    time.sleep(0.2)  # Simulate API call

    return {
        "location": location,
        "temperature": 72,
        "condition": "sunny",
        "humidity": 45,
    }


@observe(
    span_name=AIOperationType.LLM_INVOKE,
    model="gemini-pro",
    provider="google",
)
def call_llm(prompt: str, temperature: float = 0.7) -> dict:
    """Call Gemini LLM via Rhesis (or direct API)."""
    print(f"🤖 Calling LLM with prompt: {prompt[:50]}...")

    # Simulate LLM call
    time.sleep(0.8)

    # In reality, this would call Gemini via Rhesis or Google API
    response_text = f"I understand you said: '{prompt}'. Here's my thoughtful response."

    return {
        "text": response_text,
        "tokens": {
            "input": len(prompt.split()),
            "output": len(response_text.split()),
            "total": len(prompt.split()) + len(response_text.split()),
        },
        "model": "gemini-pro",
    }


# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("\n" + "=" * 70)
    print("🚀 FastAPI Server with Rhesis Telemetry")
    print("=" * 70)
    print("\nServer starting...")
    print("  • Telemetry: Enabled (@observe decorators)")
    print("  • Traces sent to: configured backend")
    print("  • API docs: http://localhost:8000/docs")
    print("\nTest endpoints:")
    print("  • POST http://localhost:8000/chat")
    print("  • GET  http://localhost:8000/health")
    print("=" * 70 + "\n")

    yield

    print("\n" + "=" * 70)
    print("🛑 Server shutting down...")
    print("=" * 70 + "\n")


# FastAPI app
app = FastAPI(
    title="Rhesis Telemetry Demo",
    description="FastAPI server with OpenTelemetry tracing via @observe",
    version="1.0.0",
    lifespan=lifespan,
)


# API Endpoints
@app.get("/health", response_model=HealthResponse)
@observe()  # Trace health checks too
async def health_check():
    """
    Health check endpoint.

    This endpoint is traced but has minimal overhead.
    """
    return {
        "status": "healthy",
        "service": "rhesis-telemetry-demo",
        "telemetry": "enabled",
    }


@app.post("/chat", response_model=ChatResponse)
@observe()  # Creates root span for the entire request
async def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint with full observability.

    This demonstrates a realistic use case:
    1. Fetch user context (traced)
    2. Check weather if mentioned (traced)
    3. Call LLM (traced)
    4. Return response

    All operations are traced as child spans, creating a hierarchy.
    """
    print(f"\n{'=' * 60}")
    print("💬 POST /chat")
    print(f"   Input: {request.input}")
    print(f"   Session: {request.session_id or 'new'}")
    print(f"{'=' * 60}\n")

    try:
        # Step 1: Fetch context (creates child span)
        session_id = request.session_id or f"session-{int(time.time())}"
        context = fetch_user_context(session_id)
        print(f"✅ Context fetched: {context['previous_messages']} messages")

        # Step 2: Check weather if mentioned (creates child span)
        weather_data = None
        if "weather" in request.input.lower():
            weather_data = check_weather()
            print(f"✅ Weather data: {weather_data['condition']}, {weather_data['temperature']}°F")

        # Step 3: Call LLM (creates child span)
        # Build prompt with context
        prompt = f"User: {request.input}"
        if weather_data:
            prompt += (
                f"\nCurrent weather: {weather_data['condition']}, {weather_data['temperature']}°F"
            )

        llm_response = call_llm(prompt, temperature=request.temperature)
        print(f"✅ LLM response generated ({llm_response['tokens']['total']} tokens)")

        # Step 4: Return response
        response = ChatResponse(
            output=llm_response["text"],
            session_id=session_id,
            model=llm_response["model"],
            tokens=llm_response["tokens"],
        )

        print("\n✅ Request completed successfully")
        print(f"{'=' * 60}\n")

        return response

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"{'=' * 60}\n")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Rhesis Telemetry Demo API",
        "docs": "/docs",
        "endpoints": {
            "chat": "POST /chat",
            "health": "GET /health",
        },
        "telemetry": "enabled",
        "traced_operations": [
            "ai.llm.invoke",
            "ai.retrieval",
            "ai.tool.invoke",
            "function.*",
        ],
    }


# CLI for running the server
if __name__ == "__main__":
    import uvicorn

    # Run the FastAPI server
    uvicorn.run(
        "fastapi_example:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload for cleaner output
        log_level="info",
    )
