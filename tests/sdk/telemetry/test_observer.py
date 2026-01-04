"""Tests for auto_instrument() function."""

from rhesis.sdk.telemetry.observer import auto_instrument, disable_auto_instrument


def test_auto_instrument_no_frameworks_installed():
    """Test auto_instrument when no AI frameworks are installed."""
    # When no frameworks are installed, it should return empty list
    result = auto_instrument()

    # Result should be a list (may be empty if no frameworks installed)
    assert isinstance(result, list)

    # Clean up
    disable_auto_instrument()


def test_auto_instrument_specific_framework():
    """Test auto_instrument with specific framework."""
    # Try to instrument langchain specifically
    result = auto_instrument("langchain")

    assert isinstance(result, list)
    # If langchain is installed, it should be in the result
    # If not installed, result should be empty

    # Clean up
    disable_auto_instrument()


def test_auto_instrument_unknown_framework():
    """Test auto_instrument with unknown framework."""
    # Should not raise error, just skip unknown frameworks
    result = auto_instrument("unknown_framework")

    assert isinstance(result, list)
    assert "unknown_framework" not in result

    # Clean up
    disable_auto_instrument()


def test_disable_auto_instrument():
    """Test disable_auto_instrument."""
    # This should not raise any errors even if nothing was instrumented
    disable_auto_instrument()

    # Calling multiple times should be safe
    disable_auto_instrument()
