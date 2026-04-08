from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint


@dataclass
class InvocationContext:
    """Context object to encapsulate all parameters needed for an endpoint invocation."""

    db: Optional[Session]
    endpoint: Endpoint
    input_data: Dict[str, Any]
    test_execution_context: Optional[Dict[str, str]] = None
    trace_id: Optional[str] = None
