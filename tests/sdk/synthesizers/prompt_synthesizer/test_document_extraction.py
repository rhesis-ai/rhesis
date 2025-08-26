from test_utils import create_temp_document, cleanup_file
from rhesis.sdk.synthesizers.prompt_synthesizer import PromptSynthesizer



# Test document contents
INSURANCE_POLICY_CONTENT = """
Insurance Policy Guidelines

1. Coverage Limits:
   - Basic coverage: $100,000
   - Premium coverage: $500,000
   - Maximum coverage: $1,000,000

2. Pre-existing Conditions:
   - Must be declared at time of application
   - May affect premium rates
   - Coverage may be limited for certain conditions

3. Claims Process:
   - Submit within 30 days of incident
   - Provide all required documentation
   - Claims are processed within 14 business days

4. Exclusions:
   - Intentional damage
   - Fraudulent claims
   - Acts of war or terrorism
"""

TECHNICAL_SPEC_CONTENT = """
API Documentation

Endpoints:
- GET /api/users - Retrieve user list
- POST /api/users - Create new user
- PUT /api/users/{id} - Update user
- DELETE /api/users/{id} - Delete user

Authentication:
- Bearer token required
- Token expires in 24 hours
- Rate limit: 100 requests per minute

Error Codes:
- 400: Bad Request
- 401: Unauthorized
- 404: Not Found
- 500: Internal Server Error
"""


def test_document_extraction_from_file():
    """Test that documents are correctly extracted from file paths."""
    temp_path = create_temp_document(INSURANCE_POLICY_CONTENT)

    try:
        documents = [
            {
                "name": "insurance_policy",
                "description": "Insurance policy guidelines",
                "path": temp_path
            }
        ]

        synthesizer = PromptSynthesizer(
            prompt="Generate test cases for an insurance chatbot.",
            documents=documents,
            batch_size=5
        )

        # Verify document was extracted
        assert synthesizer.extracted_documents, "No documents extracted"
        assert "insurance_policy" in synthesizer.extracted_documents, "Document not found in extracted documents"

        # Check content
        content = synthesizer.extracted_documents["insurance_policy"]
        assert "Coverage Limits" in content, "Insurance content not properly extracted"
        assert "Pre-existing Conditions" in content, "Insurance content not properly extracted"
        assert "Claims Process" in content, "Insurance content not properly extracted"

    finally:
        cleanup_file(temp_path)


def test_document_extraction_from_content():
    """Test that documents are correctly extracted from inline content."""
    documents = [
        {
            "name": "technical_spec",
            "description": "API documentation",
            "content": TECHNICAL_SPEC_CONTENT
        }
    ]

    synthesizer = PromptSynthesizer(
        prompt="Generate test cases for an API chatbot.",
        documents=documents,
        batch_size=5
    )

    # Verify document was extracted
    assert synthesizer.extracted_documents, "No documents extracted"
    assert "technical_spec" in synthesizer.extracted_documents, "Document not found in extracted documents"

    # Check content
    content = synthesizer.extracted_documents["technical_spec"]
    assert "API Documentation" in content, "Technical content not properly extracted"
    assert "Endpoints:" in content, "Technical content not properly extracted"
    assert "Authentication:" in content, "Technical content not properly extracted"


def test_mixed_document_extraction():
    """Test extraction of both file-based and inline documents."""
    temp_path = create_temp_document(INSURANCE_POLICY_CONTENT)

    try:
        documents = [
            {
                "name": "insurance_policy",
                "description": "Insurance policy guidelines",
                "path": temp_path
            },
            {
                "name": "technical_spec",
                "description": "API documentation",
                "content": TECHNICAL_SPEC_CONTENT
            }
        ]

        synthesizer = PromptSynthesizer(
            prompt="Generate test cases for a multi-domain chatbot.",
            documents=documents,
            batch_size=5
        )

        # Verify both documents were extracted
        assert len(synthesizer.extracted_documents) == 2, "Expected 2 documents to be extracted"
        assert "insurance_policy" in synthesizer.extracted_documents, "Insurance document not extracted"
        assert "technical_spec" in synthesizer.extracted_documents, "Technical document not extracted"

    finally:
        cleanup_file(temp_path)


