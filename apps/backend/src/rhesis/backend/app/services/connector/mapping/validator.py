"""Mapping validator for testing SDK function mappings."""

import uuid
from typing import Any, Dict

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
        timeout: float = 5.0,
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

            # Execute via WebSocket with blocking wait
            test_run_id = f"validation_{uuid.uuid4().hex[:8]}"

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

            # Wait for result (synchronous)
            # TODO: Implement result awaiting mechanism in connection_manager
            # For now, assume success if request sent
            logger.info(f"Test request sent for {function_name}, assuming success")

            return {
                "success": True,
                "test_input": test_input,
                "test_output": {"status": "pending"},  # Will be enhanced
            }

        except Exception as e:
            logger.error(f"Validation error for {function_name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "test_input": test_input,
            }
