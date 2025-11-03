"""Tests for analysis tools (AnalyzeTool and ExtractTool)."""

import pytest
from rhesis.penelope.tools.analysis import AnalyzeTool, ExtractTool
from rhesis.penelope.tools.base import ToolResult


def test_analyze_tool_properties():
    """Test AnalyzeTool properties."""
    tool = AnalyzeTool()

    assert tool.name == "analyze_response"
    assert "analyze" in tool.description.lower()


def test_analyze_tool_execute_basic():
    """Test AnalyzeTool basic execution."""
    tool = AnalyzeTool()

    result = tool.execute(
        response_text="Yes, we can help with your refund request.",
        analysis_focus="Check tone and helpfulness",
    )

    assert isinstance(result, ToolResult)
    assert result.success is True
    assert "findings" in result.output
    assert "response_length" in result.output
    assert isinstance(result.output["findings"], list)


def test_analyze_tool_execute_with_context():
    """Test AnalyzeTool execution with context."""
    tool = AnalyzeTool()

    result = tool.execute(
        response_text="Yes, we can help with your refund request.",
        analysis_focus="Check tone",
        context="Previous message was about returns",
    )

    assert result.success is True
    assert result.output["context_provided"] is True


def test_analyze_tool_detects_positive_tone():
    """Test AnalyzeTool detects positive tone."""
    tool = AnalyzeTool()

    result = tool.execute(
        response_text="Yes, I'm happy to help! Certainly we can assist you.",
        analysis_focus="Check tone",
    )

    assert result.success is True
    findings_text = " ".join(result.output["findings"])
    assert "positive" in findings_text.lower() or "helpful" in findings_text.lower()


def test_analyze_tool_detects_negative_tone():
    """Test AnalyzeTool detects negative tone."""
    tool = AnalyzeTool()

    result = tool.execute(
        response_text="No, unfortunately we cannot help. Sorry, we are unable to assist.",
        analysis_focus="Check tone",
    )

    assert result.success is True
    findings_text = " ".join(result.output["findings"])
    assert "negative" in findings_text.lower() or "limiting" in findings_text.lower()


def test_analyze_tool_detects_structure():
    """Test AnalyzeTool detects response structure."""
    tool = AnalyzeTool()

    result = tool.execute(
        response_text="Here are the options:\n- Option 1\n- Option 2\nCall us at 123-456-7890",
        analysis_focus="Check structure",
    )

    assert result.success is True
    findings_text = " ".join(result.output["findings"])
    assert "bullet" in findings_text.lower() or "list" in findings_text.lower()
    assert "numerical" in findings_text.lower() or "numbers" in findings_text.lower()


def test_analyze_tool_detects_policy_language():
    """Test AnalyzeTool detects policy-related content."""
    tool = AnalyzeTool()

    result = tool.execute(
        response_text="Our policy states that refunds are processed within 30 days.",
        analysis_focus="Check for policy information",
    )

    assert result.success is True
    findings_text = " ".join(result.output["findings"])
    assert "policy" in findings_text.lower()


def test_analyze_tool_word_count():
    """Test AnalyzeTool calculates word count."""
    tool = AnalyzeTool()

    result = tool.execute(
        response_text="One two three four five",
        analysis_focus="Count words",
    )

    assert result.success is True
    assert result.output["response_length"] == 5


def test_extract_tool_properties():
    """Test ExtractTool properties."""
    tool = ExtractTool()

    assert tool.name == "extract_information"
    assert "extract" in tool.description.lower()


def test_extract_tool_execute_basic():
    """Test ExtractTool basic execution."""
    tool = ExtractTool()

    result = tool.execute(
        response_text="Our policy allows refunds within 30 days.",
        extraction_target="refund timeframe",
    )

    assert isinstance(result, ToolResult)
    assert result.success is True
    assert "extraction_target" in result.metadata


def test_extract_tool_extract_dates():
    """Test ExtractTool extracts dates."""
    tool = ExtractTool()

    result = tool.execute(
        response_text="The deadline is 12/31/2024 and the start date was 01-15-2024.",
        extraction_target="dates",
    )

    assert result.success is True
    assert "dates" in result.output
    assert len(result.output["dates"]) == 2


def test_extract_tool_extract_numbers():
    """Test ExtractTool extracts numbers when relevant."""
    tool = ExtractTool()

    result = tool.execute(
        response_text="You have 30 days to return items. Limit of 5 returns per year.",
        extraction_target="numbers and counts",
    )

    assert result.success is True
    assert "numbers" in result.output


def test_extract_tool_extract_emails():
    """Test ExtractTool extracts email addresses."""
    tool = ExtractTool()

    result = tool.execute(
        response_text="Contact us at support@example.com or sales@example.com",
        extraction_target="contact information",
    )

    assert result.success is True
    assert "emails" in result.output
    assert len(result.output["emails"]) == 2
    assert "support@example.com" in result.output["emails"]


def test_extract_tool_extract_phones():
    """Test ExtractTool extracts phone numbers."""
    tool = ExtractTool()

    result = tool.execute(
        response_text="Call us at 123-456-7890 or 555.123.4567",
        extraction_target="phone numbers",
    )

    assert result.success is True
    assert "phones" in result.output
    assert len(result.output["phones"]) == 2


def test_extract_tool_relevant_sentences():
    """Test ExtractTool extracts relevant sentences."""
    tool = ExtractTool()

    result = tool.execute(
        response_text="We offer many services. Our refund policy is generous. Contact us anytime.",
        extraction_target="refund policy",
    )

    assert result.success is True
    assert "relevant_content" in result.output
    # Should find the sentence containing "refund" and "policy"
    relevant = result.output["relevant_content"]
    assert any("refund policy" in s.lower() for s in relevant)


def test_extract_tool_no_matches():
    """Test ExtractTool when no patterns match."""
    tool = ExtractTool()

    result = tool.execute(
        response_text="This is a simple response with no special patterns.",
        extraction_target="dates and numbers",
    )

    assert result.success is True
    # Should have a note about manual review
    if "note" in result.output:
        assert "manual review" in result.output["note"].lower()


def test_extract_tool_metadata():
    """Test ExtractTool includes extraction_target in metadata."""
    tool = ExtractTool()

    result = tool.execute(
        response_text="Test response",
        extraction_target="test target",
    )

    assert result.success is True
    assert result.metadata["extraction_target"] == "test target"

