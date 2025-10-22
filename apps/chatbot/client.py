from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import uuid
import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from endpoint import stream_assistant_response, generate_context

# Get rate limit from environment variable, default to 1000 requests/hour
RATE_LIMIT_PER_HOUR = os.getenv("CHATBOT_RATE_LIMIT", "1000")
RATE_LIMIT = f"{RATE_LIMIT_PER_HOUR}/hour"

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Rhesis Insurance Chatbot API",
    description="Default insurance chatbot (Rosalind) for new user onboarding. Provides instant access to explore Rhesis AI capabilities.",
    version="1.0.0"
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Store chat sessions
sessions: Dict[str, List[dict]] = {}

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
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Rhesis Insurance Chatbot API",
        "description": "Chat with Rosalind, your insurance expert",
        "endpoints": {
            "chat": "/chat (POST)",
            "health": "/health (GET)",
            "use_cases": "/use-cases (GET)",
            "sessions": "/sessions/{session_id} (GET, DELETE)"
        },
        "rate_limits": {
            "requests_per_hour": int(RATE_LIMIT_PER_HOUR),
            "note": "Configurable via CHATBOT_RATE_LIMIT environment variable"
        }
    }

@app.post("/chat", response_model=ChatResponse)
@limiter.limit(RATE_LIMIT)
async def chat(request: Request, chat_request: ChatRequest):
    try:
        # Get or create session_id
        session_id = chat_request.session_id or str(uuid.uuid4())
        
        # Use the provided use_case or default to insurance
        use_case = chat_request.use_case or "insurance"
        
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
async def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"messages": sessions[session_id]}

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del sessions[session_id]
    return {"message": "Session deleted"}

@app.get("/use-cases")
async def get_available_use_cases():
    """Get list of available use cases"""
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    use_cases_dir = os.path.join(current_dir, "use_cases")
    
    try:
        use_cases = []
        for filename in os.listdir(use_cases_dir):
            if filename.endswith('.md'):
                use_case_name = filename[:-3]  # Remove .md extension
                use_cases.append(use_case_name)
        return {"use_cases": sorted(use_cases)}
    except Exception as e:
        return {"use_cases": ["insurance"], "error": str(e)}
