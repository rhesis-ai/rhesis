"""Template rendering using Jinja2."""

import json
from typing import Any, Dict

from jinja2 import Template

from rhesis.backend.logging import logger


class TemplateRenderer:
    """Handles template rendering using Jinja2."""

    def render(self, template_data: Any, input_data: Dict[str, Any]) -> Any:
        """
        Render a template with input data.

        Handles conversation tracking fields properly by providing a special marker
        for missing conversation IDs that gets filtered out during JSON processing.

        Args:
            template_data: Template string or dict to render
            input_data: Data to use in template rendering

        Returns:
            Rendered template (parsed as JSON if possible, or as string/dict)
        """
        # Create a copy to avoid modifying the original input_data
        render_context = input_data.copy()

        # For conversation tracking fields that are None or missing, provide a special marker
        # that will be filtered out during JSON processing
        conversation_fields = ["session_id", "conversation_id", "thread_id", "chat_id"]

        # Check if template references any conversation fields
        template_str = (
            json.dumps(template_data) if isinstance(template_data, dict) else str(template_data)
        )

        for field in conversation_fields:
            # Check if this field is referenced in the template
            if f"{field}" in template_str:
                if field not in render_context or render_context[field] is None:
                    # Use a special marker that indicates "omit this field"
                    render_context[field] = "__OMIT_FIELD__"
                    logger.debug(f"Set {field} to omit marker - will be filtered from request")

        if isinstance(template_data, str):
            template = Template(template_data)
            rendered = template.render(**render_context)

            # Filter out omit markers from the rendered string
            rendered = self._filter_omit_markers(rendered)

            try:
                return json.loads(rendered)
            except json.JSONDecodeError:
                return rendered
        elif isinstance(template_data, dict):
            result = template_data.copy()
            keys_to_remove = []

            for key, value in result.items():
                if isinstance(value, str):
                    template = Template(value)
                    rendered_value = template.render(**render_context)

                    # If the rendered value is the omit marker, mark this key for removal
                    if rendered_value.strip() == "__OMIT_FIELD__":
                        keys_to_remove.append(key)
                    else:
                        result[key] = self._filter_omit_markers(rendered_value)

            # Remove keys that had omit markers
            for key in keys_to_remove:
                del result[key]
                logger.debug(f"Omitted field '{key}' from template result")

            return result
        return template_data

    def _filter_omit_markers(self, rendered_str: str) -> str:
        """
        Filter out omit markers from rendered template strings.

        This handles cases like:
        - "field": "__OMIT_FIELD__" -> removes the entire field
        - "__OMIT_FIELD__" -> removes the value
        """
        import re

        # Remove fields with omit markers (handles JSON format)
        # Pattern: "field_name": "__OMIT_FIELD__",?
        rendered_str = re.sub(r'"[^"]*":\s*"__OMIT_FIELD__",?\s*', "", rendered_str)

        # Remove standalone omit markers
        rendered_str = rendered_str.replace('"__OMIT_FIELD__"', "null")
        rendered_str = rendered_str.replace("__OMIT_FIELD__", "null")

        # Clean up trailing commas that might be left behind
        rendered_str = re.sub(r",\s*}", "}", rendered_str)
        rendered_str = re.sub(r",\s*]", "]", rendered_str)

        return rendered_str
