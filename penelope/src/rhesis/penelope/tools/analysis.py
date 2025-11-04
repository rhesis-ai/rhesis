"""
Analysis tools for Penelope.

These tools help Penelope analyze responses and extract information,
following Anthropic's ACI principles with extensive documentation.
"""

import re
from typing import Any

from rhesis.penelope.prompts import ANALYZE_TOOL_DESCRIPTION, EXTRACT_TOOL_DESCRIPTION
from rhesis.penelope.tools.base import Tool, ToolResult


class AnalyzeTool(Tool):
    """
    Tool for analyzing endpoint responses.

    Use this to systematically evaluate responses for patterns, issues,
    or specific characteristics relevant to your test goals.
    """

    @property
    def name(self) -> str:
        return "analyze_response"

    @property
    def description(self) -> str:
        return ANALYZE_TOOL_DESCRIPTION

    def execute(
        self, response_text: str = "", analysis_focus: str = "", context: str = "", **kwargs: Any
    ) -> ToolResult:
        """
        Execute analysis on the response.

        This is a simple implementation. In production, this could:
        - Use an LLM for deep analysis
        - Apply regex patterns
        - Check against known criteria
        - Score responses

        Args:
            response_text: The text to analyze (validated via Pydantic)
            analysis_focus: What to focus on (validated via Pydantic)
            context: Optional context
            **kwargs: Additional parameters

        Returns:
            ToolResult with analysis findings
        """
        # Perform basic analysis
        findings = []

        # Length analysis
        word_count = len(response_text.split())
        findings.append(f"Response length: {word_count} words")

        # Sentiment indicators (very basic)
        positive_words = ["yes", "can", "will", "happy", "help", "certainly", "glad"]
        negative_words = ["no", "cannot", "won't", "unable", "unfortunately", "sorry"]

        pos_count = sum(1 for word in positive_words if word in response_text.lower())
        neg_count = sum(1 for word in negative_words if word in response_text.lower())

        if pos_count > neg_count:
            findings.append("Tone: Generally positive/helpful")
        elif neg_count > pos_count:
            findings.append("Tone: Contains negative/limiting language")
        else:
            findings.append("Tone: Neutral")

        # Structure analysis
        has_bullets = "•" in response_text or "-" in response_text
        has_numbers = any(c.isdigit() for c in response_text)

        if has_bullets:
            findings.append("Structure: Contains bullet points or lists")
        if has_numbers:
            findings.append("Structure: Contains numerical information")

        # Focus-specific checks
        focus_lower = analysis_focus.lower()
        if "policy" in focus_lower or "rule" in focus_lower:
            policy_check = (
                "Contains policy language"
                if "policy" in response_text.lower()
                else "No explicit policy language"
            )
            findings.append(f"Policy check: {policy_check}")

        if "context" in focus_lower or "maintain" in focus_lower:
            findings.append("Context note: Manual review needed to verify context maintenance")

        # Build analysis summary
        analysis_summary = {
            "findings": findings,
            "analysis_focus": analysis_focus,
            "response_length": word_count,
            "context_provided": bool(context),
        }

        return ToolResult(
            success=True,
            output=analysis_summary,
            metadata={"response_analyzed": response_text[:100] + "..."},
        )


class ExtractTool(Tool):
    """
    Tool for extracting specific information from responses.

    Use this when you need to pull out specific data points, entities,
    or structured information from unstructured responses.
    """

    @property
    def name(self) -> str:
        return "extract_information"

    @property
    def description(self) -> str:
        return EXTRACT_TOOL_DESCRIPTION

    def execute(
        self, response_text: str = "", extraction_target: str = "", **kwargs: Any
    ) -> ToolResult:
        """
        Execute information extraction.

        Args:
            response_text: The text to extract from (validated via Pydantic)
            extraction_target: What to extract (validated via Pydantic)
            **kwargs: Additional parameters

        Returns:
            ToolResult with extracted information
        """
        extracted = {}

        # Extract dates (simple pattern)
        dates = re.findall(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", response_text)
        if dates:
            extracted["dates"] = dates

        # Extract numbers
        numbers = re.findall(r"\b\d+\b", response_text)
        target_lower = extraction_target.lower()
        if numbers and ("number" in target_lower or "count" in target_lower):
            extracted["numbers"] = numbers

        # Extract email addresses
        emails = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", response_text)
        if emails:
            extracted["emails"] = emails

        # Extract phone numbers (simple pattern)
        phones = re.findall(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", response_text)
        if phones:
            extracted["phones"] = phones

        # Extract sentences containing target keywords
        target_lower = extraction_target.lower()
        keywords = target_lower.split()
        relevant_sentences = []

        for sentence in response_text.split("."):
            if any(keyword in sentence.lower() for keyword in keywords):
                relevant_sentences.append(sentence.strip())

        if relevant_sentences:
            extracted["relevant_content"] = relevant_sentences

        if not extracted:
            extracted["note"] = (
                f"No specific {extraction_target} patterns found. Manual review may be needed."
            )

        return ToolResult(
            success=True,
            output=extracted,
            metadata={"extraction_target": extraction_target},
        )
