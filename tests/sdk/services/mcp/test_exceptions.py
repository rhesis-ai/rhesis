"""Tests for MCP exception classes."""

import pytest

from rhesis.sdk.services.mcp.exceptions import (
    MCPApplicationError,
    MCPConfigurationError,
    MCPConnectionError,
    MCPError,
    MCPValidationError,
)


@pytest.mark.unit
class TestMCPError:
    """Test base MCPError exception"""

    def test_mcp_error_initialization(self):
        """Test MCPError initialization with all parameters"""
        original_error = ValueError("Original")
        error = MCPError(
            message="Test error",
            category="application",
            status_code=500,
            original_error=original_error,
        )

        assert str(error) == "Test error"
        assert error.category == "application"
        assert error.status_code == 500
        assert error.original_error == original_error

    def test_mcp_error_without_status_code(self):
        """Test MCPError without status code"""
        error = MCPError(message="Test error", category="config", status_code=None)

        assert error.status_code is None

    def test_mcp_error_different_categories(self):
        """Test MCPError with different categories"""
        categories = ["connection", "config", "validation", "application"]
        for category in categories:
            error = MCPError(f"{category} error", category=category)
            assert error.category == category


@pytest.mark.unit
class TestMCPConfigurationError:
    """Test MCPConfigurationError exception"""

    def test_configuration_error_initialization(self):
        """Test MCPConfigurationError initialization"""
        error = MCPConfigurationError("Tool not found")

        assert str(error) == "Tool not found"
        assert error.category == "config"
        assert error.status_code == 404

    def test_configuration_error_with_original_error(self):
        """Test MCPConfigurationError with original error"""
        original = ValueError("Original error")
        error = MCPConfigurationError("Config error", original_error=original)

        assert error.original_error == original


@pytest.mark.unit
class TestMCPValidationError:
    """Test MCPValidationError exception"""

    def test_validation_error_initialization(self):
        """Test MCPValidationError initialization"""
        error = MCPValidationError("Invalid input")

        assert str(error) == "Invalid input"
        assert error.category == "validation"
        assert error.status_code == 422

    def test_validation_error_with_original_error(self):
        """Test MCPValidationError with original error"""
        original = TypeError("Type error")
        error = MCPValidationError("Validation failed", original_error=original)

        assert error.original_error == original


@pytest.mark.unit
class TestMCPApplicationError:
    """Test MCPApplicationError exception"""

    def test_application_error_initialization(self):
        """Test MCPApplicationError initialization"""
        error = MCPApplicationError(status_code=404, detail="Resource not found")

        assert "404" in str(error)
        assert "Resource not found" in str(error)
        assert error.detail == "Resource not found"
        assert error.category == "application"
        assert error.status_code == 404

    def test_application_error_with_original_error(self):
        """Test MCPApplicationError with original error"""
        original = Exception("API error")
        error = MCPApplicationError(status_code=500, detail="Server error", original_error=original)

        assert error.original_error == original
        assert error.status_code == 500

    def test_application_error_different_status_codes(self):
        """Test MCPApplicationError with different status codes"""
        status_codes = [400, 401, 403, 404, 500, 503]
        for status_code in status_codes:
            error = MCPApplicationError(status_code=status_code, detail=f"Error {status_code}")
            assert error.status_code == status_code


@pytest.mark.unit
class TestMCPConnectionError:
    """Test MCPConnectionError exception"""

    def test_connection_error_initialization(self):
        """Test MCPConnectionError initialization"""
        error = MCPConnectionError("Connection failed")

        assert str(error) == "Connection failed"
        assert error.category == "connection"
        assert error.status_code == 503

    def test_connection_error_with_original_error(self):
        """Test MCPConnectionError with original error"""
        original = ConnectionError("Network error")
        error = MCPConnectionError("Connection failed", original_error=original)

        assert error.original_error == original

    def test_connection_error_timeout(self):
        """Test MCPConnectionError for timeout scenarios"""
        error = MCPConnectionError("Connection timeout")

        assert "timeout" in str(error).lower()
        assert error.status_code == 503
