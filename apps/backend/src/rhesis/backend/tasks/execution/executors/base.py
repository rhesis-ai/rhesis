"""
Base test executor interface.

Defines the abstract base class for all test executors following the Strategy Pattern.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session


class BaseTestExecutor(ABC):
    """
    Abstract base class for test executors.

    All test executors must implement the execute() method which takes standard
    test execution parameters and returns a standardized result dictionary.

    The Strategy Pattern allows different test types to have completely different
    execution logic while maintaining a consistent interface.
    """

    @abstractmethod
    def execute(
        self,
        db: Session,
        test_config_id: str,
        test_run_id: str,
        test_id: str,
        endpoint_id: str,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Execute a test and return standardized results.

        Args:
            db: Database session
            test_config_id: UUID string of the test configuration
            test_run_id: UUID string of the test run
            test_id: UUID string of the test
            endpoint_id: UUID string of the endpoint
            organization_id: UUID string of the organization (optional)
            user_id: UUID string of the user (optional)
            model: Optional model override for metric evaluation

        Returns:
            Dictionary with standardized structure:
            {
                "test_id": str,
                "execution_time": float (milliseconds),
                "metrics": Dict[str, Any]
            }

        Raises:
            ValueError: If test or required data is not found
            Exception: If execution fails
        """
        pass

