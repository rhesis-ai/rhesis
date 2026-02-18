"""OpenAPI to JSON Schema utilities for MCP tool definitions.

Resolves ``$ref`` pointers and builds flat input schemas from OpenAPI
operation objects (path/query params + request body fields).
"""

from typing import Any, Dict, List


def resolve_ref(ref: str, openapi_schema: dict) -> dict:
    """Resolve a ``$ref`` like ``#/components/schemas/Foo``."""
    parts = ref.lstrip("#/").split("/")
    result = openapi_schema
    for part in parts:
        result = result.get(part, {})
    return result


def resolve_schema_references(schema: dict, openapi_schema: dict) -> dict:
    """Recursively resolve all ``$ref`` pointers in a JSON Schema.

    Returns a new dict with refs replaced by their resolved content.
    """
    if not isinstance(schema, dict):
        return schema

    if "$ref" in schema:
        resolved = resolve_ref(schema["$ref"], openapi_schema)
        return resolve_schema_references(resolved, openapi_schema)

    result = {}
    for key, value in schema.items():
        if isinstance(value, dict):
            result[key] = resolve_schema_references(value, openapi_schema)
        elif isinstance(value, list):
            result[key] = [
                resolve_schema_references(item, openapi_schema) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def build_input_schema(
    operation: dict,
    openapi_schema: dict,
    yaml_param_overrides: Dict[str, dict],
) -> dict:
    """Build a combined JSON Schema for an MCP tool from OpenAPI.

    Merges path params, query params, and request body fields into
    a single flat ``{"type": "object", "properties": ...}`` schema.
    """
    properties: Dict[str, Any] = {}
    required: List[str] = []

    # Path and query parameters (identified by param["in"])
    for param in operation.get("parameters", []):
        param_in = param.get("in", "")
        if param_in not in ("path", "query"):
            continue

        name = param["name"]
        param_schema = resolve_schema_references(
            param.get("schema", {"type": "string"}), openapi_schema
        )
        prop: Dict[str, Any] = dict(param_schema)

        # Use OpenAPI description, allow YAML override
        description = param.get("description", "")
        if name in yaml_param_overrides:
            description = yaml_param_overrides[name].get("description", description)
        if description:
            prop["description"] = description

        properties[name] = prop

        if param.get("required", param_in == "path"):
            required.append(name)

    # Request body fields (flattened into top-level properties)
    request_body = operation.get("requestBody", {})
    content = request_body.get("content", {}).get("application/json", {})
    body_schema = content.get("schema", {})

    if body_schema:
        body_schema = resolve_schema_references(body_schema, openapi_schema)
        body_props = body_schema.get("properties", {})
        body_required = set(body_schema.get("required", []))

        for field_name, field_schema in body_props.items():
            # Skip fields that collide with path/query params
            if field_name in properties:
                continue

            prop = dict(field_schema)

            # Apply YAML parameter description override
            if field_name in yaml_param_overrides:
                override_desc = yaml_param_overrides[field_name].get("description")
                if override_desc:
                    prop["description"] = override_desc

            properties[field_name] = prop

            if field_name in body_required:
                required.append(field_name)

    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        input_schema["required"] = required
    return input_schema
