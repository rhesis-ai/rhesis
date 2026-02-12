"""Core endpoint service with basic operations."""

import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.models.enums import (
    EndpointAuthType,
    EndpointConfigSource,
    EndpointConnectionType,
    EndpointEnvironment,
    EndpointResponseFormat,
)
from rhesis.backend.app.schemas.endpoint import EndpointTestRequest
from rhesis.backend.app.services.invokers import create_invoker
from rhesis.backend.app.services.invokers.conversation import (
    CONVERSATION_FIELD_NAMES,
    ConversationTracker,
    get_conversation_store,
)

# Import sdk_sync at module level to avoid circular imports
from . import sdk_sync

logger = logging.getLogger(__name__)


class EndpointService:
    """Service for managing and invoking endpoints."""

    def __init__(self, schema_path: str = None):
        """
        Initialize the endpoint service.

        Args:
            schema_path: Optional path to the endpoint schema file. If not provided,
                       defaults to endpoint_schema.json in the parent services directory.
        """
        if schema_path:
            self.schema_path = schema_path
        else:
            # Look for endpoint_schema.json in the parent services directory
            services_dir = os.path.dirname(os.path.dirname(__file__))
            self.schema_path = os.path.join(services_dir, "endpoint_schema.json")

    async def invoke_endpoint(
        self,
        db: Session,
        endpoint_id: str,
        input_data: Dict[str, Any],
        organization_id: str = None,
        user_id: str = None,
        test_execution_context: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Invoke an endpoint with the given input data.

        Args:
            db: Database session
            endpoint_id: ID of the endpoint to invoke
            input_data: Input data to be mapped to the endpoint's request template
            organization_id: Organization ID for security filtering (CRITICAL)
            user_id: User ID for context injection (CRITICAL - injected into
                headers, not from user input)
            test_execution_context: Optional dict with test_run_id, test_result_id, test_id
                                   for linking traces to test executions

        Returns:
            Dict containing the mapped response from the endpoint

        Raises:
            HTTPException: If endpoint is not found or invocation fails
        """
        # Fetch endpoint configuration with organization filtering (SECURITY CRITICAL)
        endpoint = self._get_endpoint(db, endpoint_id, organization_id)
        logger.debug(f"Invoking endpoint {endpoint.name} ({endpoint.connection_type})")

        try:
            # Create appropriate invoker based on connection_type
            invoker = create_invoker(endpoint)

            # Inject organization_id and user_id into input_data for context
            # These are injected by the backend, NOT from user input (SECURITY CRITICAL)
            enriched_input_data = input_data.copy()
            if organization_id:
                enriched_input_data["organization_id"] = organization_id
            if user_id:
                enriched_input_data["user_id"] = user_id

            # -------------------------------------------------------
            # Stateless conversation management
            # -------------------------------------------------------
            # For stateless endpoints (detected via {{ messages }} in
            # request_mapping) the backend manages conversation history
            # server-side.  Callers use ``conversation_id`` exactly like
            # they would for stateful endpoints -- the difference is
            # transparent.
            #
            # Two-phase commit: the user message is appended to a
            # *temporary* messages list for the request body, but is
            # only committed to the store after a successful invocation.
            # This avoids leaving the conversation in an inconsistent
            # state when the external endpoint returns an error.
            is_stateless = ConversationTracker.detect_stateless_mode(endpoint)
            stateless_conversation_id = None
            stateless_user_input = None

            if is_stateless and "messages" not in enriched_input_data:
                store = get_conversation_store()
                incoming_cid = enriched_input_data.get("conversation_id")
                stateless_user_input = enriched_input_data.get("input", "")

                if incoming_cid and store.exists(incoming_cid):
                    # Continue existing conversation
                    stateless_conversation_id = incoming_cid
                else:
                    # New conversation (or expired -- start fresh)
                    system_prompt = ConversationTracker.extract_system_prompt(endpoint)
                    stateless_conversation_id = store.create(
                        system_prompt=system_prompt,
                    )
                    if incoming_cid:
                        logger.warning(
                            f"Conversation {incoming_cid} not found, "
                            f"created new: {stateless_conversation_id}"
                        )

                # Build the messages array WITHOUT committing to the
                # store yet.  get_messages() returns a deep copy, so
                # appending to it is safe.
                messages = store.get_messages(
                    stateless_conversation_id,
                )
                if stateless_user_input:
                    messages.append({"role": "user", "content": stateless_user_input})
                enriched_input_data["messages"] = messages

                # Remove conversation_id from the data that goes to the
                # template renderer -- it's an internal tracking field,
                # not a value to render into the external request body.
                # Without this, the renderer's alias propagation would
                # fill {{ session_id }} (or similar) in the request
                # mapping and leak the internal ID to the external API.
                enriched_input_data.pop("conversation_id", None)

                logger.debug(
                    "Stateless conversation %s: %d message(s)",
                    stateless_conversation_id,
                    len(messages),
                )

            # Preprocess prompt placeholders (e.g., Garak's {TARGET_MODEL})
            # This substitutes placeholders with runtime context like project name
            if "input" in enriched_input_data and isinstance(enriched_input_data["input"], str):
                from rhesis.backend.app.services.prompt_preprocessor import (
                    prompt_preprocessor,
                )

                enriched_input_data["input"] = prompt_preprocessor.process(
                    enriched_input_data["input"],
                    endpoint=endpoint,
                )

            # Check if invoker needs explicit tracing (REST/WebSocket)
            if not invoker.automatic_tracing:
                # Import here to avoid circular imports
                from rhesis.backend.app.services.invokers.tracing import (
                    create_invocation_trace,
                )

                # Wrap invocation with trace creation
                async with create_invocation_trace(
                    db, endpoint, organization_id, test_execution_context
                ) as trace_ctx:
                    result = await invoker.invoke(
                        db, endpoint, enriched_input_data, test_execution_context
                    )
                    trace_ctx["result"] = result
            else:
                # SDK invoker - handles tracing internally
                result = await invoker.invoke(
                    db, endpoint, enriched_input_data, test_execution_context
                )

            # -------------------------------------------------------
            # Post-invocation: commit messages for stateless on success
            # -------------------------------------------------------
            if is_stateless and stateless_conversation_id and result:
                result_dict = result if isinstance(result, dict) else None
                if result_dict is not None:
                    store = get_conversation_store()
                    # Phase 2: commit the user turn now that we know
                    # the invocation succeeded.
                    if stateless_user_input:
                        store.add_user_message(
                            stateless_conversation_id,
                            stateless_user_input,
                        )
                    # Commit the assistant turn.
                    output = result_dict.get("output", "")
                    if output:
                        store.add_assistant_message(
                            stateless_conversation_id,
                            str(output),
                        )
                    # Surface conversation_id so callers can continue
                    # the conversation -- same field stateful endpoints
                    # use.
                    result_dict["conversation_id"] = stateless_conversation_id

            # -------------------------------------------------------
            # Guarantee conversation_id in every dict response
            # -------------------------------------------------------
            # For stateful endpoints the invoker may have already
            # placed a conversation field in the result (extracted
            # from the external API via response_mapping, or echoed
            # from the request).  If no recognised field is present,
            # we echo back the caller's conversation_id so the chain
            # is never broken.
            if (
                not is_stateless
                and isinstance(result, dict)
                and not any(f in result for f in CONVERSATION_FIELD_NAMES)
            ):
                incoming_cid = input_data.get("conversation_id")
                if incoming_cid:
                    result["conversation_id"] = incoming_cid

            logger.debug(f"Endpoint invocation completed: {endpoint.name}")
            return result
        except ValueError as e:
            logger.error(f"ValueError invoking endpoint: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Exception invoking endpoint: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    def _get_endpoint(self, db: Session, endpoint_id: str, organization_id: str = None) -> Endpoint:
        """
        Get an endpoint by ID with organization filtering.

        Args:
            db: Database session
            endpoint_id: ID of the endpoint to retrieve
            organization_id: Organization ID for security filtering (CRITICAL)

        Returns:
            The endpoint configuration

        Raises:
            HTTPException: If endpoint is not found or not accessible
        """
        query = db.query(Endpoint).filter(Endpoint.id == endpoint_id)

        # Apply organization filtering if provided (SECURITY CRITICAL)
        if organization_id:
            from uuid import UUID

            query = query.filter(Endpoint.organization_id == UUID(organization_id))

        endpoint = query.first()
        if not endpoint:
            raise HTTPException(status_code=404, detail="Endpoint not found or not accessible")
        return endpoint

    def get_schema(self) -> Dict[str, Any]:
        """
        Get the endpoint schema definition.

        Returns:
            Dict containing the input and output schema definitions
        """
        with open(self.schema_path, "r") as f:
            return json.load(f)

    async def test_endpoint(
        self,
        db: Session,
        test_config: EndpointTestRequest,
        organization_id: str = None,
        user_id: str = None,
    ) -> Dict[str, Any]:
        """
        Test an endpoint configuration without saving it to the database.

        Args:
            db: Database session (required for invoker, but no writes occur)
            test_config: Endpoint test configuration
            organization_id: Organization ID for context injection (CRITICAL)
            user_id: User ID for context injection (CRITICAL - injected into
                headers, not from user input)

        Returns:
            Dict containing the mapped response from the endpoint

        Raises:
            HTTPException: If configuration is invalid or invocation fails
        """

        # Validate connection_type and auth_type (schema validation should catch this,
        # but double-check for safety)
        # Helper function to safely get enum value
        def get_enum_value(enum_or_str, expected_enum_class):
            """Safely extract value from enum or return string."""
            if hasattr(enum_or_str, "value"):
                return enum_or_str.value
            return str(enum_or_str)

        connection_type_str = get_enum_value(test_config.connection_type, EndpointConnectionType)
        auth_type_str = get_enum_value(test_config.auth_type, EndpointAuthType)
        response_format_str = get_enum_value(test_config.response_format, EndpointResponseFormat)

        if connection_type_str != EndpointConnectionType.REST.value:
            raise HTTPException(
                status_code=400,
                detail=f"Only REST endpoints are supported for testing. Got: {connection_type_str}",
            )

        if auth_type_str != EndpointAuthType.BEARER_TOKEN.value:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only BEARER_TOKEN authentication is supported for testing. "
                    f"Got: {auth_type_str}"
                ),
            )

        logger.debug(f"Testing endpoint configuration: {test_config.url} ({connection_type_str})")

        try:
            # Create a temporary Endpoint object (not saved to DB)
            # Set required fields from test_config and defaults for non-test fields
            endpoint = Endpoint(
                name="test",  # Temporary name for testing
                connection_type=connection_type_str,
                url=test_config.url,
                method=test_config.method,
                endpoint_path=test_config.endpoint_path,
                request_headers=test_config.request_headers,
                query_params=test_config.query_params,
                request_mapping=test_config.request_mapping,
                response_mapping=test_config.response_mapping,
                response_format=response_format_str,
                auth_type=auth_type_str,
                auth_token=test_config.auth_token,
                environment=EndpointEnvironment.DEVELOPMENT.value,
                config_source=EndpointConfigSource.MANUAL.value,
            )

            # Create appropriate invoker based on connection_type
            invoker = create_invoker(endpoint)

            # Inject organization_id and user_id into input_data for context
            # These are injected by the backend, NOT from user input (SECURITY CRITICAL)
            enriched_input_data = test_config.input_data.copy()
            if organization_id:
                enriched_input_data["organization_id"] = organization_id
            if user_id:
                enriched_input_data["user_id"] = user_id

            # Invoke the endpoint
            result = await invoker.invoke(db, endpoint, enriched_input_data)
            logger.debug("Endpoint test invocation completed")
            return result
        except ValueError as e:
            logger.error(f"ValueError testing endpoint: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Exception testing endpoint: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    async def sync_sdk_endpoints(
        self,
        db: Session,
        project_id: str,
        environment: str,
        functions_data: list,
        organization_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Sync SDK endpoints - create/update/mark inactive as needed.

        This is a convenience method that delegates to the sdk_sync module.

        Args:
            db: Database session
            project_id: Project identifier
            environment: Environment name
            functions_data: List of function metadata from SDK
            organization_id: Organization ID
            user_id: User ID

        Returns:
            Dict with sync statistics (created, updated, marked_inactive counts)
        """
        return await sdk_sync.sync_sdk_endpoints(
            db=db,
            project_id=project_id,
            environment=environment,
            functions_data=functions_data,
            organization_id=organization_id,
            user_id=user_id,
        )
