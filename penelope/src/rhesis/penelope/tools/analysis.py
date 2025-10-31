"""
Analysis tools for Penelope.

These tools help Penelope analyze responses and extract information,
following Anthropic's ACI principles with extensive documentation.
"""

import re
from typing import Any

from rhesis.penelope.tools.base import Tool, ToolParameter, ToolResult


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
        return """Analyze an endpoint response for patterns, issues, or characteristics.

Use this tool to systematically evaluate responses you've received from the endpoint.
This helps you reason about what you've learned and plan next steps.

═══════════════════════════════════════════════════════════════════════════════

WHEN TO USE:
✓ After receiving a response that needs careful evaluation
✓ To check for specific patterns or behaviors
✓ To identify potential issues or anomalies
✓ To extract structured insights from unstructured responses

WHEN NOT TO USE:
✗ Don't analyze before getting a response
✗ Don't use for simple extractions (use extract_information instead)
✗ Don't over-analyze obvious results

═══════════════════════════════════════════════════════════════════════════════

BEST PRACTICES:

1. Be Specific
   ├─ Clearly state what you're looking for
   ├─ Focus on test-relevant aspects
   └─ Avoid vague analysis requests

2. Consider Context
   ├─ Include relevant conversation history
   ├─ Reference your test goals
   └─ Note previous findings

3. Look for Patterns
   ├─ Consistency across turns
   ├─ Quality indicators
   └─ Edge case behaviors

═══════════════════════════════════════════════════════════════════════════════

This tool provides structured analysis to help you make informed testing decisions."""
    
    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="response_text",
                type="string",
                description="""The response text to analyze.

Typically this is the "response" field from send_message_to_endpoint output.

Example:
  "Our refund policy allows returns within 30 days of purchase..."

Length: Can be any length, but focus on relevant portions for efficiency.""",
                required=True,
            ),
            ToolParameter(
                name="analysis_focus",
                type="string",
                description="""What to focus on in the analysis.

Be specific about what you're looking for.

Good examples:
  ✓ "Check if the response contains policy details"
  ✓ "Evaluate tone and professionalism"
  ✓ "Look for signs of hallucination or incorrect information"
  ✓ "Check if context from previous messages is maintained"
  ✓ "Identify any security concerns or data leaks"

Bad examples:
  ✗ "Analyze everything" (too vague)
  ✗ "Check response" (not specific enough)

Be clear and focused for best results.""",
                required=True,
            ),
            ToolParameter(
                name="context",
                type="string",
                description="""Optional context to inform the analysis.

Include relevant background:
- Previous conversation turns
- Expected behaviors
- Test goals
- Domain knowledge

Example:
  "User previously asked about electronics, now asking about timeframes."

This helps provide more accurate analysis.""",
                required=False,
            ),
        ]
    
    def execute(
        self,
        response_text: str = "",
        analysis_focus: str = "",
        context: str = "",
        **kwargs: Any
    ) -> ToolResult:
        """
        Execute analysis on the response.
        
        This is a simple implementation. In production, this could:
        - Use an LLM for deep analysis
        - Apply regex patterns
        - Check against known criteria
        - Score responses
        
        Args:
            response_text: The text to analyze
            analysis_focus: What to focus on
            context: Optional context
            **kwargs: Additional parameters
            
        Returns:
            ToolResult with analysis findings
        """
        # Validate input
        is_valid, error = self.validate_input(
            response_text=response_text,
            analysis_focus=analysis_focus,
            context=context,
        )
        if not is_valid:
            return ToolResult(success=False, output={}, error=error)
        
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
        return """Extract specific information from an endpoint response.

Use this tool when you need to pull out specific data, facts, or entities from
a response for verification or further testing.

═══════════════════════════════════════════════════════════════════════════════

WHEN TO USE:
✓ To extract specific facts or data points
✓ To pull out entities (dates, numbers, names)
✓ To verify presence of expected information
✓ To gather data for comparison or validation

WHEN NOT TO USE:
✗ For general response understanding (use analyze_response)
✗ For sentiment or quality evaluation
✗ When the information is already obvious

═══════════════════════════════════════════════════════════════════════════════

EXAMPLE USES:
- Extract policy details (timeframes, conditions, exceptions)
- Pull out specific facts or claims
- Identify mentioned products, services, or features
- Extract numerical values or dates
- Find quoted regulations or rules

This tool helps you gather specific data points for test verification."""
    
    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="response_text",
                type="string",
                description="The response text to extract information from",
                required=True,
            ),
            ToolParameter(
                name="extraction_target",
                type="string",
                description="""What specific information to extract.

Examples:
  ✓ "refund timeframe"
  ✓ "policy exceptions"
  ✓ "mentioned products"
  ✓ "dates and deadlines"
  ✓ "contact information"

Be specific about what you're looking for.""",
                required=True,
            ),
        ]
    
    def execute(
        self,
        response_text: str = "",
        extraction_target: str = "",
        **kwargs: Any
    ) -> ToolResult:
        """
        Execute information extraction.
        
        Args:
            response_text: The text to extract from
            extraction_target: What to extract
            **kwargs: Additional parameters
            
        Returns:
            ToolResult with extracted information
        """
        # Validate input
        is_valid, error = self.validate_input(
            response_text=response_text,
            extraction_target=extraction_target,
        )
        if not is_valid:
            return ToolResult(success=False, output={}, error=error)
        
        extracted = {}
        
        # Extract dates (simple pattern)
        dates = re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', response_text)
        if dates:
            extracted["dates"] = dates
        
        # Extract numbers
        numbers = re.findall(r'\b\d+\b', response_text)
        target_lower = extraction_target.lower()
        if numbers and ("number" in target_lower or "count" in target_lower):
            extracted["numbers"] = numbers
        
        # Extract email addresses
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', response_text)
        if emails:
            extracted["emails"] = emails
        
        # Extract phone numbers (simple pattern)
        phones = re.findall(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', response_text)
        if phones:
            extracted["phones"] = phones
        
        # Extract sentences containing target keywords
        target_lower = extraction_target.lower()
        keywords = target_lower.split()
        relevant_sentences = []
        
        for sentence in response_text.split('.'):
            if any(keyword in sentence.lower() for keyword in keywords):
                relevant_sentences.append(sentence.strip())
        
        if relevant_sentences:
            extracted["relevant_content"] = relevant_sentences
        
        if not extracted:
            extracted["note"] = (
                f"No specific {extraction_target} patterns found. "
                "Manual review may be needed."
            )
        
        return ToolResult(
            success=True,
            output=extracted,
            metadata={"extraction_target": extraction_target},
        )

