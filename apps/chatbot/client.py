import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from endpoint import generate_context, stream_assistant_response
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from notifications import send_rate_limit_alert
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from rhesis.sdk import collaborate

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
    Determine rate limit identifier based on authentication.

    - Authenticated requests (with valid API key): Use user/org ID from headers
    - Unauthenticated requests: Use IP address
    """
    # Check if request has valid authentication
    auth_header = request.headers.get("Authorization", "")

    logger.info(
        f"🔍 Rate limit check - Has auth header: {bool(auth_header)}, "
        f"API key configured: {bool(CHATBOT_API_KEY)}"
    )

    if auth_header and CHATBOT_API_KEY:
        try:
            token = auth_header.replace("Bearer ", "").strip()
            if token == CHATBOT_API_KEY:
                # Authenticated - use user/org ID for per-user rate limiting
                org_id = request.headers.get("X-Organization-ID", "default-org")
                user_id = request.headers.get("X-User-ID", "default-user")
                identifier = f"authenticated:{org_id}:{user_id}"
                logger.info(
                    f"✅ Authenticated request - Identifier: {identifier}, "
                    f"Rate limit: {RATE_LIMIT_AUTHENTICATED}"
                )
                return identifier
        except Exception as e:
            logger.warning(f"⚠️ Error processing auth header: {e}")

    # Unauthenticated - use IP address for stricter rate limiting
    ip = get_remote_address(request)
    identifier = f"public:{ip}"
    logger.info(f"🌐 Public request - Identifier: {identifier}, Rate limit: {RATE_LIMIT_PUBLIC}")
    return identifier


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


def verify_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    """
    Verify API key for authentication.
    Returns authentication info. Does not raise error if no key is provided (allows public access).
    """
    if not CHATBOT_API_KEY:
        # No API key configured - all requests are treated as public
        return {"authenticated": False, "tier": "public"}

    if not credentials:
        # No credentials provided - public access with stricter limits
        return {"authenticated": False, "tier": "public"}

    if credentials.credentials != CHATBOT_API_KEY:
        # Invalid credentials
        raise HTTPException(
            status_code=401,
            detail="Invalid API key. Public access available with rate limit of 100 requests/day.",
        )

    # Valid credentials - authenticated access
    return {"authenticated": True, "tier": "authenticated"}


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


class ChatResponse(BaseModel):
    message: str
    session_id: str
    context: List[str]
    use_case: str


@collaborate(
    name="chat_with_history",
    description="Chat with the insurance assistant using conversation history",
    response_mapping={
        "output": "$.message",
        "session_id": "$.session_id",
        "context": "$.context",
        "metadata": "$.use_case",
    },
)
def chat_with_history(
    message: str,
    session_id: Optional[str] = None,
    use_case: str = "insurance",
    conversation_history: Optional[List[dict]] = None,
) -> ChatResponse:
    """
    Process a chat message and return structured response.

    Args:
        message: User's message
        session_id: Session identifier
        use_case: Use case for system prompt
        conversation_history: Previous conversation messages

    Returns:
        ChatResponse with message, session_id, context, use_case
    """
    # Generate context
    context_fragments = generate_context(message, use_case=use_case)

    # Get assistant response
    response_text = "".join(
        stream_assistant_response(
            message, use_case=use_case, conversation_history=conversation_history
        )
    )

    # Return Pydantic model
    return ChatResponse(
        message=response_text,
        session_id=session_id or str(uuid.uuid4()),
        context=context_fragments,
        use_case=use_case,
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
            "chat": "/chat (POST)",
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
@limiter.limit(RATE_LIMIT_PUBLIC)
async def chat(request: Request, chat_request: ChatRequest, auth: dict = Depends(verify_api_key)):
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

        # Call the collaborative function
        result = chat_with_history(
            message=chat_request.message,
            session_id=session_id,
            use_case=use_case,
            conversation_history=conversation_history,
        )

        # Update session with the conversation
        sessions[session_id].messages.append({"role": "user", "content": chat_request.message})
        sessions[session_id].messages.append({"role": "assistant", "content": result.message})

        logger.info(f"✅ Response generated successfully - Length: {len(result.message)} chars")

        return result

    except Exception as e:
        logger.error(f"❌ Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}")
@limiter.limit(RATE_LIMIT_PUBLIC)
async def get_session(request: Request, session_id: str, auth: dict = Depends(verify_api_key)):
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
@limiter.limit(RATE_LIMIT_PUBLIC)
async def delete_session(request: Request, session_id: str, auth: dict = Depends(verify_api_key)):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del sessions[session_id]
    logger.info(f"🗑️ Manually deleted session: {session_id}")
    return {"message": "Session deleted"}


@app.get("/use-cases")
@limiter.limit(RATE_LIMIT_PUBLIC)
async def list_use_cases(request: Request, auth: dict = Depends(verify_api_key)):
    """Get list of available use cases"""
    try:
        use_cases = get_available_use_cases()
        return {"use_cases": use_cases}
    except Exception as e:
        return {"use_cases": ["insurance"], "error": str(e)}
