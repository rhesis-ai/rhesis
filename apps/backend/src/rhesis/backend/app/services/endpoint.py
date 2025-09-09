import json
import os
import uuid
from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.services.invokers import create_invoker


class EndpointService:
    """Service for managing and invoking endpoints."""

    def __init__(self, schema_path: str = None):
        """
        Initialize the endpoint service.

        Args:
            schema_path: Optional path to the endpoint schema file. If not provided,
                       defaults to endpoint_schema.json in the same directory.
        """
        self.schema_path = schema_path or os.path.join(
            os.path.dirname(__file__), "endpoint_schema.json"
        )

    def invoke_endpoint(
        self, db: Session, endpoint_id: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Invoke an endpoint with the given input data.

        Args:
            db: Database session
            endpoint_id: ID of the endpoint to invoke
            input_data: Input data to be mapped to the endpoint's request template

        Returns:
            Dict containing the mapped response from the endpoint

        Raises:
            HTTPException: If endpoint is not found or invocation fails
        """
        # Fetch endpoint configuration
        endpoint = self._get_endpoint(db, endpoint_id)

        try:
            # Create appropriate invoker based on protocol
            invoker = create_invoker(endpoint)

            # Invoke the endpoint
            return invoker.invoke(db, endpoint, input_data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def _get_endpoint(self, db: Session, endpoint_id: str) -> Endpoint:
        """
        Get an endpoint by ID.

        Args:
            db: Database session
            endpoint_id: ID of the endpoint to retrieve

        Returns:
            The endpoint configuration

        Raises:
            HTTPException: If endpoint is not found
        """
        endpoint = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
        if not endpoint:
            raise HTTPException(status_code=404, detail="Endpoint not found")
        return endpoint

    def get_schema(self) -> Dict[str, Any]:
        """
        Get the endpoint schema definition.

        Returns:
            Dict containing the input and output schema definitions
        """
        with open(self.schema_path, "r") as f:
            return json.load(f)


# Create a singleton instance of the service
endpoint_service = EndpointService()


def invoke(db: Session, endpoint_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function that uses the singleton EndpointService.

    Args:
        db: Database session
        endpoint_id: ID of the endpoint to invoke
        input_data: Input data to be mapped to the endpoint's request template

    Returns:
        Dict containing the mapped response from the endpoint
    """
    return endpoint_service.invoke_endpoint(db, endpoint_id, input_data)


def get_schema() -> Dict[str, Any]:
    """
    Convenience function that uses the singleton EndpointService.

    Returns:
        Dict containing the input and output schema definitions
    """
    return endpoint_service.get_schema()


# Add main section for command line testing
if __name__ == "__main__":
    import argparse

    from rhesis.backend.app.database import SessionLocal, set_tenant

    parser = argparse.ArgumentParser(description="Test endpoint invocation")
    parser.add_argument("endpoint_id", help="ID of the endpoint to invoke")
    parser.add_argument(
        "--input", "-i", help="Input message", default="Hello, how can you help me?"
    )
    parser.add_argument("--session", "-s", help="Session ID", default=None)
    parser.add_argument("--org-id", "-o", help="Organization ID", required=True)
    parser.add_argument("--user-id", "-u", help="User ID", required=True)

    args = parser.parse_args()

    # Prepare input data
    input_data = {"input": args.input, "session_id": args.session or str(uuid.uuid4())}

    # Create DB session
    db = SessionLocal()
    try:
        # Set tenant context
        set_tenant(db, organization_id=args.org_id, user_id=args.user_id)

        # Invoke endpoint
        # print(f"\nInvoking endpoint {args.endpoint_id} with input: {input_data}")
        # print(f"Using organization ID: {args.org_id}")
        # print(f"Using user ID: {args.user_id}")
        result = invoke(db, args.endpoint_id, input_data)
        # print("\nResponse:")
        # print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"\nError: {str(e)}")
    finally:
        db.close()

"""
Usage examples:

1. Basic usage with required org and user IDs:
python -m rhesis.backend.app.services.endpoint "your-endpoint-id" --org-id "org-uuid" --user-id "user-uuid"

2. With custom input:
python -m rhesis.backend.app.services.endpoint "your-endpoint-id" -i "What's the weather like?" --org-id "org-uuid" --user-id "user-uuid"

3. With all parameters:
python -m rhesis.backend.app.services.endpoint "your-endpoint-id" -i "Hello" -s "custom-session-123" --org-id "org-uuid" --user-id "user-uuid"
"""
