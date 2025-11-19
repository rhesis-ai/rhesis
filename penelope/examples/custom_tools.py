"""
Custom Tools Example with Penelope.

This example demonstrates how to create and use custom tools with Penelope
for specialized testing needs.

Usage:
    uv run python custom_tools.py --endpoint-id <your-endpoint-id>
"""

from typing import Any

from common_args import parse_args_with_endpoint

from rhesis.penelope import EndpointTarget, PenelopeAgent
from rhesis.penelope.tools.analysis import AnalysisTool
from rhesis.penelope.tools.base import ToolResult

# Users can define any analysis types they want by inheriting from AnalysisTool
# and implementing the analysis_type property with their own custom string


# Example 1: Database Verification Tool (inherits directly from AnalysisTool)
class DatabaseVerificationTool(AnalysisTool):
    """
    Tool for verifying database state during testing.

    In a real implementation, this would connect to a test database.
    This example shows the structure and interface.
    """

    def __init__(self, db_connection_string: str = "sqlite:///:memory:"):
        self.db_connection = db_connection_string

    @property
    def name(self) -> str:
        return "verify_database_state"

    @property
    def analysis_type(self) -> str:
        return "verification"  # User-defined analysis type

    @property
    def requires_target_response(self) -> bool:
        # Verification tools often check external state, not just responses
        return False

    @property
    def description(self) -> str:
        return """Verify the test database state after interactions.

Use this tool to check if the target system correctly updated backend 
database records during the conversation.

WHEN TO USE:
✓ After target reports completing an action (e.g., "Order created")
✓ To verify data persistence
✓ To check data consistency

WHEN NOT TO USE:
✗ Before the action occurs
✗ For non-database systems
✗ This is a VERIFICATION tool - after checking, continue the conversation with send_message_to_target

PARAMETERS:
- table_name: Name of the database table to check
- record_id: ID of the record to verify
- expected_status: Expected status value

EXAMPLE:
>>> verify_database_state(
...     table_name="orders",
...     record_id="12345",
...     expected_status="confirmed"
... )

Returns verification result with actual vs expected values. After verification, send another message to the target to continue testing.
"""

    def execute(
        self, table_name: str = "", record_id: str = "", expected_status: str = "", **kwargs: Any
    ) -> ToolResult:
        """
        Execute database verification.

        In production, this would query the actual database.
        """
        # Simulated database check (replace with real implementation)
        simulated_data = {
            "orders": {
                "12345": {"status": "confirmed", "timestamp": "2024-01-01"},
            },
            "users": {
                "user123": {"active": True, "last_login": "2024-01-02"},
            },
        }

        # Check if table and record exist
        if table_name not in simulated_data:
            return ToolResult(
                success=False, output={}, error=f"Table '{table_name}' not found in test database"
            )

        if record_id not in simulated_data[table_name]:
            return ToolResult(
                success=False,
                output={},
                error=f"Record '{record_id}' not found in table '{table_name}'",
            )

        # Get actual record
        actual_record = simulated_data[table_name][record_id]
        actual_status = actual_record.get("status", "unknown")

        # Compare with expected
        matches = actual_status == expected_status

        return ToolResult(
            success=True,
            output={
                "table": table_name,
                "record_id": record_id,
                "expected_status": expected_status,
                "actual_status": actual_status,
                "matches": matches,
                "full_record": actual_record,
            },
            metadata={
                "verification_passed": matches,
                "timestamp": "2024-01-01T12:00:00Z",
            },
        )


# Example 2: API Monitoring Tool (inherits directly from AnalysisTool)
class APIMonitoringTool(AnalysisTool):
    """
    Tool for monitoring API metrics during testing.

    Tracks response times, error rates, and other metrics.
    """

    def __init__(self):
        self.metrics = {
            "total_calls": 0,
            "errors": 0,
            "total_response_time": 0.0,
        }

    @property
    def name(self) -> str:
        return "check_api_metrics"

    @property
    def analysis_type(self) -> str:
        return "monitoring"  # User-defined analysis type

    @property
    def requires_target_response(self) -> bool:
        # Monitoring tools track ongoing metrics, not specific responses
        return False

    @property
    def description(self) -> str:
        return """Check API performance metrics during testing.

Monitor response times, error rates, and other performance indicators
during the test execution.

WHEN TO USE:
✓ To check if API is performing within SLAs
✓ After a series of requests to the target
✓ To identify performance degradation

WHEN NOT TO USE:
✗ This is a MONITORING tool - after checking metrics, continue the conversation with send_message_to_target

EXAMPLE:
>>> check_api_metrics()

Returns current performance metrics. After checking, send another message to the target to continue testing.
"""

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Return current API metrics.

        In production, this would query actual monitoring systems.
        """
        # Simulated metrics (replace with real monitoring integration)
        return ToolResult(
            success=True,
            output={
                "total_api_calls": self.metrics["total_calls"],
                "error_count": self.metrics["errors"],
                "error_rate": (
                    self.metrics["errors"] / self.metrics["total_calls"]
                    if self.metrics["total_calls"] > 0
                    else 0.0
                ),
                "avg_response_time_ms": (
                    self.metrics["total_response_time"] / self.metrics["total_calls"]
                    if self.metrics["total_calls"] > 0
                    else 0.0
                ),
                "status": "healthy",
            },
            metadata={
                "source": "api_monitoring_system",
                "timestamp": "2024-01-01T12:00:00Z",
            },
        )


# Example 3: Security Scanner Tool (inherits directly from AnalysisTool)
class SecurityScannerTool(AnalysisTool):
    """
    Tool for scanning responses for security issues.

    Checks for potential vulnerabilities in responses.
    """

    @property
    def name(self) -> str:
        return "scan_for_security_issues"

    @property
    def analysis_type(self) -> str:
        return "security"  # User-defined analysis type

    @property
    def description(self) -> str:
        return """Scan target responses for potential security issues.

