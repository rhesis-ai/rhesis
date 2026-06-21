"""Merge partial credential updates with stored tool credentials."""

import json


def merge_gitlab_credentials_on_update(
    existing_credentials_json: str,
    incoming_credentials: dict[str, str],
) -> dict[str, str]:
    """Preserve GITLAB_API_URL when PATCH or test-connection updates only the token."""
    merged = dict(incoming_credentials)
    if merged.get("GITLAB_API_URL", "").strip():
        return merged

    try:
        existing_credentials = json.loads(existing_credentials_json)
    except (json.JSONDecodeError, TypeError):
        return merged

    if not isinstance(existing_credentials, dict):
        return merged

    existing_api_url = existing_credentials.get("GITLAB_API_URL")
    if isinstance(existing_api_url, str) and existing_api_url.strip():
        merged["GITLAB_API_URL"] = existing_api_url.strip()

    return merged


def merge_azure_devops_credentials_on_update(
    existing_credentials_json: str,
    incoming_credentials: dict[str, str],
) -> dict[str, str]:
    """Preserve org/email when PATCH or test-connection updates only the PAT."""
    merged = dict(incoming_credentials)

    try:
        existing_credentials = json.loads(existing_credentials_json)
    except (json.JSONDecodeError, TypeError):
        return merged

    if not isinstance(existing_credentials, dict):
        return merged

    for key in ("AZURE_DEVOPS_ORG", "AZURE_DEVOPS_EMAIL"):
        if not merged.get(key, "").strip():
            existing_value = existing_credentials.get(key)
            if isinstance(existing_value, str) and existing_value.strip():
                merged[key] = existing_value.strip()

    return merged


def resolve_mcp_test_connection_credentials(
    provider: str,
    existing_credentials_json: str,
    incoming_credentials: dict[str, str],
) -> dict[str, str]:
    """Fill missing credential fields from a saved tool before MCP health check."""
    if provider == "azure_devops":
        return merge_azure_devops_credentials_on_update(
            existing_credentials_json, incoming_credentials
        )
    if provider == "gitlab":
        return merge_gitlab_credentials_on_update(existing_credentials_json, incoming_credentials)
    return dict(incoming_credentials)
