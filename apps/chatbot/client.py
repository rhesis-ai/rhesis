import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Import endpoint module first to initialize RhesisClient
# This ensures only ONE tracer provider exists (critical for proper trace nesting)
import endpoint as endpoint_module
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from notifications import send_rate_limit_alert
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from rhesis.sdk import endpoint

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Get rate limit from environment variable (total desired limit across all workers)
# This will be automatically divided by the number of workers
WORKERS = int(os.getenv("WORKERS", "4"))  # Number of Gunicorn workers
TOTAL_RATE_LIMIT_AUTHENTICATED = int(os.getenv("CHATBOT_RATE_LIMIT", "1000"))
TOTAL_RATE_LIMIT_PUBLIC = 100  # Public users get lower limit

# Calculate per-worker limits (each worker tracks independently with in-memory storage)
RATE_LIMIT_PER_WORKER_AUTHENTICATED = TOTAL_RATE_LIMIT_AUTHENTICATED // WORKERS
RATE_LIMIT_PER_WORKER_PUBLIC = TOTAL_RATE_LIMIT_PUBLIC // WORKERS

RATE_LIMIT_AUTHENTICATED = f"{RATE_LIMIT_PER_WORKER_AUTHENTICATED}/day"
RATE_LIMIT_PUBLIC = f"{RATE_LIMIT_PER_WORKER_PUBLIC}/day"

# API Key for backend authentication (optional)
CHATBOT_API_KEY = os.getenv("CHATBOT_API_KEY")

# Session management configuration
SESSION_TIMEOUT_HOURS = int(os.getenv("SESSION_TIMEOUT_HOURS", "24"))  # Default 24 hours
SESSION_CLEANUP_INTERVAL_MINUTES = int(
    os.getenv("SESSION_CLEANUP_INTERVAL_MINUTES", "60")
)  # Default 60 minutes

# HTTP Bearer token security
security = HTTPBearer(auto_error=False)  # auto_error=False allows optional auth


def get_rate_limit_identifier(request: Request) -> str:
    """
    Get rate limit identifier from request state.

    This is called by the limiter's key function, but should NOT be used
    as the primary rate limiting mechanism. Use check_rate_limit_chatbot
    dependency instead.

    This function now only reads from request.state which is set by
    the verify_api_key_with_rate_limit dependency.
    """
    # Get identifier from request state (set by auth dependency)
    identifier = getattr(request.state, "rate_limit_id", None)
    if identifier:
        return identifier

    # Fallback to IP address (shouldn't normally reach here with proper dependency order)
    ip = get_remote_address(request)
    logger.warning(f"⚠️ Rate limit identifier not found in request state, falling back to IP: {ip}")
    return f"public:{ip}"


# Initialize rate limiter with custom key function
limiter = Limiter(key_func=get_rate_limit_identifier)


# Session storage with metadata
class SessionData:
    """Session data with metadata for garbage collection."""

    def __init__(self, messages: List[dict] = None):
        self.messages = messages or []
        self.last_accessed = datetime.utcnow()
        self.created_at = datetime.utcnow()

    def update_access_time(self):
        """Update the last accessed timestamp."""
        self.last_accessed = datetime.utcnow()

    def is_stale(self, timeout_hours: int) -> bool:
        """Check if session is stale based on last access time."""
        age = datetime.utcnow() - self.last_accessed
        return age > timedelta(hours=timeout_hours)


# Store chat sessions with metadata
sessions: Dict[str, SessionData] = {}