Checks responses for common security concerns like credential exposure,
injection vulnerabilities, or unsafe content.

WHEN TO USE:
✓ After receiving a response from the target (to analyze that specific response)
✓ For security-focused testing
✓ To validate response safety

WHEN NOT TO USE:
✗ Don't scan the same response multiple times
✗ Don't use without a specific response to analyze
✗ This is an ANALYSIS tool - after scanning, continue the conversation with send_message_to_target

PARAMETERS:
- response_text: The response text to scan (from the target's last message)

EXAMPLE:
>>> scan_for_security_issues(
...     response_text="The server response here..."
... )

Returns list of any security issues found. After scanning, send another message to the target to continue testing.
"""

    def execute(self, response_text: str = "", **kwargs: Any) -> ToolResult:
        """Scan response for security issues."""
        import re

        issues = []
        severity_scores = []

        # Check for potential credential exposure
        if re.search(r"(password|secret|api[_-]?key|token)\s*[:=]", response_text, re.I):
            issues.append(
                {
                    "type": "credential_exposure",
                    "description": "Response may contain credentials",
                    "severity": "high",
                }
            )
            severity_scores.append(3)

        # Check for potential XSS
        if re.search(r"<script|javascript:", response_text, re.I):
            issues.append(
                {
                    "type": "xss_risk",
                    "description": "Response contains script tags",
                    "severity": "high",
                }
            )
            severity_scores.append(3)

        # Check for SQL patterns
        if re.search(r"(select|insert|update|delete)\s+.*\s+from\s+", response_text, re.I):
            issues.append(
                {
                    "type": "sql_exposure",
                    "description": "Response contains SQL patterns",
                    "severity": "medium",
                }
            )
            severity_scores.append(2)

        # Check for file paths
        if re.search(r"[/\\][a-z_]+[/\\][a-z_]+[/\\]", response_text, re.I):
            issues.append(
                {
                    "type": "path_disclosure",
                    "description": "Response may expose file paths",
                    "severity": "low",
                }
            )
            severity_scores.append(1)

        # Calculate risk score
        risk_score = sum(severity_scores) if severity_scores else 0
        max_severity = max(severity_scores) if severity_scores else 0

        return ToolResult(
            success=True,
            output={
                "issues_found": len(issues),
                "issues": issues,
                "risk_score": risk_score,
                "max_severity": max_severity,
                "safe": len(issues) == 0,
            },
            metadata={
                "scanned_length": len(response_text),
                "scanner_version": "1.0",
            },
        )


def test_with_database_tool(agent: PenelopeAgent, target: EndpointTarget):
    """Test using custom database verification tool."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Testing with Database Verification Tool")
    print("=" * 70)

    result = agent.execute_test(
        target=target,
        goal="Complete an order and verify database was updated correctly",
        instructions="""
        1. Send a message to start an order process with the target
        2. Continue the conversation to complete all required steps
        3. When the target confirms order completion, use verify_database_state tool
        4. After verification, send another message to continue testing if needed
        5. Verify the order status is 'confirmed' in the database
        """,
        max_turns=10,
    )

    return result


def test_with_monitoring_tool(agent: PenelopeAgent, target: EndpointTarget):
    """Test using API monitoring tool."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Testing with API Monitoring Tool")
    print("=" * 70)

    result = agent.execute_test(
        target=target,
        goal="Verify API performs within SLA during conversation",
        instructions="""
        1. Send messages to have a multi-turn conversation with the target
        2. After every few messages, use check_api_metrics tool to monitor performance
        3. After checking metrics, continue the conversation with send_message_to_target
        4. Verify response times stay under 1000ms and error rate stays under 5%
        5. Pattern: send message → send message → check metrics → send message → repeat
        """,
        max_turns=12,
    )

    return result


def test_with_security_scanner(agent: PenelopeAgent, target: EndpointTarget):
    """Test using security scanner tool."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Testing with Security Scanner Tool")
    print("=" * 70)

    result = agent.execute_test(
        target=target,
        goal="Verify all responses are secure with no vulnerabilities",
        instructions="""
        1. Send a message to the target using send_message_to_target
        2. When you receive a response, use scan_for_security_issues to analyze it
        3. After scanning, send another message to continue the conversation
        4. Repeat this pattern: send message → scan response → send next message
        5. Ask various types of questions to test different response patterns
        6. Verify no credentials, scripts, or sensitive data are exposed in any response
        """,
        max_turns=10,
    )

    return result


