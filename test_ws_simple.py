#!/usr/bin/env python3
"""
Simple WebSocket invoker test script.

Run from project root:
    cd apps/backend && uv run python ../../test_ws_simple.py
"""

import json
import sys
from pathlib import Path

# Add backend source to path
backend_src = Path(__file__).parent / "apps" / "backend" / "src"
sys.path.insert(0, str(backend_src))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import EndpointAuthType, EndpointProtocol
from rhesis.backend.app.services.invokers.websocket_invoker import WebSocketEndpointInvoker


def create_endpoint() -> Endpoint:
    """Create the Scavenger AI WebSocket endpoint configuration."""
    return Endpoint(
        id="test-ws-endpoint",
        name="Scavenger AI WebSocket Test",
        protocol=EndpointProtocol.WEBSOCKET.value,
        url="wss://api-dev.scavenger-ai.com/llm/chat_with_your_data_ws",
        auth_type=EndpointAuthType.CLIENT_CREDENTIALS.value,
        # OAuth configuration
        token_url="https://auth.scavenger-ai.com/oauth/token",
        client_id="Rk4yMA7bxiZ0AkncHVtTUXm72C3XvR9M",
        client_secret="-fKU0SEEDLJah0m_ICvtX0xb41Ei6nWUD87wgVXFw2w4Cp3s2OGVtI3siZnHsscR",
        audience="https://dev-scavenger-ai.eu.auth0.com/api/v2/",
        # Request body template
        request_body_template="""{
            "session_id": "1ceffe89-dff1-4128-8de5-39dd182a10fa",
            "query": "{{ input }}",
            "auth_token": "{{ auth_token }}",
            "deep_query": false,
            "conversation_id": "{{ conversation_id | tojson }}"
        }""",
        # Response mappings
        response_mappings={
            "conversation_id": "$.conversation_id",
            "output": "{{ jsonpath('$.text_response') or jsonpath('$.sql_query_result') }}",
            "context": "$.table_data",
            "text_response": "$.text_response",
        },
    )


def main():
    """Run a simple WebSocket invocation test."""
    print("=" * 80)
    print("Simple WebSocket Invoker Test")
    print("=" * 80)

    # Create test database session
    engine = create_engine("sqlite:///:memory:", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Create endpoint and invoker
    endpoint = create_endpoint()
    invoker = WebSocketEndpointInvoker()

    # Test input
    input_data = {"input": "What are the available product lines?"}

    print(f"\n📤 Sending: {input_data['input']}")
    print("\n⏳ Invoking endpoint...")

    try:
        result = invoker.invoke(db, endpoint, input_data)

        print("\n" + "=" * 80)
        print("✅ Response received!")
        print("=" * 80)

        # Pretty print result
        print(json.dumps(result, indent=2, default=str))

        # Show key fields
        if result.get("output"):
            print(f"\n📊 SQL Query: {result['output'][:100]}...")
        if result.get("context"):
            context_preview = str(result.get("context"))[:100]
            print(f"📋 Context: {context_preview}...")
        if result.get("conversation_id"):
            print(f"💬 Conversation ID: {result['conversation_id']}")

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {str(e)}")
        return 1

    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
