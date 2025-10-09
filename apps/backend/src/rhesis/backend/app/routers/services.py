from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.services import (
    ChatRequest,
    DocumentUploadResponse,
    ExtractDocumentRequest,
    ExtractDocumentResponse,
    GenerateContentRequest,
    GenerateTestsRequest,
    GenerateTestsResponse,
    PromptRequest,
    TestConfigRequest,
    TestConfigResponse,
    TextResponse,
)
from rhesis.backend.app.services.document_handler import DocumentHandler
from rhesis.backend.app.services.gemini_client import (
    create_chat_completion,
    get_chat_response,
    get_json_response,
)
from rhesis.backend.app.services.generation import generate_tests
from rhesis.backend.app.services.github import read_repo_contents
from rhesis.backend.app.services.test_config_generator import TestConfigGeneratorService
from rhesis.backend.logging import logger
from rhesis.sdk.services.extractor import DocumentExtractor
from rhesis.sdk.types import Document

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
    logger.info(f"Getting GitHub contents for {repo_url}")
    try:
        contents = read_repo_contents(repo_url)
        return contents
    except Exception as e:
        logger.error(f"Failed to get GitHub contents for {repo_url}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to retrieve repository contents")


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


@router.post("/generate/content")
async def generate_content_endpoint(request: GenerateContentRequest):
    """
    Generate text using LLM with optional OpenAI schema validation.

    Args:
        request: Contains prompt and optional OpenAI schema for structured output

    Returns:
        str or dict: Raw text if no schema, validated dict if schema provided
    """
    try:
        from rhesis.sdk.models.providers.gemini import GeminiLLM

        prompt = request.prompt
        schema = request.schema_

        model = GeminiLLM()
        response = model.generate(prompt, schema=schema)

        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generate/tests", response_model=GenerateTestsResponse)
async def generate_tests_endpoint(
    request: GenerateTestsRequest,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    Generate test cases using the prompt synthesizer.

    Args:
        request: The request containing the prompt, number of tests, and optional documents
            - Each document may contain:
                - `name` (str): Identifier for the document.
                - `description` (str): Short description of its purpose.
                - `path` (str): Path to the uploaded document file.
                - `content` (str, optional): Raw content of the document.
                ⚠️ If both `path` and `content` are provided in a document, `content` will override
                 `path`: the file at `path` will not be read or used.
        db: Database session
        current_user: Current authenticated user

    Returns:
        GenerateTestsResponse: The generated test cases
    """
    try:
        prompt = request.prompt
        num_tests = request.num_tests
        documents = request.documents

        if not prompt:
            raise HTTPException(status_code=400, detail="prompt is required")

        # Convert Pydantic models to Document objects
        documents_sdk = [Document(**doc.dict()) for doc in documents] if documents else None

        test_cases = await generate_tests(db, current_user, prompt, num_tests, documents_sdk)
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
        messages = [{"role": "user", "content": prompt_request.prompt}]

        if prompt_request.stream:
            # Handle streaming response
            async def generate():
                response_stream = get_chat_response(
                    messages=messages,
                    response_format="text",  # Explicitly request text format
                    stream=True,
                )

                async for chunk in response_stream:
                    if chunk["choices"][0]["delta"]["content"]:
                        yield f"data: {chunk['choices'][0]['delta']['content']}\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")

        # Non-streaming response
        response = get_chat_response(
            messages=messages,
            response_format="text",  # Explicitly request text format
            stream=False,
        )

        return TextResponse(text=response)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    document: UploadFile = File(...), tenant_context=Depends(get_tenant_context)
):
    """
    Upload a document to persistent storage.

    The document will be saved to the configured storage backend (GCS or local filesystem)
    with a multi-tenant path structure.
    Maximum document size is 5MB.

    Args:
        document: The document to upload (multipart/form-data)
        tenant_context: Tenant context containing organization_id and user_id

    Returns:
        DocumentUploadResponse: Contains the full path to the uploaded document
    """
    organization_id, user_id = tenant_context
    handler = DocumentHandler()

    # Use user_id as source_id for now (can be changed to a proper source ID later)
    path, metadata = await handler.save_document(document, organization_id, user_id)
    return {"path": path}


@router.post("/documents/extract", response_model=ExtractDocumentResponse)
async def extract_document_content(request: ExtractDocumentRequest) -> ExtractDocumentResponse:
    """
    Extract text content from an uploaded document.

    Uses the SDK's DocumentExtractor to extract text from various document formats:
    - PDF (.pdf)
    - Microsoft Office formats (.docx, .xlsx, .pptx)
    - Markdown (.md)
    - AsciiDoc (.adoc)
    - HTML/XHTML (.html, .xhtml)
    - CSV (.csv)
    - Plain text (.txt)
    - And more...

    Args:
        request: ExtractDocumentRequest containing the path to the uploaded document

    Returns:
        ExtractDocumentResponse containing the extracted text content and detected format
    """
    try:
        # Initialize extractor
        extractor = DocumentExtractor()

        # Get file extension to determine format
        file_extension = Path(request.path).suffix.lower()

        # Check if format is supported
        if file_extension not in extractor.supported_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {file_extension}. "
                f"Supported formats: {', '.join(extractor.supported_extensions)}",
            )

        # Prepare document for extraction
        document = Document(name="document", description="Uploaded document", path=request.path)

        # Extract content
        extracted_texts = extractor.extract([document])

        # Get the extracted content (there's only one document)
        content = next(iter(extracted_texts.values()))

        return ExtractDocumentResponse(
            content=content,
            format=file_extension.lstrip("."),  # Remove the leading dot
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail="Document not found. Please check the file path."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract document content: {str(e)}")


@router.post("/generate/test_config", response_model=TestConfigResponse)
async def generate_test_config(request: TestConfigRequest):
    """
    Generate test configuration JSON based on user description.

    This endpoint analyzes a user-provided description and generates a configuration
    JSON containing relevant behaviors, topics, test categories, and test scenarios
    from predefined lists.

    Args:
        request: Contains prompt (description) for test configuration generation and
            optional sample_size (default: 5, max: 20) for number of items per category

    Returns:
        TestConfigResponse: JSON containing selected behaviors, topics, test categories,
            and scenarios, each with name and description fields
    """
    try:
        logger.info(
            f"Test config generation request for prompt: {request.prompt[:100]}... "
            f"with sample_size: {request.sample_size}"
        )
        service = TestConfigGeneratorService()
        result = service.generate_config(request.prompt, request.sample_size)
        logger.info("Test config generation successful")
        return result
    except ValueError as e:
        logger.warning(f"Invalid request for test config generation: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid request parameters")
    except RuntimeError as e:
        logger.error(f"Test config generation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate test configuration")
    except Exception as e:
        logger.error(f"Unexpected error in test config generation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
