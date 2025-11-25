"""Response mapping using Jinja2 templates and JSONPath."""

import json
from typing import Any, Dict

import jsonpath_ng
from jinja2 import Template

from rhesis.backend.logging import logger


class ResponseMapper:
    """Handles response mapping using Jinja2 templates (with optional JSONPath)."""

    def _jsonpath_extract(self, response_data: Dict[str, Any], path: str) -> Any:
        """
        Extract value from response_data using JSONPath.
        Helper function for use within Jinja2 templates.

        Args:
            response_data: Response data to extract from
            path: JSONPath expression

        Returns:
            Extracted value or None if not found
        """
        try:
            jsonpath_expr = jsonpath_ng.parse(path)
            matches = jsonpath_expr.find(response_data)
            return matches[0].value if matches else None
        except Exception as e:
            logger.warning(f"JSONPath extraction failed for '{path}': {str(e)}")
            return None

    def map_response(
        self, response_data: Dict[str, Any], mappings: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Map response data using configured mappings.

        Mappings can be:
        - Pure JSONPath: "$.field.path"
        - Jinja2 template: "{{ field1 or field2 }}"
        - Jinja2 with JSONPath: "{{ jsonpath('$.nested.field') or 'default' }}"

        Args:
            response_data: Raw response data from API
            mappings: Field mappings (output_key -> mapping_expression)

        Returns:
            Mapped response dictionary
        """
        if not mappings:
            return response_data

        result = {}
        for output_key, mapping_value in mappings.items():
            try:
                # Step 1: Render as Jinja2 template with response_data as context
                # Also provide jsonpath() function for extracting nested fields
                template = Template(mapping_value)

                # Build template context: merge response_data fields with jsonpath function
                template_context = dict(response_data)
                template_context["jsonpath"] = lambda path: self._jsonpath_extract(
                    response_data, path
                )

                rendered_value = template.render(**template_context)

                # Step 2: If result starts with '$', treat as JSONPath expression
                if rendered_value.startswith("$"):
                    jsonpath_expr = jsonpath_ng.parse(rendered_value)
                    matches = jsonpath_expr.find(response_data)
                    if matches:
                        result[output_key] = matches[0].value
                    else:
                        # If no match found, set to None
                        result[output_key] = None
                else:
                    # Direct template result (not a JSONPath expression)
                    result[output_key] = rendered_value if rendered_value else None

            except Exception as e:
                logger.warning(
                    f"Failed to map response field '{output_key}' "
                    f"with mapping '{mapping_value}': {str(e)}"
                )
                result[output_key] = None

        # Post-process context field: convert string to list if needed
        if "context" in result and result["context"] is not None:
            result["context"] = self._normalize_context_field(result["context"])

        return result

    def _normalize_context_field(self, context_value: Any) -> Any:
        """
        Normalize context field to ensure it's a list.

        If context is a string:
        1. Try to parse as JSON (in case it's a JSON array string)
        2. If that fails, wrap the string in a list as a single element

        Args:
            context_value: The context value to normalize

        Returns:
            Normalized context value (preferably a list)
        """
        if isinstance(context_value, str):
            # Try to parse as JSON first
            try:
                parsed_context = json.loads(context_value)
                # If it's a list, return it; otherwise wrap in a list
                if isinstance(parsed_context, list):
                    logger.debug(f"Context parsed as JSON list with {len(parsed_context)} items")
                    return parsed_context
                else:
                    logger.debug(
                        f"Context parsed as JSON {type(parsed_context).__name__}, wrapping in list"
                    )
                    return [parsed_context]
            except (json.JSONDecodeError, TypeError):
                # JSON parsing failed, wrap string in list
                logger.debug("Context is string, wrapping in list as single element")
                return [context_value]
        elif isinstance(context_value, list):
            # Already a list, return as-is
            logger.debug(f"Context is already a list with {len(context_value)} items")
            return context_value
        else:
            # Other types (dict, int, etc.), wrap in list
            logger.debug(f"Context is {type(context_value).__name__}, wrapping in list")
            return [context_value]
