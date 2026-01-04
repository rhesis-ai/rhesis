"""Base integration framework for AI frameworks."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BaseIntegration(ABC):
    """
    Base class for AI framework integrations.

    Each framework integration:
    1. Detects if framework is installed
    2. Creates callback/instrumentor
    3. Enables/disables observation
    """

    def __init__(self):
        """Initialize integration."""
        self._enabled = False
        self._callback = None

    @property
    @abstractmethod
    def framework_name(self) -> str:
        """Return framework name (e.g., 'langchain')."""
        pass

    @abstractmethod
    def is_installed(self) -> bool:
        """Check if framework is installed."""
        pass

    @abstractmethod
    def _create_callback(self) -> Any:
        """Create framework-specific callback/instrumentor."""
        pass

    def enable(self) -> bool:
        """
        Enable observation for this framework.

        Returns:
            True if successfully enabled, False if not installed
        """
        if self._enabled:
            logger.debug(f"{self.framework_name} observation already enabled")
            return True

        if not self.is_installed():
            logger.debug(f"{self.framework_name} not installed")
            return False

        try:
            self._callback = self._create_callback()
            self._enabled = True
            logger.info(f"✓ Observing {self.framework_name}")
            return True
        except Exception as e:
            logger.warning(f"Failed to enable {self.framework_name}: {e}")
            return False

    def disable(self):
        """Disable observation."""
        if self._enabled:
            self._enabled = False
            self._callback = None
            logger.info(f"✗ Stopped observing {self.framework_name}")

    def callback(self) -> Optional[Any]:
        """
        Get callback handler for manual use.

        Automatically enables if not already enabled.

        Returns:
            Framework-specific callback handler
        """
        if not self._enabled:
            self.enable()
        return self._callback

    @property
    def enabled(self) -> bool:
        """Check if observation is enabled."""
        return self._enabled
