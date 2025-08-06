from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import os

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.services import (
    ChatRequest, 
    GenerateTestsRequest, 
    GenerateTestsResponse,
    PromptRequest,
    TextResponse,
    DocumentUploadResponse
)
from rhesis.backend.app.services.github import read_repo_contents
from rhesis.backend.app.services.generation import generate_tests
from rhesis.backend.app.services.gemini_client import (
    create_chat_completion,
    get_chat_response,
    get_json_response,
)
from rhesis.backend.app.services.document_handler import DocumentHandler

router = APIRouter(
    prefix="/services",
    tags=["services"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(require_current_user_or_token)],
)


@router.get("/github/contents")
async def get_github_contents(repo_url: str):
    """
    Get the contents of a GitHub repository.

    Args:
        repo_url: The URL of the GitHub repository to read

    Returns:
        str: The contents of the repository
    """
    print(f"Getting GitHub contents for {repo_url}")
    try:
        contents = read_repo_contents(repo_url)
        return contents
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/openai/json")
async def get_ai_json_response(prompt_request: PromptRequest):
    """
    Get a JSON response from OpenAI API.

    Args:
        prompt_request: The request containing the prompt to send to OpenAI

    Returns:
        dict: The JSON response from OpenAI
    """
    try:
        if prompt_request.stream:

            async def generate():
                async for chunk in get_json_response(prompt_request.prompt, stream=True):
                    yield f"data: {chunk}\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")

        return get_json_response(prompt_request.prompt)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/openai/chat")
async def get_ai_chat_response(chat_request: ChatRequest):
    """
    Get a response from OpenAI API using a chat messages array.

    Args:
        chat_request: The request containing the messages array and response format

    Returns:
        dict: The response from OpenAI (JSON or text based on response_format)
    """
    try:
        if chat_request.stream:
            return StreamingResponse(
                get_chat_response(
                    messages=[msg.dict() for msg in chat_request.messages],
                    response_format=chat_request.response_format,
                    stream=True,
                ),
                media_type="text/event-stream",
            )

        return get_chat_response(
            messages=[msg.dict() for msg in chat_request.messages],
            response_format=chat_request.response_format,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/chat/completions")
async def create_chat_completion_endpoint(request: dict):
    """
    OpenAI-compatible chat completions endpoint.
    Accepts requests in the standard OpenAI chat completion format.

    Args:
        request: The complete chat completion request body matching OpenAI's format

    Returns:
        dict: The unmodified OpenAI API response
    """
    try:
        response = create_chat_completion(request)

        if request.get("stream", False):
            return StreamingResponse(response, media_type="text/event-stream")

        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generate/tests", response_model=GenerateTestsResponse)
async def generate_tests_endpoint(
    request: GenerateTestsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Generate test cases using the prompt synthesizer.

    Args:
        request: The request containing the prompt and number of tests
        db: Database session
        current_user: Current authenticated user

    Returns:
        GenerateTestsResponse: The generated test cases
    """
    try:
        prompt = request.prompt
        num_tests = request.num_tests
        
        if not prompt:
            raise HTTPException(status_code=400, detail="prompt is required")
            
        test_cases = await generate_tests(db, current_user, prompt, num_tests)
        return {"tests": test_cases}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generate/text", response_model=TextResponse)
async def generate_text(prompt_request: PromptRequest):
    """
    Generate raw text from an arbitrary prompt.

    Args:
        prompt_request: The request containing the prompt and stream flag

    Returns:
        TextResponse: The raw text response from the model
    """
    try:
        # Create a simple message array with the prompt
        messages = [
            {"role": "user", "content": prompt_request.prompt}
        ]
        
        if prompt_request.stream:
            # Handle streaming response
            async def generate():
                response_stream = get_chat_response(
                    messages=messages,
                    response_format="text",  # Explicitly request text format
                    stream=True
                )
                
                async for chunk in response_stream:
                    if chunk["choices"][0]["delta"]["content"]:
                        yield f"data: {chunk['choices'][0]['delta']['content']}\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")
        
        # Non-streaming response
        response = get_chat_response(
            messages=messages,
            response_format="text",  # Explicitly request text format
            stream=False
        )
        
        return TextResponse(text=response)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(document: UploadFile = File(...)):
    """
    Upload a document to temporary storage.

    The document will be saved in a temporary directory with a UUID prefix to avoid naming conflicts.
    Maximum document size is 5MB.

    Args:
        document: The document to upload (multipart/form-data)

    Returns:
        DocumentUploadResponse: Contains the temporary filename identifier
    
    Note: 
        The document will be saved in the temporary directory and should be cleaned up after use.
        Use the returned filename to reference this document in other endpoints.
    """
    handler = DocumentHandler()
    filename = await handler.save_document(document)
    return {"filename": filename}