"""
Tool descriptions for Penelope's analysis tools.

Following Anthropic's ACI principles, these descriptions provide extensive
documentation, examples, and guidance for tool usage.
"""

# Analysis Tool Description
ANALYZE_TOOL_DESCRIPTION = """Analyze an endpoint response for patterns, issues, or characteristics.

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

# Extract Tool Description
EXTRACT_TOOL_DESCRIPTION = """Extract specific information from an endpoint response.

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