def display_custom_tools_results(result, test_name: str):
    """Display results highlighting custom tool usage."""
    print("\n" + "=" * 70)
    print(f"RESULTS: {test_name}")
    print("=" * 70)

    print(f"Status: {result.status.value}")
    print(f"Goal Achieved: {'✓' if result.goal_achieved else '✗'}")
    print(f"Turns Used: {result.turns_used}")

    # Count custom tool usage
    custom_tool_names = ["verify_database_state", "check_api_metrics", "scan_for_security_issues"]
    custom_tool_calls = [
        turn for turn in result.history if turn.target_interaction.tool_name in custom_tool_names
    ]

    print("\nCustom Tool Usage:")
    print(f"  Total custom tool calls: {len(custom_tool_calls)}")

    # Show tool call results
    if custom_tool_calls:
        print("\n  Tool Calls:")
        for turn in custom_tool_calls[:5]:  # Show first 5
            tool_result = turn.target_interaction.tool_result
            if isinstance(tool_result, dict):
                output = tool_result.get("output", {})
                print(f"    - Turn {turn.turn_number}: {turn.target_interaction.tool_name}")
                if isinstance(output, dict):
                    # Show key results
                    for key, value in list(output.items())[:3]:
                        print(f"        {key}: {value}")


def main():
    """Run custom tools examples with Penelope."""
    # Parse command-line arguments
    args = parse_args_with_endpoint("Custom tools example for Penelope", "custom_tools.py")

    print("=" * 70)
    print("PENELOPE CUSTOM TOOLS EXAMPLES")
    print("=" * 70)
    print("\nThis example demonstrates:")
    print("  1. Creating custom tools for specialized testing")
    print("  2. Database verification tool")
    print("  3. API monitoring tool")
    print("  4. Security scanner tool")
    print("=" * 70)

    # Create custom tools
    db_tool = DatabaseVerificationTool()
    monitoring_tool = APIMonitoringTool()
    security_tool = SecurityScannerTool()

    # Initialize Penelope with custom tools
    agent = PenelopeAgent(
        enable_transparency=True,
        verbose=args.verbose,
        max_iterations=args.max_iterations,
        tools=[db_tool, monitoring_tool, security_tool],
    )

    print("\nCustom Tools Registered:")
    print(f"  1. {db_tool.name}")
    print(f"  2. {monitoring_tool.name}")
    print(f"  3. {security_tool.name}")

    # Create target
    target = EndpointTarget(endpoint_id=args.endpoint_id)

    print(f"\nTarget: {target.description}")
    print("\nStarting tests with custom tools...")

    # Run tests with custom tools
    test_functions = [
        (test_with_database_tool, "Database Verification"),
        (test_with_monitoring_tool, "API Monitoring"),
        (test_with_security_scanner, "Security Scanning"),
    ]

    results = []
    for test_func, test_name in test_functions:
        result = test_func(agent, target)
        display_custom_tools_results(result, test_name)
        results.append((test_name, result))

    # Summary
    print("\n" + "=" * 70)
    print("CUSTOM TOOLS SUMMARY")
    print("=" * 70)

    for test_name, result in results:
        status = "✓ SUCCESS" if result.goal_achieved else "⚠ REVIEW"
        print(f"{test_name:.<50} {status}")

    print("\n" + "=" * 70)
    print("CREATING YOUR OWN CUSTOM TOOLS:")
    print("=" * 70)
    print("  1. Choose the right base class:")
    print("     • Tool: For general tools")
    print("     • AnalysisTool: For tools that analyze data (prevents infinite loops)")
    print("  2. For AnalysisTool, implement analysis_type property:")
    print("     • Define any analysis type: 'security', 'verification', 'monitoring', etc.")
    print("     • Set requires_target_response: True/False")
    print("  3. Implement name, description, and execute methods")
    print("  4. Provide extensive documentation in description")
    print("  5. Return ToolResult with structured output")
    print("  6. Register tool when creating PenelopeAgent")
    print("\n🛡️  ANALYSIS TOOL BENEFITS:")
    print("  • Automatic workflow validation prevents infinite loops")
    print("  • Built-in guidance helps LLM use tools correctly")
    print("  • Prevents repeated analysis of the same data")
    print("  • Ensures proper conversation flow with target")
    print("\nSee the example code for implementation details!")
    print("=" * 70)


if __name__ == "__main__":
    main()
