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
        timeout: float = 30.0,
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
            timeout: Timeout in seconds (default: 30s for LLM endpoints)

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

        # Initialize test_run_id to None to avoid NameError in exception handler
        test_run_id = None

        try:
            # Render template to function kwargs
            function_kwargs = self.template_renderer.render(request_mapping, test_input)
            logger.debug(f"Rendered function kwargs for {function_name}: {function_kwargs}")

            # Execute via WebSocket and wait for actual result
            test_run_id = f"validation_{uuid.uuid4().hex[:8]}"

            logger.info(f"Sending validation test to {function_name}...")

            # Send test request
            success = await connection_manager.send_test_request(
                project_id=project_id,
                environment=environment,
                test_run_id=test_run_id,
                function_name=function_name,
                inputs=function_kwargs,
            )

            if not success:
                return {
                    "success": False,
                    "error": "Failed to send test request to SDK",
                    "test_input": test_input,
                }

            logger.info(f"Test request sent for {function_name}, waiting {timeout}s for result...")

            # Simple synchronous wait - check for result every 0.1 seconds
            import asyncio

            elapsed = 0.0
            check_interval = 0.1

            while elapsed < timeout:
                await asyncio.sleep(check_interval)
                elapsed += check_interval

                # Check if result arrived
                result = connection_manager.get_test_result(test_run_id)

                if result:
                    logger.info(f"Received result for {function_name} after {elapsed:.1f}s")

                    # Clean up result after retrieval
                    connection_manager.cleanup_test_result(test_run_id)

                    # Parse result with schema
                    try:
                        test_result = TestResultMessage(**result)
                    except Exception as e:
                        logger.error(f"Invalid result format for {function_name}: {e}")
                        return {
                            "success": False,
                            "error": f"Invalid result format: {e}",
                            "test_input": test_input,
                            "test_output": result,
                        }

                    # Check status
                    if test_result.status == "success":
                        logger.info(f"Validation PASSED for {function_name}")
                        return {
                            "success": True,
                            "test_input": test_input,
                            "test_output": test_result.output,
                        }
                    else:
                        error_msg = test_result.error or "Unknown SDK function error"
                        logger.error(f"Validation FAILED for {function_name}: {error_msg}")
                        return {
                            "success": False,
                            "error": f"SDK function error: {error_msg}",
                            "test_input": test_input,
                            "test_output": test_result.model_dump(),
                        }

            # Timeout reached - mark as cancelled immediately to prevent race condition
            # where late results arrive after timeout detection but before cleanup
            connection_manager.cleanup_test_result(test_run_id)
            logger.warning(f"Validation test for {function_name} timed out after {timeout}s")
            return {
                "success": False,
                "error": f"Validation test timed out after {timeout} seconds",
                "test_input": test_input,
            }

        except Exception as e:
            # Mark as cancelled immediately to prevent race condition with late results
            # Only cleanup if test_run_id was assigned (exception occurred after test started)
            if test_run_id is not None:
                connection_manager.cleanup_test_result(test_run_id)
            logger.error(f"Validation error for {function_name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "test_input": test_input,
            }
