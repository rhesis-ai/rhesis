from rhesis.sdk.synthesizers.document_synthesizer import DocumentSynthesizer
from rhesis.sdk.types import Document

from .synthesizer_test_utils import cleanup_file, create_temp_document

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
            Document(
                name="insurance_policy",
                description="Insurance policy guidelines",
                path=temp_path,
            )
        ]

        synthesizer = DocumentSynthesizer(
            prompt="Generate test cases for an insurance chatbot.",
            batch_size=5,
        )

        # Generate tests from the documents
        test_set = synthesizer.generate(documents=documents, num_tests=2)

        # Verify tests were generated
        assert len(test_set.tests) > 0, "No tests generated from documents"
        assert test_set.metadata["documents_used"] == ["insurance_policy"], (
            "Document not tracked in metadata"
        )

    finally:
        cleanup_file(temp_path)


def test_document_extraction_from_content():
    """Test that documents are correctly extracted from inline content."""
    documents = [
        Document(
            name="technical_spec",
            description="API documentation",
            content=TECHNICAL_SPEC_CONTENT,
        )
    ]

    synthesizer = DocumentSynthesizer(
        prompt="Generate test cases for an API chatbot.", batch_size=5
    )

    # Generate tests from the documents
    test_set = synthesizer.generate(documents=documents, num_tests=2)

    # Verify tests were generated
    assert len(test_set.tests) > 0, "No tests generated from documents"
    assert test_set.metadata["documents_used"] == ["technical_spec"], (
        "Document not tracked in metadata"
    )


def test_mixed_document_extraction():
    """Test extraction of both file-based and inline documents."""
    temp_path = create_temp_document(INSURANCE_POLICY_CONTENT)

    try:
        documents = [
            Document(
                name="insurance_policy",
                description="Insurance policy guidelines",
                path=temp_path,
            ),
            Document(
                name="technical_spec",
                description="API documentation",
                content=TECHNICAL_SPEC_CONTENT,
            ),
        ]

        synthesizer = DocumentSynthesizer(
            prompt="Generate test cases for a multi-domain chatbot.",
            batch_size=5,
        )

        # Generate tests from both documents
        test_set = synthesizer.generate(documents=documents, num_tests=3)

        # Verify tests were generated
        assert len(test_set.tests) > 0, "No tests generated from documents"
        assert set(test_set.metadata["documents_used"]) == {"insurance_policy", "technical_spec"}, (
            "Both documents should be tracked in metadata"
        )

    finally:
        cleanup_file(temp_path)


def test_context_in_prompt():
    """Test that DocumentSynthesizer correctly uses context from documents."""
    temp_path = create_temp_document(INSURANCE_POLICY_CONTENT)

    try:
        documents = [
            Document(
                name="insurance_policy",
                description="Insurance policy guidelines",
                path=temp_path,
            ),
            Document(
                name="manual_content",
                description="Manual inline content",
                content="This is manual content for testing document extraction.",
            ),
        ]

        synthesizer = DocumentSynthesizer(
            prompt="Generate test cases for an insurance chatbot.",
            batch_size=5,
        )

        # Generate tests from documents with context
        test_set = synthesizer.generate(documents=documents, num_tests=2)

        # Verify tests were generated
        assert len(test_set.tests) > 0, "No tests generated from documents"

        # Verify tests have source metadata
        for test in test_set.tests:
            assert "metadata" in test, "Test should have metadata"
            assert "sources" in test["metadata"], "Test metadata should include sources"

    finally:
        cleanup_file(temp_path)


def test_document_extraction_error_handling():
    """Test that the synthesizer handles document extraction errors gracefully."""
    documents = [
        Document(
            name="nonexistent_file",
            description="A file that doesn't exist",
            path="/path/to/nonexistent/file.txt",
        )
    ]

    synthesizer = DocumentSynthesizer(prompt="Generate test cases for a chatbot.", batch_size=5)

    # Should raise an error when trying to extract from nonexistent file
    try:
        test_set = synthesizer.generate(documents=documents, num_tests=2)
        assert False, "Should have raised an error for nonexistent file"
    except (ValueError, FileNotFoundError):
        # Expected behavior - error raised for missing file
        pass


def test_no_documents():
    """Test that DocumentSynthesizer requires documents."""
    synthesizer = DocumentSynthesizer(
        prompt="Generate test cases for a general chatbot.", batch_size=5
    )

    # Should raise an error when no documents provided
    try:
        test_set = synthesizer.generate(documents=[], num_tests=2)
        assert False, "Should have raised an error for empty documents"
    except ValueError:
        # Expected behavior - error raised for empty documents
        pass


def test_empty_documents_list():
    """Test that DocumentSynthesizer handles empty documents list."""
    synthesizer = DocumentSynthesizer(
        prompt="Generate test cases for a general chatbot.", batch_size=5
    )

    # Should raise an error when empty documents list provided
    try:
        test_set = synthesizer.generate(documents=[], num_tests=2)
        assert False, "Should have raised an error for empty documents list"
    except ValueError:
        # Expected behavior - error raised for empty documents
        pass


def test_document_metadata_in_test_set():
    """Test that document information is included in test set metadata."""
    temp_path = create_temp_document(INSURANCE_POLICY_CONTENT)

    try:
        documents = [
            Document(
                name="insurance_policy",
                description="Insurance policy guidelines",
                path=temp_path,
            )
        ]

        synthesizer = DocumentSynthesizer(
            prompt="Generate test cases for an insurance chatbot.",
            batch_size=5,
        )

        # Generate test set
        test_set = synthesizer.generate(documents=documents, num_tests=2)

        # Check that document information is in metadata
        assert "documents_used" in test_set.metadata, (
            "Documents used not found in test set metadata"
        )
        assert "insurance_policy" in test_set.metadata["documents_used"], (
            "Document name not found in metadata"
        )

        # Check that individual test cases have source metadata
        for test in test_set.tests:
            assert "metadata" in test, "Test case missing metadata"
            assert "sources" in test["metadata"], "Test case missing sources in metadata"

    finally:
        cleanup_file(temp_path)
