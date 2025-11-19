"""
Analysis tools for Penelope.

Analysis tools are used to examine, verify, or monitor data during testing,
but do not directly interact with the target. They should be used in conjunction
with target interaction tools, not as replacements for them.
"""

from abc import ABC
from typing import Any, Optional

from rhesis.penelope.tools.base import Tool, ToolResult


class AnalysisTool(Tool, ABC):
    """
    Base class for analysis tools.

    Analysis tools are used to examine responses, verify state, or monitor
    performance during testing. They complement target interaction tools
    but should not replace the conversation flow.

    Key characteristics:
    - They analyze data that already exists (responses, database state, metrics)
    - They do not directly communicate with the target
    - They should be used strategically, not repeatedly on the same data
    - After analysis, the conversation should continue with target interaction

    Examples:
    - Security scanners that analyze responses for vulnerabilities
    - Database verification tools that check data consistency
    - Performance monitors that track API metrics
    - Response analyzers that extract specific information
    """

    @property
    def tool_category(self) -> str:
        """Return the tool category for workflow management."""
        return "analysis"

    @property
    def analysis_type(self) -> str:
        """
        Return the type of analysis this tool performs.

        This is completely optional - users can define any string they want
        or return a generic type. Examples: "security", "verification",
        "monitoring", "custom", or even just "analysis".

        This is mainly used for workflow tracking and debugging.

        Returns:
            String describing the analysis type (defaults to "analysis")
        """
        return "analysis"  # Default implementation - users can override if they want

    @property
    def requires_target_response(self) -> bool:
        """
        Whether this tool requires a recent target response to function properly.

        Returns:
            True if the tool needs a target response, False if it can work independently
        """
        return True

    def get_usage_guidance(self) -> str:
        """
        Get guidance on when and how to use this analysis tool.

        Returns:
            String with usage guidance for the LLM
        """
        guidance = f"""
ANALYSIS TOOL: {self.name}
Type: {self.analysis_type}

WORKFLOW GUIDANCE:
1. Use this tool to analyze data after target interactions
2. Do not use repeatedly on the same data
3. After analysis, continue the conversation with send_message_to_target
4. This tool complements but does not replace target interaction

WHEN TO USE:
✓ After receiving a response from the target
✓ To verify or analyze specific data
✓ As part of a broader testing strategy

WHEN NOT TO USE:
✗ Without relevant data to analyze
✗ Repeatedly on the same response/data
✗ As a substitute for target interaction
✗ When no target interaction has occurred yet
"""

        if self.requires_target_response:
            guidance += "\n✗ Without a recent target response to analyze"

        return guidance

    def validate_usage_context(self, context: Optional[dict] = None) -> tuple[bool, str]:
        """
        Validate whether this tool should be used in the current context.

        Args:
            context: Optional context information (e.g., recent responses, turn history)

        Returns:
            Tuple of (is_valid, reason)
        """
        if self.requires_target_response and context:
            # Check if there's a recent target response
            recent_responses = context.get("recent_target_responses", [])
            if not recent_responses:
                return False, f"Tool {self.name} requires a target response but none found"

            # Check if this response was already analyzed by this tool
            analyzed_responses = context.get("analyzed_responses", {})
            tool_analyses = analyzed_responses.get(self.name, set())

            latest_response_id = recent_responses[0].get("id") if recent_responses else None
            if latest_response_id and latest_response_id in tool_analyses:
                return False, f"Response already analyzed by {self.name}"

        return True, "Usage context is valid"

    def execute_with_validation(self, context: Optional[dict] = None, **kwargs: Any) -> ToolResult:
        """
        Execute the tool with built-in validation.

        Args:
            context: Context information for validation
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with validation information
        """
        # Validate usage context
        is_valid, reason = self.validate_usage_context(context)
        if not is_valid:
            return ToolResult(
                success=False,
                output={},
                error=f"Invalid usage: {reason}",
                metadata={
                    "tool_category": self.tool_category,
                    "analysis_type": self.analysis_type,
                    "validation_failed": True,
                    "validation_reason": reason,
                },
            )

        # Execute the actual analysis
        result = self.execute(**kwargs)

        # Enhance metadata with analysis tool information
        if result.metadata is None:
            result.metadata = {}

        result.metadata.update(
            {
                "tool_category": self.tool_category,
                "analysis_type": self.analysis_type,
                "requires_target_response": self.requires_target_response,
            }
        )

        return result


# Concrete analysis tool implementations


