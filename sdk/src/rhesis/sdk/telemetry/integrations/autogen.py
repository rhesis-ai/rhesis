"""Legacy Microsoft AutoGen framework integration (placeholder).

AutoGen 0.2 has been folded into the unified Microsoft Agent Framework. New
projects should use the ``agent_framework`` integration in
:mod:`rhesis.sdk.telemetry.integrations.agent_framework` instead -- it covers
the full ``ChatAgent`` / tool / workflow surface MAF exposes today.

This module remains as a no-op placeholder for users still on the legacy
``pyautogen`` package so existing ``auto_instrument("autogen")`` calls don't
fail loudly.
"""

import logging

from rhesis.sdk.telemetry.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class AutoGenIntegration(BaseIntegration):
    """
    Legacy Microsoft AutoGen 0.2 framework integration (no-op placeholder).

    For Microsoft Agent Framework (the unified successor to AutoGen and
    Semantic Kernel) use ``auto_instrument("agent_framework")`` instead.
    """

    @property
    def framework_name(self) -> str:
        return "autogen"

    def is_installed(self) -> bool:
        """Check if AutoGen is installed."""
        try:
            import autogen  # noqa: F401

            return True
        except ImportError:
            return False

    def _create_callback(self):
        """
        Create AutoGen instrumentation.

        Not yet implemented - placeholder for future work.
        """
        logger.warning("AutoGen integration not yet implemented")
        return None


# Singleton instance
_autogen_integration = AutoGenIntegration()


def get_integration() -> AutoGenIntegration:
    """Get the singleton AutoGen integration instance."""
    return _autogen_integration
