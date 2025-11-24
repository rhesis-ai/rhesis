"""Mapping validator for testing SDK function mappings."""

import uuid
from typing import Any, Dict

from rhesis.backend.app.services.connector.schemas import TestResultMessage
from rhesis.backend.app.services.invokers.templating import TemplateRenderer
from rhesis.backend.logging import logger


class MappingValidator:
    """Validates mappings by sending synchronous test request to SDK."""

    def __init__(self):
        """Initialize validator with template renderer."""
        self.template_renderer = TemplateRenderer()

    async def validate_mappings(
        self,
        project_id: str,
        environment: str,
        function_name: str,
        request_mapping: Dict[str, str],
        response_mapping: Dict[str, str],
        timeout: float = 15.0,
    ) -> Dict[str, Any]:
        """
        Send test request to validate mappings work correctly.

        Blocks until test completes or timeout.

        Args:
            project_id: Project identifier
            environment: Environment name
            function_name: Function name to test
            request_mapping: Request template to validate
            response_mapping: Response mappings to validate
            timeout: Timeout in seconds

        Returns:
            {
                "success": bool,
                "error": Optional[str],
                "test_input": {...},
                "test_output": {...}
            }
        """
        from rhesis.backend.app.services.connector.manager import connection_manager

        logger.info(f"Validating mappings for {function_name}")

        # Create test input with all standard fields
        test_input = {
            "input": "test message for validation",
            "session_id": "test_session_123",
            "context": ["test document"],
            "metadata": {"test": True},
            "tool_calls": [],
        }

        try:
            # Render template to function kwargs
            function_kwargs = self.template_renderer.render(request_mapping, test_input)
            logger.debug(f"Rendered function kwargs for {function_name}: {function_kwargs}")

            # Execute via WebSocket and wait for actual result
            test_run_id = f"validation_{uuid.uuid4().hex[:8]}"

            logger.info(f"Sending validation test to {function_name} and awaiting result...")
            result = await connection_manager.send_and_await_result(
                project_id=project_id,
                environment=environment,
                test_run_id=test_run_id,
                function_name=function_name,
                inputs=function_kwargs,
                timeout=timeout,
            )

            # LOG EVERYTHING about the result for debugging
            logger.info(f"🔍 RAW RESULT for {function_name}:")
            logger.info(f"🔍 Result type: {type(result)}")
            logger.info(
                f"🔍 Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}"
            )
            logger.info(f"🔍 Full result: {result}")
            logger.info(f"🔍 Result as JSON: {str(result)}")

            # Check if the request failed to send
            if result.get("error") == "send_failed":
                return {
                    "success": False,
                    "error": "Failed to send test request to SDK",
                    "test_input": test_input,
                }

            # Check if timeout occurred
            if result.get("error") == "timeout":
                return {
                    "success": False,
                    "error": f"Validation test timed out after {timeout} seconds",
                    "test_input": test_input,
                }

            # Parse result using Pydantic schema for type safety
            try:
                logger.info(f"🔍 Attempting to parse result with TestResultMessage schema for {function_name}")
                test_result = TestResultMessage(**result)
                logger.info(f"🔍 Successfully parsed TestResultMessage for {function_name}: {test_result}")
            except Exception as e:
                logger.error(f"🟡 Invalid test result format for {function_name}: {e}")
                logger.error(f"🟡 Raw result that failed parsing: {result}")
                logger.error(f"🟡 Expected schema: TestResultMessage(type, test_run_id, status, output?, error?, duration_ms)")
                return {
                    "success": False,
                    "error": f"Invalid test result format: {e}",
                    "test_input": test_input,
                    "test_output": result,
                }

            # Check status and log detailed information
            logger.info(f"🔍 Checking status for {function_name}: '{test_result.status}'")
            logger.info(f"🔍 Status type: {type(test_result.status)}")
            logger.info(f"🔍 Status == 'error': {test_result.status == 'error'}")
            logger.info(f"🔍 Status == 'success': {test_result.status == 'success'}")

            if test_result.status == "error":
                error_msg = test_result.error or "Unknown SDK function error"
                logger.error(f"🔴 Validation FAILED for {function_name}: {error_msg}")
                logger.error(f"🔴 Error field: {test_result.error}")
                logger.error(f"🔴 Duration: {test_result.duration_ms}ms")
                logger.error(f"🔴 Full result: {test_result.dict()}")
                return {
                    "success": False,
                    "error": f"SDK function error: {error_msg}",
                    "test_input": test_input,
                    "test_output": test_result.dict(),
                }
            elif test_result.status == "success":
                # Success - function executed without errors
                logger.info(f"🟢 Validation PASSED for {function_name}")
                logger.info(f"🟢 Output: {test_result.output}")
                logger.info(f"🟢 Duration: {test_result.duration_ms}ms")
                logger.debug(f"🟢 Full result: {test_result.dict()}")
                return {
                    "success": True,
                    "test_input": test_input,
                    "test_output": test_result.output,
                }
            else:
                # Unknown status - treat as error for safety
                logger.error(f"🟡 Unknown validation status for {function_name}: '{test_result.status}'")
                logger.error(f"🟡 Available statuses should be: 'success' or 'error'")
                logger.error(f"🟡 Full result: {test_result.dict()}")
                return {
                    "success": False,
                    "error": f"Unknown validation status: {test_result.status}",
                    "test_input": test_input,
                    "test_output": test_result.dict(),
                }

        except Exception as e:
            logger.error(f"Validation error for {function_name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "test_input": test_input,
            }
