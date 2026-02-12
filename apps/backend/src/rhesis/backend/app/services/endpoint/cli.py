"""Command-line interface for endpoint testing."""

import argparse
import asyncio
import uuid

from rhesis.backend.app.database import get_db

from .service import EndpointService


def main():
    """CLI entry point for testing endpoint invocation."""
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
    input_data = {
        "input": args.input,
        "conversation_id": args.session or str(uuid.uuid4()),
    }

    # Create service and invoke
    service = EndpointService()

    try:
        with get_db() as db:
            result = asyncio.run(
                service.invoke_endpoint(
                    db=db,
                    endpoint_id=args.endpoint_id,
                    input_data=input_data,
                    organization_id=args.org_id,
                    user_id=args.user_id,
                )
            )
            print(result.get("response", result))
    except Exception as e:
        print(f"\nError: {str(e)}")


if __name__ == "__main__":
    main()


"""
Usage examples:

1. Basic usage with required org and user IDs:
python -m rhesis.backend.app.services.endpoint.cli "your-endpoint-id" \\
    --org-id "org-uuid" --user-id "user-uuid"

2. With custom input:
python -m rhesis.backend.app.services.endpoint.cli "your-endpoint-id" \\
    -i "What's the weather like?" --org-id "org-uuid" --user-id "user-uuid"

3. With all parameters:
python -m rhesis.backend.app.services.endpoint.cli "your-endpoint-id" \\
    -i "Hello" -s "custom-session-123" --org-id "org-uuid" --user-id "user-uuid"
"""