class AnalyzeTextTool(AnalysisTool):
    """
    Tool for analyzing response content, tone, and characteristics.

    This tool examines text responses to identify patterns, sentiment,
    helpfulness, and other qualitative aspects.
    """

    @property
    def name(self) -> str:
        return "analyze_response"

    @property
    def description(self) -> str:
        return """
Analyze response text for tone, sentiment, helpfulness, and other characteristics.

WHEN TO USE:
✓ To evaluate response quality and tone
✓ To identify sentiment patterns
✓ To assess helpfulness and clarity

WHEN NOT TO USE:
✗ This is an ANALYSIS tool - after analyzing, continue the conversation with
  send_message_to_target

PARAMETERS:
- response_text: The text response to analyze
- analysis_focus: What aspect to focus on (e.g., "tone", "helpfulness")
- context: Optional context about the conversation

Returns analysis findings including tone assessment and response characteristics.
After analysis, send another message to the target to continue testing.
"""

    @property
    def analysis_type(self) -> str:
        return "response_analysis"

    def execute(
        self,
        response_text: str,
        analysis_focus: str = "general analysis",
        context: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute response analysis."""
        if not response_text.strip():
            return ToolResult(
                success=False,
                output={"error": "No response text provided for analysis"},
                metadata={"analysis_focus": analysis_focus},
            )

        findings = []
        output = {
            "analysis_focus": analysis_focus,
            "response_length": len(response_text),
            "context_provided": context is not None,
        }

        # Analyze tone
        response_lower = response_text.lower()
        positive_words = ["yes", "happy", "help", "certainly", "glad", "pleased", "welcome"]
        negative_words = ["no", "sorry", "cannot", "unable", "unfortunately", "problem"]

        positive_count = sum(1 for word in positive_words if word in response_lower)
        negative_count = sum(1 for word in negative_words if word in response_lower)

        if positive_count > negative_count:
            findings.append("Response has a positive and helpful tone")
        elif negative_count > positive_count:
            findings.append("Response has a more negative or limiting tone")
        else:
            findings.append("Response has a neutral tone")

        # Check for helpfulness indicators
        helpful_phrases = ["i can help", "let me", "i'll", "we can", "certainly", "of course"]
        if any(phrase in response_lower for phrase in helpful_phrases):
            findings.append("Response shows willingness to help")

        # Check for politeness
        polite_words = ["please", "thank", "sorry", "excuse", "pardon"]
        if any(word in response_lower for word in polite_words):
            findings.append("Response includes polite language")

        # Check for structure patterns
        if "-" in response_text or "•" in response_text:
            findings.append("Response contains bullet points or list structure")
        if any(char.isdigit() for char in response_text):
            findings.append("Response contains numerical information")

        # Check for policy language
        policy_words = ["policy", "terms", "conditions", "rules", "guidelines", "procedure"]
        if any(word in response_lower for word in policy_words):
            findings.append("Response contains policy-related language")

        # Check response completeness
        if len(response_text.strip()) < 10:
            findings.append("Response is very brief")
        elif len(response_text.strip()) > 200:
            findings.append("Response is detailed and comprehensive")

        # Calculate word count for response_length
        word_count = len(response_text.split())
        output["response_length"] = word_count
        output["findings"] = findings

        return ToolResult(
            success=True,
            output=output,
            metadata={"analysis_focus": analysis_focus, "tool_type": "analysis"},
        )


class ExtractTool(AnalysisTool):
    """
    Tool for extracting specific information from response text.

    This tool identifies and extracts structured data like dates, emails,
    phone numbers, and other patterns from text responses.
    """

    @property
    def name(self) -> str:
        return "extract_information"

    @property
    def description(self) -> str:
        return """
Extract specific information patterns from response text.

WHEN TO USE:
✓ To extract dates, numbers, contact information
✓ To identify specific data patterns
✓ To pull out structured information from responses

WHEN NOT TO USE:
✗ This is an EXTRACTION tool - after extracting, continue the conversation with
  send_message_to_target

PARAMETERS:
- response_text: The text response to extract information from
- extraction_target: What to extract (e.g., "dates", "contact info", "numbers")

Returns extracted information organized by type. After extraction, send another
message to the target to continue testing.
"""

    @property
    def analysis_type(self) -> str:
        return "information_extraction"

    def execute(
        self, response_text: str, extraction_target: str = "general extraction", **kwargs: Any
    ) -> ToolResult:
        """Execute information extraction."""
        import re

        if not response_text.strip():
            return ToolResult(
                success=False,
                output={"error": "No response text provided for extraction"},
                metadata={"extraction_target": extraction_target},
            )

        output = {}

        # Extract dates
        date_patterns = [
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",  # MM/DD/YYYY or MM-DD-YYYY
            r"\b\d{2,4}[/-]\d{1,2}[/-]\d{1,2}\b",  # YYYY/MM/DD or YYYY-MM-DD
        ]
        dates = []
        for pattern in date_patterns:
            dates.extend(re.findall(pattern, response_text))
        if dates:
            output["dates"] = list(set(dates))

        # Extract numbers
        numbers = re.findall(r"\b\d+\b", response_text)
        if numbers:
            output["numbers"] = [int(n) for n in numbers]

        # Extract email addresses
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        emails = re.findall(email_pattern, response_text)
        if emails:
            output["emails"] = emails

        # Extract phone numbers
        phone_patterns = [
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # XXX-XXX-XXXX or XXX.XXX.XXXX
            r"\(\d{3}\)\s*\d{3}[-.]?\d{4}\b",  # (XXX) XXX-XXXX
        ]
        phones = []
        for pattern in phone_patterns:
            phones.extend(re.findall(pattern, response_text))
        if phones:
            output["phones"] = phones

        # Extract relevant sentences based on extraction target
        if extraction_target and extraction_target != "general extraction":
            target_words = extraction_target.lower().split()
            sentences = re.split(r"[.!?]+", response_text)
            relevant_sentences = []

            for sentence in sentences:
                sentence = sentence.strip()
                if sentence and any(word in sentence.lower() for word in target_words):
                    relevant_sentences.append(sentence)

            if relevant_sentences:
                output["relevant_content"] = relevant_sentences

        # If no extractions found, add a note
        if not output:
            output["note"] = "No specific patterns found. Manual review may be needed."

        return ToolResult(
            success=True,
            output=output,
            metadata={"extraction_target": extraction_target, "tool_type": "extraction"},
        )