async def cleanup_stale_sessions():
    """Background task to periodically clean up stale sessions."""
    while True:
        try:
            await asyncio.sleep(SESSION_CLEANUP_INTERVAL_MINUTES * 60)

            # Find stale sessions
            stale_session_ids = [
                session_id
                for session_id, session_data in sessions.items()
                if session_data.is_stale(SESSION_TIMEOUT_HOURS)
            ]

            # Remove stale sessions
            for session_id in stale_session_ids:
                del sessions[session_id]

            if stale_session_ids:
                logger.info(
                    f"🧹 Cleaned up {len(stale_session_ids)} stale sessions. "
                    f"Active sessions: {len(sessions)}"
                )
            else:
                logger.debug(f"🧹 Session cleanup: {len(sessions)} active sessions, 0 stale")

        except Exception as e:
            logger.error(f"❌ Error in session cleanup task: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to run background tasks."""
    # Start cleanup task
    cleanup_task = asyncio.create_task(cleanup_stale_sessions())
    logger.info(
        f"🚀 Started session cleanup task (interval: {SESSION_CLEANUP_INTERVAL_MINUTES}min, "
        f"timeout: {SESSION_TIMEOUT_HOURS}h)"
    )

    yield

    # Cleanup on shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        logger.info("🛑 Session cleanup task cancelled")


def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    Verify API key for authentication.
    Returns authentication info. Does not raise error if no key is provided (allows public access).
    Also sets rate_limit_id and rate_limit_tier in request.state for proper rate limiting.
    """
    if not CHATBOT_API_KEY:
        # No API key configured - all requests are treated as public
        ip = get_remote_address(request)
        request.state.rate_limit_id = f"public:{ip}"
        request.state.rate_limit_tier = "public"
        return {"authenticated": False, "tier": "public"}

    if not credentials:
        # No credentials provided - public access with stricter limits
        ip = get_remote_address(request)
        request.state.rate_limit_id = f"public:{ip}"
        request.state.rate_limit_tier = "public"
        return {"authenticated": False, "tier": "public"}

    if credentials.credentials != CHATBOT_API_KEY:
        # Invalid credentials
        raise HTTPException(
            status_code=401,
            detail="Invalid API key. Public access available with rate limit of 100 requests/day.",
        )

    # Valid credentials - authenticated access
    # Use user/org ID for per-user rate limiting
    org_id = request.headers.get("X-Organization-ID", "default-org")
    user_id = request.headers.get("X-User-ID", "default-user")
    request.state.rate_limit_id = f"authenticated:{org_id}:{user_id}"
    request.state.rate_limit_tier = "authenticated"

    logger.info(
        f"✅ Authenticated request - Identifier: {request.state.rate_limit_id}, "
        f"Rate limit: {RATE_LIMIT_AUTHENTICATED}"
    )

    return {"authenticated": True, "tier": "authenticated"}


async def check_rate_limit_chatbot(
    request: Request,
    auth: dict = Depends(verify_api_key),  # Authentication runs first
) -> dict:
    """
    Rate limit dependency that runs after authentication.

    This ensures rate limiting is based on authenticated user/org identifiers
    instead of just IP addresses.

    Returns the auth dict for downstream dependencies.
    """
    from limits import parse

    # Get the rate limit identifier and tier from request state (set by verify_api_key)
    identifier = request.state.rate_limit_id
    tier = request.state.rate_limit_tier

    # Determine which rate limit to apply
    rate_limit_str = RATE_LIMIT_AUTHENTICATED if tier == "authenticated" else RATE_LIMIT_PUBLIC

    try:
        # Parse the rate limit string into a RateLimitItem
        rate_limit_item = parse(rate_limit_str)

        # Manually perform rate limit check using slowapi's internal limiter
        allowed = limiter._limiter.hit(rate_limit_item, identifier)

        if not allowed:
            logger.warning(
                f"🚫 Rate limit exceeded - Tier: {tier}, Identifier: {identifier}, "
                f"Limit: {rate_limit_str}"
            )

            # Send email notification (async, non-blocking)
            try:
                send_rate_limit_alert(request, identifier, tier.capitalize(), rate_limit_str)
            except Exception as e:
                logger.error(f"⚠️ Error sending rate limit alert: {e}")

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again later. Limit: {rate_limit_str}",
            )

        logger.debug(f"✅ Rate limit check passed - Tier: {tier}, Identifier: {identifier}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Rate limiting error for {identifier}: {str(e)}", exc_info=True)
        # Don't block request on rate limiter errors - fail open
        pass

    return auth


app = FastAPI(
    title="Rhesis Insurance Chatbot API",
    description=(
        "Default insurance chatbot (Rosalind) for new user onboarding. "
        "Provides instant access to explore Rhesis AI capabilities."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# Custom rate limit exceeded handler with email notifications
async def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler for rate limit exceeded that sends email notifications.
    """
    # Get the rate limit identifier
    identifier = get_rate_limit_identifier(request)

    # Determine rate limit type and value
    is_authenticated = identifier.startswith("authenticated:")
    rate_limit_type = "Authenticated" if is_authenticated else "Public"
    rate_limit_value = RATE_LIMIT_AUTHENTICATED if is_authenticated else RATE_LIMIT_PUBLIC

    logger.warning(
        f"🚫 RATE LIMIT EXCEEDED - Type: {rate_limit_type}, "
        f"Identifier: {identifier}, Limit: {rate_limit_value}"
    )

    # Send email notification (async, non-blocking)
    try:
        send_rate_limit_alert(request, identifier, rate_limit_type, rate_limit_value)
    except Exception as e:
        # Log but don't fail the response
        logger.error(f"⚠️ Error sending rate limit alert: {e}")

    # Return the standard rate limit exceeded response (not awaited - it returns a Response object)
    return _rate_limit_exceeded_handler(request, exc)


# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_exceeded_handler)


def get_available_use_cases() -> List[str]:
    """Get list of available use cases from use_cases directory."""
    try:
        import os

        current_dir = os.path.dirname(os.path.abspath(__file__))
        use_cases_dir = os.path.join(current_dir, "use_cases")

        use_cases = []
        for filename in os.listdir(use_cases_dir):
            if filename.endswith(".md"):
                use_case_name = filename[:-3]  # Remove .md extension
                use_cases.append(use_case_name)
        return sorted(use_cases)
    except Exception:
        return ["insurance"]  # Default fallback


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    use_case: Optional[str] = "insurance"  # Default to insurance for backward compatibility
    image_urls: Optional[List[str]] = None  # List of image URLs to analyze
    image_data: Optional[List[str]] = None  # List of base64-encoded images


class ChatResponse(BaseModel):
    message: str
    session_id: str
    context: List[str]
    metadata: dict


class ImageGenerationRequest(BaseModel):
    prompt: str
    n: Optional[int] = 1
    size: Optional[str] = "1024x1024"


class ImageGenerationResponse(BaseModel):
    images: List[str]  # URLs or base64-encoded images
    metadata: dict


@endpoint()
async def chat(
    message: str,
    session_id: Optional[str] = None,
    use_case: str = "insurance",
    conversation_history: Optional[List[dict]] = None,
    image_urls: Optional[List[str]] = None,
    image_data: Optional[List[str]] = None,
) -> ChatResponse:
    """
    Process a chat message and return structured response.

    Args:
        message: User's message
        session_id: Session identifier
        use_case: Use case for system prompt
        conversation_history: Previous conversation messages
        image_urls: Optional list of image URLs to analyze
        image_data: Optional list of base64-encoded images

    Returns:
        ChatResponse with message, session_id, context, and metadata (use_case, intent, has_images)
    """
    # Create single ResponseGenerator instance to avoid duplicate instantiation
    # This ensures proper trace nesting - all operations under one trace
    response_generator = endpoint_module.get_response_generator(use_case)

    # Generate context using the instance
    context_fragments = response_generator.generate_context(message)

    # Recognize intent from the current message
    intent_result = response_generator.recognize_intent(message)

    # Check if images are provided
    has_images = bool(image_urls or image_data)

    # Get assistant response using the same instance
    if has_images:
        # Use multimodal generation with images
        response_text = response_generator.get_multimodal_response(
            message=message,
            conversation_history=conversation_history,
            image_urls=image_urls,
            image_data=image_data,
        )
    else:
        # Use standard text generation
        response_text = "".join(
            response_generator.stream_assistant_response(
                message, conversation_history=conversation_history
            )
        )

    # Return Pydantic model
    return ChatResponse(
        message=response_text,
        session_id=session_id or str(uuid.uuid4()),
        context=context_fragments,
        metadata={"use_case": use_case, "intent": intent_result, "has_images": has_images},
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and load balancer."""
    return {"status": "healthy", "service": "rhesis-insurance-chatbot", "version": "1.0.0"}


@app.get("/")
async def root(request: Request, auth: dict = Depends(verify_api_key)):
    """Root endpoint with API information."""
    return {
        "service": "Rhesis Insurance Chatbot API",
        "description": "Chat with Rosalind, your insurance expert",
        "authentication": {
            "status": "authenticated" if auth["authenticated"] else "public",
            "tier": auth["tier"],
        },
        "endpoints": {
            "chat": "/chat (POST) - Text chat with optional image analysis",
            "generate_image": "/generate-image (POST) - Generate images from text",
            "health": "/health (GET)",
            "use_cases": "/use-cases (GET)",
            "session": "/sessions/{session_id} (GET, DELETE)",
        },
        "rate_limits": {
            "authenticated": f"{TOTAL_RATE_LIMIT_AUTHENTICATED} requests per day per user",
            "public": f"{TOTAL_RATE_LIMIT_PUBLIC} requests per day per IP address",
            "current_tier": auth["tier"],
        },
    }


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: Request, chat_request: ChatRequest, auth: dict = Depends(check_rate_limit_chatbot)
):
    try:
        logger.info(
            f"💬 Chat request received - Auth tier: {auth['tier']}, "
            f"Message: {chat_request.message[:50]}..."
        )

        # Get or create session_id
        session_id = chat_request.session_id or str(uuid.uuid4())

        # Use the provided use_case or default to insurance
        use_case = chat_request.use_case or "insurance"

        # Validate use case exists, default to insurance if not
        available_use_cases = get_available_use_cases()
        if use_case not in available_use_cases:
            use_case = "insurance"

        # Initialize session if it doesn't exist
        if session_id not in sessions:
            sessions[session_id] = SessionData()
            logger.info(f"📝 Created new session: {session_id}")

        # Update session access time
        sessions[session_id].update_access_time()

        # Get conversation history before adding the new message
        conversation_history = sessions[session_id].messages.copy()

        # Call the endpoint function
        result = await chat(
            message=chat_request.message,
            session_id=session_id,
            use_case=use_case,
            conversation_history=conversation_history,
            image_urls=chat_request.image_urls,
            image_data=chat_request.image_data,
        )

        # Update session with the conversation
        sessions[session_id].messages.append({"role": "user", "content": chat_request.message})
        sessions[session_id].messages.append({"role": "assistant", "content": result.message})

        logger.info(f"✅ Response generated successfully - Length: {len(result.message)} chars")

        return result

    except Exception as e:
        logger.error(f"❌ Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-image", response_model=ImageGenerationResponse)
async def generate_image_endpoint(
    request: Request,
    image_request: ImageGenerationRequest,
    auth: dict = Depends(check_rate_limit_chatbot),
):
    """Generate images from text prompts.

    Args:
        image_request: Image generation request with prompt, n, and size

    Returns:
        ImageGenerationResponse with generated image URLs/data
    """
    try:
        logger.info(
            f"🎨 Image generation request - Auth tier: {auth['tier']}, "
            f"Prompt: {image_request.prompt[:50]}..., n={image_request.n}"
        )

        # Get response generator
        response_generator = endpoint_module.get_response_generator()

        # Generate images
        result = response_generator.generate_image(
            prompt=image_request.prompt, n=image_request.n, size=image_request.size
        )

        # Normalize result to list
        if isinstance(result, str):
            images = [result]
        else:
            images = result

        logger.info(f"✅ Generated {len(images)} image(s)")

        return ImageGenerationResponse(
            images=images,
            metadata={
                "prompt": image_request.prompt,
                "n": image_request.n,
                "size": image_request.size,
                "count": len(images),
            },
        )

    except Exception as e:
        logger.error(f"❌ Error in image generation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Image generation failed: {str(e)}. Make sure image generation is enabled.",
        )


@app.get("/sessions/{session_id}")
async def get_session(
    request: Request, session_id: str, auth: dict = Depends(check_rate_limit_chatbot)
):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update access time when retrieving session
    sessions[session_id].update_access_time()

    return {
        "messages": sessions[session_id].messages,
        "created_at": sessions[session_id].created_at.isoformat(),
        "last_accessed": sessions[session_id].last_accessed.isoformat(),
    }


@app.delete("/sessions/{session_id}")
async def delete_session(
    request: Request, session_id: str, auth: dict = Depends(check_rate_limit_chatbot)
):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del sessions[session_id]
    logger.info(f"🗑️ Manually deleted session: {session_id}")
    return {"message": "Session deleted"}


@app.get("/use-cases")
async def list_use_cases(request: Request, auth: dict = Depends(check_rate_limit_chatbot)):
    """Get list of available use cases"""
    try:
        use_cases = get_available_use_cases()
        return {"use_cases": use_cases}
    except Exception as e:
        return {"use_cases": ["insurance"], "error": str(e)}
