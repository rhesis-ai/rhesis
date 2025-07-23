from rhesis.sdk.synthesizers.prompt_synthesizer import PromptSynthesizer
from test_utils import create_temp_document, cleanup_file

INSURANCE_CONTENT = """
Insurance Policy Guidelines

1. Coverage Limits: Basic - $100k, Premium - $500k, Max - $1M
2. Pre-existing Conditions must be declared.
3. Claims must be submitted within 30 days.
4. Exclusions: Fraud, Intentional damage, War, Terrorism.
"""



def test_with_documents():
    """Test PromptSynthesizer with both file and inline documents."""
    temp_path = create_temp_document(INSURANCE_CONTENT)

    documents = [
        {
            "name": "insurance_policy",
            "description": "Insurance policy details",
            "path": temp_path
        },
        {
            "name": "manual_content",
            "description": "Manual inline content",
            "content": "Manual override for chatbot insurance questions."
        }
    ]

    try:
        synthesizer = PromptSynthesizer(
            prompt="Generate test cases for an insurance chatbot.",
            documents=documents,
            batch_size=5
        )

        assert synthesizer.extracted_documents, "No documents extracted"

        test_set = synthesizer.generate(num_tests=3)
        assert len(test_set.tests) == 3, "Incorrect number of tests generated"

    finally:
        cleanup_file(temp_path)


def test_without_documents():
    """Test PromptSynthesizer without any documents."""
    synthesizer = PromptSynthesizer(
        prompt="Generate test cases for a general chatbot.",
        batch_size=5
    )

    test_set = synthesizer.generate(num_tests=2)
    assert len(test_set.tests) == 2, "Failed to generate tests without documents"
