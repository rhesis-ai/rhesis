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

        return self._render_recursive(template_data, render_context)

    def _render_recursive(self, template_data: Any, render_context: Dict[str, Any]) -> Any:
        """
        Recursively render template data, handling nested structures.

        Args:
            template_data: Template data to render (string, dict, list, or other)
            render_context: Data to use in template rendering

        Returns:
            Rendered template data with same structure as input
        """
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
            result = {}
            keys_to_remove = []

            for key, value in template_data.items():
                if isinstance(value, str):
                    template = Template(value)
                    rendered_value = template.render(**render_context)

                    # If the rendered value is the omit marker, mark this key for removal
                    if rendered_value.strip() == "__OMIT_FIELD__":
                        keys_to_remove.append(key)
                    else:
                        # Try to intelligently handle the rendered value
                        result[key] = self._parse_rendered_value(
                            rendered_value, render_context, value
                        )
                else:
                    # Recursively render non-string values (nested dicts, lists, etc.)
                    result[key] = self._render_recursive(value, render_context)

            # Remove keys that had omit markers
            for key in keys_to_remove:
                if key in result:
                    del result[key]
                    logger.debug(f"Omitted field '{key}' from template result")

            return result
        elif isinstance(template_data, list):
            result = []
            for item in template_data:
                result.append(self._render_recursive(item, render_context))
            return result
        else:
            # For other types (int, float, bool, None, etc.), return as-is
            return template_data

    def _parse_rendered_value(
        self, rendered_value: str, render_context: Dict[str, Any], original_template: str
    ) -> Any:
        """
        Parse rendered value intelligently to preserve types.

        If the template is a simple variable reference like "{{ field_name }}" and
        the field value is a complex type (dict, list), preserve it as-is instead
        of converting to string.

        Args:
            rendered_value: The Jinja2-rendered string value
            render_context: The context used for rendering
            original_template: The original template string

        Returns:
            Parsed value (could be dict, list, string, etc.)
        """
        import re

        # Check if template is a simple variable reference: {{ var_name }}
        simple_var_pattern = r"^\{\{\s*(\w+)\s*\}\}$"
        match = re.match(simple_var_pattern, original_template)

        if match:
            var_name = match.group(1)
            if var_name in render_context:
                value = render_context[var_name]

                # Check if value is a Pydantic model - convert to dict for serialization
                if hasattr(value, "model_dump"):
                    logger.debug(
                        f"Converting Pydantic model {type(value).__name__} to dict "
                        f"for template {{ {var_name} }}"
                    )
                    return value.model_dump(exclude_none=True)

                # If the value is a complex type, return it directly
                if isinstance(value, (dict, list)):
                    logger.debug(f"Preserving {type(value).__name__} for template {{ {var_name} }}")
                    return value

        # For non-simple templates or string values, filter and return
        return self._filter_omit_markers(rendered_value)

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
