from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List
import uuid
from endpoint import stream_assistant_response, generate_context

app = FastAPI(
    title="AI Assistant API",
    description="API for interacting with AI assistants across different domains (insurance, finance, legal, health)",
    version="1.0.0"
)

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

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Get or create session_id
        session_id = request.session_id or str(uuid.uuid4())
        
        # Use the provided use_case or default to insurance
        use_case = request.use_case or "insurance"
        
        # Initialize session if it doesn't exist
        if session_id not in sessions:
            sessions[session_id] = []
        
        # Add user message to session history
        sessions[session_id].append({
            "role": "user",
            "content": request.message
        })
        
        # Generate context fragments for the response with the specified use case
        context_fragments = generate_context(request.message, use_case=use_case)
        
        # Get response from assistant with the specified use case
        response = "".join(stream_assistant_response(request.message, use_case=use_case))
        
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
