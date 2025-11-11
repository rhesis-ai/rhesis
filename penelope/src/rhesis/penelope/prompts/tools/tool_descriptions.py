"""
Tool descriptions for Penelope's tools.

Following Anthropic's ACI principles, these descriptions provide extensive
documentation, examples, and guidance for tool usage.
"""

# Target Interaction Tool Description Template
# Note: This is a template that will be formatted with target-specific documentation
TARGET_INTERACTION_TOOL_DESCRIPTION_TEMPLATE = """Send a message to the test target and \
receive a response.

{target_documentation}

This is your PRIMARY tool for testing. Each call represents one conversational turn
with the system under test.

═══════════════════════════════════════════════════════════════════════════════

WHEN TO USE:
✓ To send user queries/prompts to the endpoint
✓ To continue multi-turn conversations
✓ To test specific inputs or scenarios
✓ To gather responses for analysis

WHEN NOT TO USE:
✗ Don't use for analysis (use analyze_response instead)
✗ Don't use before planning your approach
✗ Don't make calls without clear purpose

═══════════════════════════════════════════════════════════════════════════════

BEST PRACTICES:

1. Read Responses Carefully
   ├─ Always examine the full response before deciding next steps
   ├─ Look for both explicit content and implicit behaviors
   └─ Note any errors, warnings, or unexpected formatting

2. Maintain Conversation Context
   ├─ Use the session_id from previous responses for follow-ups
   ├─ Don't start a new session unless testing fresh conversation
   └─ Session continuity is crucial for multi-turn testing

3. Test Systematically
   ├─ Each message should have a specific testing purpose
   ├─ Build on previous responses naturally
   └─ Avoid repetitive or aimless queries

4. Write Natural Messages
   ├─ Write as a real user would write
   ├─ Avoid test-like language ("Test case 1...")
   └─ Match the tone appropriate for the endpoint

═══════════════════════════════════════════════════════════════════════════════

EXAMPLE USAGE:

# Good Example 1: Initial question
>>> send_message_to_target(
...     message="What's your refund policy for electronics?"
... )
{{
  "response": "Our electronics refund policy allows...",
  "session_id": "abc123",
  "success": true
}}

# Good Example 2: Natural follow-up
>>> send_message_to_target(
...     message="What if I opened the box but didn't use it?",
...     session_id="abc123"
... )
{{
  "response": "If the product is unopened and in original condition...",
  "session_id": "abc123",
  "success": true
}}

# Good Example 3: Testing edge case
>>> send_message_to_target(
...     message="I bought it 6 months ago, can I still return it?"
... )

# Bad Example: Too artificial
>>> send_message_to_target(
...     message="Test Case #1: Refund query validation"
... )

# Bad Example: Template-like
>>> send_message_to_target(
...     message="{{user_input_here}}"
... )

═══════════════════════════════════════════════════════════════════════════════

IMPORTANT NOTES:

⚠ Session Management:
  - First message: Leave session_id empty, you'll get one in response
  - Follow-ups: Always use the session_id from the previous response
  - New conversation: Omit session_id to start fresh
  - Sessions may expire after inactivity (typically 1 hour)

⚠ Error Handling:
  - If success=false, check the error field for details
  - Network errors will be retried automatically (up to 3 times)
  - Invalid requests won't be retried

⚠ Response Format:
  - Always check the "success" field first
  - Response content is in the "response" field
  - Additional metadata may be in "metadata" field

═══════════════════════════════════════════════════════════════════════════════

Remember: Each call costs time and resources. Make every interaction count."""

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
