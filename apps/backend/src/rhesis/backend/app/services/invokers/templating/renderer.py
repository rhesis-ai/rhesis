"""Template rendering using Jinja2."""

import json
import uuid
from typing import Any, Dict

from jinja2 import Template

from rhesis.backend.logging import logger


class TemplateRenderer:
    """Handles template rendering using Jinja2."""

    def render(self, template_data: Any, input_data: Dict[str, Any]) -> Any:
        """
        Render a template with input data.

        Automatically generates session_id if referenced in template but missing from input.

        Args:
            template_data: Template string or dict to render
            input_data: Data to use in template rendering

        Returns:
            Rendered template (parsed as JSON if possible, or as string/dict)
        """
        # Ensure session_id exists if it's referenced in template but missing from input
        if isinstance(template_data, (dict, str)):
            template_str = (
                json.dumps(template_data) if isinstance(template_data, dict) else template_data
            )
            if "{{ session_id }}" in template_str and "session_id" not in input_data:
                input_data = input_data.copy()
                input_data["session_id"] = str(uuid.uuid4())
                logger.info(f"Auto-generated session_id: {input_data['session_id']}")

        return self._render_recursive(template_data, input_data)

    def _render_recursive(self, template_data: Any, input_data: Dict[str, Any]) -> Any:
        """
        Recursively render template data, handling nested structures.

        Args:
            template_data: Template data to render (string, dict, list, or other)
            input_data: Data to use in template rendering

        Returns:
            Rendered template data with same structure as input
        """
        if isinstance(template_data, str):
            template = Template(template_data)
            rendered = template.render(**input_data)
            try:
                return json.loads(rendered)
            except json.JSONDecodeError:
                return rendered
        elif isinstance(template_data, dict):
            result = {}
            for key, value in template_data.items():
                result[key] = self._render_recursive(value, input_data)
            return result
        elif isinstance(template_data, list):
            result = []
            for item in template_data:
                result.append(self._render_recursive(item, input_data))
            return result
        else:
            # For other types (int, float, bool, None, etc.), return as-is
            return template_data
