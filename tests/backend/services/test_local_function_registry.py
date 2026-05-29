"""Tests for backend-resident local function registry."""

from rhesis.backend.app.services.local_function_registry import (
    ensure_local_functions_registered,
    registry,
)


def test_ensure_local_functions_registered_loads_mcp_endpoints():
    ensure_local_functions_registered()
    assert "search_mcp" in registry
    assert "extract_mcp" in registry
    assert "query_mcp" in registry
