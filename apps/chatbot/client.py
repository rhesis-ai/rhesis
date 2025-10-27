from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Dict, List
import uuid
import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from endpoint import stream_assistant_response, generate_context
from notifications import send_rate_limit_alert

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
    
    if auth_header and CHATBOT_API_KEY:
        try:
            token = auth_header.replace("Bearer ", "").strip()
            if token == CHATBOT_API_KEY:
                # Authenticated - use user/org ID for per-user rate limiting
                org_id = request.headers.get("X-Organization-ID", "default-org")
                user_id = request.headers.get("X-User-ID", "default-user")
                return f"authenticated:{org_id}:{user_id}"
        except:
            pass
    
    # Unauthenticated - use IP address for stricter rate limiting
    return f"public:{get_remote_address(request)}"

# Initialize rate limiter with custom key function
limiter = Limiter(key_func=get_rate_limit_identifier)

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
            detail="Invalid API key. Public access available with rate limit of 100 requests/day."
        )
    
    # Valid credentials - authenticated access
    return {"authenticated": True, "tier": "authenticated"}

app = FastAPI(
    title="Rhesis Insurance Chatbot API",
    description="Default insurance chatbot (Rosalind) for new user onboarding. Provides instant access to explore Rhesis AI capabilities.",
    version="1.0.0"
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
    
    # Send email notification (async, non-blocking)
    try:
        send_rate_limit_alert(request, identifier, rate_limit_type, rate_limit_value)
    except Exception as e:
        # Log but don't fail the response
        print(f"⚠️ Error sending rate limit alert: {e}")
    
    # Return the standard rate limit exceeded response (not awaited - it returns a Response object)
    return _rate_limit_exceeded_handler(request, exc)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_exceeded_handler)

# Store chat sessions
sessions: Dict[str, List[dict]] = {}

def get_available_use_cases() -> List[str]:
    """Get list of available use cases from use_cases directory."""
    try:
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        use_cases_dir = os.path.join(current_dir, "use_cases")
        
        use_cases = []
        for filename in os.listdir(use_cases_dir):
            if filename.endswith('.md'):
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

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and load balancer."""
    return {
        "status": "healthy",
        "service": "rhesis-insurance-chatbot",
        "version": "1.0.0"
    }

@app.get("/")
async def root(request: Request, auth: dict = Depends(verify_api_key)):
    """Root endpoint with API information."""
    return {
        "service": "Rhesis Insurance Chatbot API",
        "description": "Chat with Rosalind, your insurance expert",
        "authentication": {
            "status": "authenticated" if auth["authenticated"] else "public",
            "tier": auth["tier"]
        },
        "endpoints": {
            "chat": "/chat (POST)",
            "health": "/health (GET)",
            "use_cases": "/use-cases (GET)",
            "sessions": "/sessions/{session_id} (GET, DELETE)"
        },
        "rate_limits": {
            "authenticated": f"{TOTAL_RATE_LIMIT_AUTHENTICATED} requests per day per user",
            "public": f"{TOTAL_RATE_LIMIT_PUBLIC} requests per day per IP address",
            "current_tier": auth["tier"]
        }
    }

@app.post("/chat", response_model=ChatResponse)
@limiter.limit(RATE_LIMIT_PUBLIC)
async def chat(
    request: Request, 
    chat_request: ChatRequest,
    auth: dict = Depends(verify_api_key)
):
    try:
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
            sessions[session_id] = []
        
        # Add user message to session history
        sessions[session_id].append({
            "role": "user",
            "content": chat_request.message
        })
        
        # Generate context fragments for the response with the specified use case
        context_fragments = generate_context(chat_request.message, use_case=use_case)
        
        # Get response from assistant with the specified use case
        response = "".join(stream_assistant_response(chat_request.message, use_case=use_case))
        
        # Add assistant response to session history
        sessions[session_id].append({
            "role": "assistant",
            "content": response
        })
        
        return ChatResponse(
            message=response,
            session_id=session_id,
            context=context_fragments,
            use_case=use_case
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}")
@limiter.limit(RATE_LIMIT_PUBLIC)
async def get_session(request: Request, session_id: str, auth: dict = Depends(verify_api_key)):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"messages": sessions[session_id]}

@app.delete("/sessions/{session_id}")
@limiter.limit(RATE_LIMIT_PUBLIC)
async def delete_session(request: Request, session_id: str, auth: dict = Depends(verify_api_key)):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del sessions[session_id]
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
