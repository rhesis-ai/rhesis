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


def test_auto_instrument_dedupes_repeated_calls():
    """Repeated ``auto_instrument`` calls must not duplicate the bookkeeping list.

    Each integration is a singleton, so calling ``auto_instrument`` twice (e.g.
    after an app reload) should leave at most one entry per integration in the
    internal ``_instrumented_frameworks`` list. Otherwise
    ``disable_auto_instrument`` ends up calling ``disable()`` on the same
    integration N times.
    """
    from rhesis.sdk.telemetry import observer as observer_mod

    disable_auto_instrument()
    assert observer_mod._instrumented_frameworks == []

    # Two back-to-back calls with the same explicit framework name.
    auto_instrument("langchain")
    first_snapshot = list(observer_mod._instrumented_frameworks)
    auto_instrument("langchain")
    second_snapshot = list(observer_mod._instrumented_frameworks)

    # Identity-aware: each integration appears at most once regardless of how
    # many times ``auto_instrument`` is called. (Also covers the no-frameworks
    # case where both snapshots are simply ``[]``.)
    for integration in second_snapshot:
        assert second_snapshot.count(integration) == 1, (
            f"integration {integration!r} appears more than once after repeated "
            f"auto_instrument calls: {second_snapshot!r}"
        )
    # Length must not grow on the second call.
    assert len(second_snapshot) == len(first_snapshot)

    disable_auto_instrument()
