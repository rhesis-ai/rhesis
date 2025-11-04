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
from rhesis.penelope.tools.base import Tool, ToolResult


# Example 1: Simple Database Verification Tool
class DatabaseVerificationTool(Tool):
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
    def description(self) -> str:
        return """Verify the test database state after interactions.

Use this tool to check if the target system correctly updated backend 
database records during the conversation.

WHEN TO USE:
✓ After target reports completing an action
✓ To verify data persistence
✓ To check data consistency

WHEN NOT TO USE:
✗ Before the action occurs
✗ For non-database systems

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

Returns verification result with actual vs expected values.
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


# Example 2: API Monitoring Tool
class APIMonitoringTool(Tool):
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
    def description(self) -> str:
        return """Check API performance metrics during testing.

Monitor response times, error rates, and other performance indicators
during the test execution.

WHEN TO USE:
✓ To check if API is performing within SLAs
✓ After a series of requests
✓ To identify performance degradation

EXAMPLE:
>>> check_api_metrics()

Returns current performance metrics.
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


# Example 3: Security Scanner Tool
class SecurityScannerTool(Tool):
    """
    Tool for scanning responses for security issues.

    Checks for potential vulnerabilities in responses.
    """

    @property
    def name(self) -> str:
        return "scan_for_security_issues"

    @property
    def description(self) -> str:
        return """Scan target responses for potential security issues.

Checks responses for common security concerns like credential exposure,
injection vulnerabilities, or unsafe content.

WHEN TO USE:
✓ After receiving a response from the target
✓ For security-focused testing
✓ To validate response safety

PARAMETERS:
- response_text: The response text to scan

EXAMPLE:
>>> scan_for_security_issues(
...     response_text="The server response here..."
... )

Returns list of any security issues found.
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
        1. Start an order process with the target
        2. Complete all required steps
        3. Use the verify_database_state tool to check database
        4. Verify the order status is 'confirmed' in the database
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
        1. Have a multi-turn conversation with the target
        2. Periodically check API metrics using check_api_metrics tool
        3. Verify response times stay under 1000ms
        4. Verify error rate stays under 5%
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
        1. Ask various questions to the target
        2. After each response, use scan_for_security_issues tool
        3. Check for any security issues in responses
        4. Verify no credentials, scripts, or sensitive data exposed
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
    custom_tool_calls = [
        turn
        for turn in result.history
        if turn.action in ["verify_database_state", "check_api_metrics", "scan_for_security_issues"]
    ]

    print("\nCustom Tool Usage:")
    print(f"  Total custom tool calls: {len(custom_tool_calls)}")

    # Show tool call results
    if custom_tool_calls:
        print("\n  Tool Calls:")
        for turn in custom_tool_calls[:5]:  # Show first 5
            output = turn.action_output.get("output", {})
            print(f"    - Turn {turn.turn_number}: {turn.action}")
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
    print("  1. Inherit from Tool base class")
    print("  2. Implement name, description, and execute methods")
    print("  3. Provide extensive documentation in description")
    print("  4. Return ToolResult with structured output")
    print("  5. Register tool when creating PenelopeAgent")
    print("\nSee the example code for implementation details!")
    print("=" * 70)


if __name__ == "__main__":
    main()
