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

        if isinstance(template_data, str):
            template = Template(template_data)
            rendered = template.render(**input_data)
            try:
                return json.loads(rendered)
            except json.JSONDecodeError:
                return rendered
        elif isinstance(template_data, dict):
            result = template_data.copy()
            for key, value in result.items():
                if isinstance(value, str):
                    template = Template(value)
                    result[key] = template.render(**input_data)
            return result
        return template_data
