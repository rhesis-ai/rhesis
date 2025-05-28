from abc import ABC, abstractmethod
from typing import Any, Dict

from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint


class BaseEndpointInvoker(ABC):
    """Base class for endpoint invokers."""

    @abstractmethod
    def invoke(self, db: Session, endpoint: Endpoint, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke the endpoint with the given input data.

        Args:
            db: Database session
            endpoint: The endpoint to invoke
            input_data: Input data to be mapped to the endpoint's request template

        Returns:
            Dict containing the mapped response from the endpoint
        """
        pass 