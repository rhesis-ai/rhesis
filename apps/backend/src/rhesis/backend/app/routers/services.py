from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.dependencies import get_form_document_processor, get_json_document_processor, DocumentProcessor
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.services import (
    ChatRequest, 
    GenerateTestsRequest, 
    GenerateTestsResponse,
    PromptRequest,
    TextResponse
)
from rhesis.backend.app.services.github import read_repo_contents
from rhesis.backend.app.services.generation import generate_tests
from rhesis.backend.app.services.gemini_client import (
    create_chat_completion,
    get_chat_response,
    get_json_response,
)

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


@router.post("/generate/tests/json", response_model=GenerateTestsResponse)
async def generate_tests_json_endpoint(
    request: GenerateTestsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Generate insurance test cases using either a prompt alone or with additional content.

    This endpoint supports two modes:
    1. Prompt-only: Generate tests based solely on the prompt
    2. Content-based: Generate tests using the prompt and provided document content

    Args:
        request: The request containing:
            - prompt: Description of test scenarios to generate
            - num_tests: Number of test cases to generate (default: 5)
            - documents: Optional list of documents with content (for content-based generation)
        db: Database session
        current_user: Current authenticated user

    Returns:
        GenerateTestsResponse: The generated test cases with prompts and expected behaviors
        
    Example 1 - Prompt-only generation:
        ```json
        {
          "prompt": "Generate test cases for verifying auto insurance coverage limits",
          "num_tests": 5
        }
        ```

    Example 2 - Content-based generation:
        ```json
        {
          "prompt": "Generate test cases for handling life insurance beneficiary changes",
          "num_tests": 5,
          "documents": [
            {
              "name": "beneficiary_policy",
              "description": "Life insurance beneficiary change procedures",
              "content": "1. Policy holders may change beneficiaries at any time..."
            }
          ]
        }
        ```

    """
    if not request.prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    
    # Get document processor for JSON documents (might be None for prompt-only)
    document_processor = await get_json_document_processor(request.documents)
    
    # Use the document processor with automatic cleanup
    async with document_processor as processed_documents:
        test_cases = await generate_tests(
            db, 
            current_user, 
            request.prompt, 
            request.num_tests, 
            processed_documents
        )
        return {"tests": test_cases}


@router.post("/generate/tests/files", response_model=GenerateTestsResponse)
async def generate_tests_files_endpoint(
    prompt: str = Form(...),
    num_tests: Optional[int] = Form(5),
    files: List[UploadFile] = File(...),  # Make files required
    document_processor: DocumentProcessor = Depends(get_form_document_processor),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Generate test cases from uploaded documents.

    This endpoint is specifically designed for generating tests based on actual documents that you upload. Use this when you have existing files (PDFs, docs, etc.) that contain the content you want to base your tests on.

    Args:
        prompt: The generation prompt describing what kind of tests to generate
        num_tests: Number of test cases to generate (default: 5)
        files: Documents to use as context (required, supports various formats like PDF, DOCX, etc.)
        db: Database session
        current_user: Current authenticated user

    Returns:
        GenerateTestsResponse: The generated test cases with prompts and expected behaviors
        
    Example usage:
        Upload documents for test generation:
        ```
        curl -X POST "/generate/tests/files" \
          -F "prompt=Generate test cases to verify compliance with our auto insurance policy" \
          -F "num_tests=3" \
          -F "files=@auto_insurance_policy.pdf" \
          -F "files=@claims_procedures.docx"
        ```
    """
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    
    if not files:
        raise HTTPException(status_code=400, detail="at least one file is required")
    
    # Use the document processor with automatic cleanup
    async with document_processor as processed_documents:
        test_cases = await generate_tests(
            db, 
            current_user, 
            prompt, 
            num_tests, 
            processed_documents
        )
        return {"tests": test_cases}


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