def test_context_in_prompt():
    """Test that context is correctly included in the prompt template."""
    temp_path = create_temp_document(INSURANCE_POLICY_CONTENT)

    try:
        documents = [
            {
                "name": "insurance_policy",
                "description": "Insurance policy guidelines",
                "path": temp_path
            },
            {
                "name": "manual_content",
                "description": "Manual inline content",
                "content": "This is manual content for testing document extraction."
            }
        ]

        synthesizer = PromptSynthesizer(
            prompt="Generate test cases for an insurance chatbot.",
            documents=documents,
            batch_size=5
        )

        # Verify documents were extracted
        assert synthesizer.extracted_documents, "No documents extracted"
        assert "insurance_policy" in synthesizer.extracted_documents, "File document not extracted"
        assert "manual_content" in synthesizer.extracted_documents, "Manual content not extracted"

        # Check that the extracted content contains expected text
        insurance_content = synthesizer.extracted_documents["insurance_policy"]
        manual_content = synthesizer.extracted_documents["manual_content"]

        assert "Coverage Limits" in insurance_content, "Insurance content not properly extracted"
        assert "manual content for testing" in manual_content, "Manual content not properly extracted"

        # Create context the same way the synthesizer does
        context = "\n\n".join([
            f"Document '{name}':\n{content}"
            for name, content in synthesizer.extracted_documents.items()
        ])

        # Test prompt rendering with documents
        formatted_prompt = synthesizer.system_prompt.render(
            generation_prompt="Generate test cases for an insurance chatbot.",
            num_tests=3,
            context=context
        )

        # Verify context is included in the prompt
        assert "Context" in formatted_prompt, "Context section not found in prompt"
        assert "insurance_policy" in formatted_prompt, "Document name not found in prompt"
        assert "Coverage Limits" in formatted_prompt, "Document content not found in prompt"
        assert "manual content for testing" in formatted_prompt, "Manual content not found in prompt"

    finally:
        cleanup_file(temp_path)


def test_document_extraction_error_handling():
    """Test that the synthesizer handles document extraction errors gracefully."""
    documents = [
        {
            "name": "nonexistent_file",
            "description": "A file that doesn't exist",
            "path": "/path/to/nonexistent/file.txt"
        }
    ]

    # This should not raise an exception, but should log a warning
    synthesizer = PromptSynthesizer(
        prompt="Generate test cases for a chatbot.",
        documents=documents,
        batch_size=5
    )

    # Should have empty extracted documents due to error
    assert not synthesizer.extracted_documents, "Should have empty extracted documents when file doesn't exist"


def test_no_documents():
    """Test that synthesizer works correctly without any documents."""
    synthesizer = PromptSynthesizer(
        prompt="Generate test cases for a general chatbot.",
        documents=None,
        batch_size=5
    )

    # Should have empty extracted documents
    assert not synthesizer.extracted_documents, "Should have empty extracted documents when no documents provided"


def test_empty_documents_list():
    """Test that synthesizer works correctly with empty documents list."""
    synthesizer = PromptSynthesizer(
        prompt="Generate test cases for a general chatbot.",
        documents=[],
        batch_size=5
    )

    # Should have empty extracted documents
    assert not synthesizer.extracted_documents, "Should have empty extracted documents when documents list is empty"


def test_document_metadata_in_test_set():
    """Test that document information is included in test set metadata."""
    temp_path = create_temp_document(INSURANCE_POLICY_CONTENT)

    try:
        documents = [
            {
                "name": "insurance_policy",
                "description": "Insurance policy guidelines",
                "path": temp_path
            }
        ]

        synthesizer = PromptSynthesizer(
            prompt="Generate test cases for an insurance chatbot.",
            documents=documents,
            batch_size=5
        )

        # Generate test set
        test_set = synthesizer.generate(num_tests=2)

        # Check that document information is in metadata
        assert "documents_used" in test_set.metadata, "Documents used not found in test set metadata"
        assert "insurance_policy" in test_set.metadata["documents_used"], "Document name not found in metadata"

        # Check that individual test cases also have document metadata
        for test in test_set.tests:
            assert "metadata" in test, "Test case missing metadata"
            assert "documents_used" in test["metadata"], "Test case missing documents_used metadata"
            assert "insurance_policy" in test["metadata"]["documents_used"], "Document name not found in test case metadata"

    finally:
        cleanup_file(temp_path)
