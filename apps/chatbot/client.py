from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
import uuid
from .endpoint import stream_assistant_response, generate_context

app = FastAPI(
    title="Insurance Assistant API",
    description="API for interacting with the insurance chatbot",
    version="1.0.0"
)

# Store chat sessions
sessions: Dict[str, List[dict]] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    message: str
    session_id: str
    context: List[str]

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Get or create session_id
        session_id = request.session_id or str(uuid.uuid4())
        
        # Initialize session if it doesn't exist
        if session_id not in sessions:
            sessions[session_id] = []
        
        # Add user message to session history
        sessions[session_id].append({
            "role": "user",
            "content": request.message
        })
        
        # Generate context fragments for the response
        context_fragments = generate_context(request.message)
        
        # Get response from assistant
        response = "".join(stream_assistant_response(request.message))
        
        # Add assistant response to session history
        sessions[session_id].append({
            "role": "assistant",
            "content": response
        })
        
        return ChatResponse(
            message=response,
            session_id=session_id,
            context=context_fragments
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
