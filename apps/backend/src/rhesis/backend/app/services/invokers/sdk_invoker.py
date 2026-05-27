"""SDK endpoint invoker for WebSocket-connected SDK functions."""

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Union

from fastapi import HTTPException

from rhesis.backend.app.constants import TestExecutionContext as TestContextConstants
from rhesis.backend.app.schemas.test_execution import TestExecutionContext
from rhesis.telemetry.constants import ConversationContext as ConversationConstants

from .base import BaseEndpointInvoker
from .common.schemas import ErrorResponse
from .context import InvocationContext

logger = logging.getLogger(__name__)

# SDK function execution timeout in seconds
# Configurable via environment variable for long-running LLM operations
SDK_FUNCTION_TIMEOUT = float(os.environ.get("SDK_FUNCTION_TIMEOUT", "120.0"))


class SdkEndpointInvoker(BaseEndpointInvoker):
    """Invoker for SDK-connected endpoints via WebSocket."""

    # SDK endpoints automatically generate traces via instrumentation
    automatic_tracing: bool = True

    def __init__(self, context: "InvocationContext | None" = None):
        """Initialize SDK invoker."""
        super().__init__(context)

    def _validate_and_extract_metadata(self) -> tuple[str, str, str]:
        """Validate endpoint and extract SDK metadata.

        Returns:
            Tuple of (function_name, project_id, environment)

        Raises:
            HTTPException: If metadata is missing or invalid
        """
        endpoint = self.context.endpoint
        if not endpoint.endpoint_metadata:
            raise HTTPException(
                status_code=500,
                detail="SDK endpoint missing metadata (function_name, project_id, environment)",
            )

        sdk_connection = endpoint.endpoint_metadata.get("sdk_connection", {})
        function_name = sdk_connection.get("function_name")
        project_id = endpoint.project_id
        environment = endpoint.environment

        if not all([function_name, project_id, environment]):
            raise HTTPException(
                status_code=500,
                detail=(
                    f"SDK endpoint incomplete: function_name={function_name}, "
                    f"project_id={project_id}, environment={environment}"
                ),
            )

        return function_name, str(project_id), environment

    def _determine_invocation_context(self, project_id: str, environment: str) -> tuple[bool, str]:
        """
        Determine whether to use RPC or direct WebSocket.

        Args:
            project_id: Project identifier
            environment: Environment name

        Returns:
            Tuple of (use_rpc, context_type_description)
        """
        is_worker = os.getenv("CELERY_WORKER_NAME") is not None

        from rhesis.backend.app.services.connector.manager import connection_manager

        has_local_connection = connection_manager.has_local_route(project_id, environment)

        # Determine invocation method:
        # - Workers: always use RPC (they never have WebSocket connections)
        # - Backend with local connection: use direct WebSocket
        # - Backend without local connection: use RPC (connection on another instance)
        use_rpc = is_worker or not has_local_connection

        if is_worker:
            context_type = "WORKER (RPC via Redis)"
        elif has_local_connection:
            context_type = "BACKEND (direct WebSocket connection)"
        else:
            context_type = "BACKEND (RPC via Redis - connection on another instance)"

        return use_rpc, context_type

    # Platform-internal keys that must not leak as function kwargs in
    # passthrough mode (no request_mapping).  When a request_mapping IS
    # present these keys are still available in the Jinja template context
    # (e.g. ``{{ params.model }}``, ``{{ test_id }}``).
    _PLATFORM_CONTEXT_KEYS: set = {
        "organization_id",
        "user_id",
        "params",
        "files_metadata",
    }

    def _strip_user_rhesis_keys(self, function_kwargs: Dict[str, Any]) -> None:
        """Remove user-supplied _rhesis_* keys to prevent injection."""
        for key in [k for k in function_kwargs if k.startswith("_rhesis_")]:
            function_kwargs.pop(key)

    def _prepare_function_kwargs(self, function_name: str) -> Dict[str, Any]:
        """Prepare function kwargs from input data using request mapping.

        Experiment parameters are available in the Jinja template context
        as ``params``, so request mappings can reference individual values
        with ``{{ params.model }}``, ``{{ params.temperature }}``, etc. --
        the same syntax used for REST endpoints.

        Args:
            function_name: Name of the function (for logging)

        Returns:
            Transformed function kwargs ready to send to SDK
        """
        endpoint = self.context.endpoint
        input_data = self.context.input_data
        # Prepare conversation context
        template_context, _ = self._prepare_conversation_context(endpoint, input_data)

        # Transform using request_mapping
        request_mapping = endpoint.request_mapping or {}

        if not request_mapping:
            logger.warning(f"No request_mapping configured for {function_name}, using passthrough")
            return {
                k: v for k, v in template_context.items() if k not in self._PLATFORM_CONTEXT_KEYS
            }

        # Full context (including params) available for Jinja rendering
        rendered = self.template_renderer.render(request_mapping, template_context)

        # Strip reserved meta keys (e.g. system_prompt) from the wire body
        self._strip_meta_keys(rendered)

        return rendered

    def _connector_parameter_extras(self) -> Dict[str, Any]:
        """Load resolved-parameter snapshot from the active test run, if any."""
        from uuid import UUID

        from rhesis.backend.app import crud
        from rhesis.backend.app.services.experiment import (
            connector_execute_extras_from_run_attributes,
        )

        ctx = self.context.test_execution_context or {}
        tr_id = ctx.get("test_run_id")
        db = self.context.db
        if not tr_id or db is None:
            return {}
        org = str(self.context.endpoint.organization_id)
        run = crud.get_test_run(db, UUID(str(tr_id)), organization_id=org, user_id=None)
        if run is None:
            return {}
        return connector_execute_extras_from_run_attributes(run.attributes)

    async def _execute_via_rpc(
        self,
        project_id: str,
        environment: str,
        test_run_id: str,
        function_name: str,
        function_kwargs: Dict[str, Any],
        execute_extras: Dict[str, Any] | None = None,
    ) -> Union[Dict[str, Any], ErrorResponse]:
        """
        Execute SDK function via RPC (Redis pub/sub).

        Args:
            project_id: Project identifier
            environment: Environment name
            test_run_id: Unique test run ID
            function_name: Function to invoke
            function_kwargs: Function arguments

        Returns:
            Result dictionary from SDK, or ErrorResponse if RPC unavailable or not connected
        """
        from rhesis.backend.app.services.connector.rpc_client import get_rpc_client

        try:
            rpc_client = await get_rpc_client()
        except RuntimeError as e:
            logger.error(f"Failed to initialize RPC client: {e}")
            return self._create_error_response(
                error_type="sdk_rpc_unavailable",
                output_message=(
                    "Cannot invoke SDK: Redis not configured for multi-instance deployment"
                ),
                message=str(e),
                request_details=self._safe_request_details(locals(), "SDK"),
            )

        # Check connection via RPC client (checks Redis)
        is_connected = await rpc_client.is_connected(project_id, environment)

        if not is_connected:
            logger.warning(f"SDK not connected: {project_id}:{environment}")
            return self._create_error_response(
                error_type="sdk_not_connected",
                output_message=f"SDK not connected: {project_id} in {environment}",
                message="SDK client is not currently connected",
                request_details=self._safe_request_details(locals(), "SDK"),
            )

        # Send request via RPC — client is thread-local and stays open for reuse
        return await rpc_client.send_and_await_result(
            project_id=project_id,
            environment=environment,
            test_run_id=test_run_id,
            function_name=function_name,
            inputs=function_kwargs,
            timeout=SDK_FUNCTION_TIMEOUT,
            execute_extras=execute_extras,
        )

    async def _execute_via_websocket(
        self,
        project_id: str,
        environment: str,
        test_run_id: str,
        function_name: str,
        function_kwargs: Dict[str, Any],
        execute_extras: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Execute SDK function via direct WebSocket connection.

        Args:
            project_id: Project identifier
            environment: Environment name
            test_run_id: Unique test run ID
            function_name: Function to invoke
            function_kwargs: Function arguments

        Returns:
            Result dictionary from SDK
        """
        from rhesis.backend.app.services.connector.manager import connection_manager

        return await connection_manager.send_and_await_result(
            project_id=project_id,
            environment=environment,
            test_run_id=test_run_id,
            function_name=function_name,
            inputs=function_kwargs,
            timeout=SDK_FUNCTION_TIMEOUT,
            execute_extras=execute_extras,
        )

    def _check_result_errors(
        self, result: Dict[str, Any], function_name: str
    ) -> Union[ErrorResponse, None]:
        """
        Check result for errors and return ErrorResponse if found.

        Args:
            result: Result dictionary from SDK execution
            function_name: Name of the function (for logging)

        Returns:
            ErrorResponse if error found, None otherwise
        """
        # Check if SDK is disconnected
        if result.get("error") == "sdk_disconnected":
            return self._create_error_response(
                error_type="sdk_disconnected",
                output_message="SDK is not connected",
                message=result.get("details", "SDK connection not available"),
                request_details=self._safe_request_details(locals(), "SDK"),
            )

        # Check if request failed to send
        if result.get("error") == "send_failed":
            return self._create_error_response(
                error_type="sdk_send_failed",
                output_message="Failed to send request to SDK",
                message=result.get("details", "Unknown error"),
                request_details=self._safe_request_details(locals(), "SDK"),
            )

        # Check if timeout occurred
        if result.get("error") == "timeout":
            return self._create_error_response(
                error_type="sdk_timeout",
                output_message="SDK function execution timed out",
                message=f"Function did not respond within {SDK_FUNCTION_TIMEOUT} seconds",
                request_details=self._safe_request_details(locals(), "SDK"),
            )

        # Check if SDK function returned error
        if result.get("status") == "error":
            return self._create_error_response(
                error_type="sdk_function_error",
                output_message=f"SDK function error: {result.get('error', 'Unknown error')}",
                message=result.get("error", "Function execution failed"),
                request_details=self._safe_request_details(locals(), "SDK"),
                duration_ms=result.get("duration_ms"),
            )

        return None

    def _map_sdk_response(self, result: Dict[str, Any], function_name: str) -> Dict[str, Any]:
        """Map SDK output to standardized response format.

        Args:
            result: Raw result from SDK
            function_name: Name of the function (for logging)

        Returns:
            Mapped response dictionary
        """
        endpoint = self.context.endpoint
        raw_output = result.get("output", {})
        logger.debug(f"Raw SDK output: {raw_output}")

        response_mapping = endpoint.response_mapping or {}

        if not response_mapping:
            logger.warning(f"No response_mapping configured for {function_name}, using raw output")
            return {"output": raw_output}

        return self.response_mapper.map_response(raw_output, response_mapping)

    def _ensure_conversation_field(
        self,
        mapped_response: Dict[str, Any],
        conversation_field: Optional[str],
    ) -> None:
        """Ensure the conversation tracking field is present in the response.

        If the response_mapping already extracted a value, keep it.
        Otherwise fall back to the value from the request so the
        caller can continue the conversation on the next turn.

        Args:
            mapped_response: Mapped response dictionary (mutated in place)
            conversation_field: Field name for conversation tracking
        """
        input_data = self.context.input_data
        if not conversation_field:
            return

        if conversation_field in mapped_response:
            logger.info(f"Extracted {conversation_field}: {mapped_response[conversation_field]}")
            return

        # Fall back to request value so the chain isn't broken
        fallback = input_data.get(conversation_field)
        if fallback:
            mapped_response[conversation_field] = fallback
            logger.debug(f"Echoed {conversation_field} from request: {fallback}")

    def _resolve_conversation_trace_context(
        self,
        conversation_field: Optional[str],
    ) -> tuple[Optional[str], Optional[str], str]:
        """Resolve the trio that drives conversation-coherent tracing.

        Returns ``(conversation_id, existing_trace_id, mapped_input)``:

        * ``conversation_id`` -- read from input_data using the endpoint's
          configured field name, falling back to recognised aliases.
        * ``existing_trace_id`` -- the trace_id of Turn 1 for that
          conversation, so the SDK tracer can reuse it on subsequent turns.
          Looked up first from the DB and then from the in-flight pending
          links cache (covers the window between Turn 1's invocation and
          Turn 1's span ingest).
        * ``mapped_input`` -- the rendered user input, stamped on the root
          span as ``rhesis.conversation.input``.

        Pure lookup: does not mutate kwargs or write to ContextVars.  Used
        by both the WebSocket path (which injects the trio into
        ``function_kwargs``) and the local registry path (which threads
        them through SDK telemetry ContextVars directly).
        """
        db = self.context.db
        endpoint = self.context.endpoint
        input_data = self.context.input_data
        trace_id = self.context.trace_id

        from .conversation import find_conversation_id

        # Prefer the endpoint's configured field name (from response_mapping),
        # then fall back to scanning all recognized field names.
        if conversation_field and conversation_field in input_data:
            conversation_id = input_data[conversation_field]
        else:
            conversation_id = find_conversation_id(input_data)

        mapped_input = str(input_data.get("input", ""))

        existing_trace_id: Optional[str] = None
        if conversation_id and endpoint.project_id:
            existing_trace_id = trace_id

            if existing_trace_id is None and db is not None:
                # Lazy import: crud uses models that would cause a circular
                # import at module level.
                from rhesis.backend.app import crud

                existing_trace_id = crud.get_trace_id_for_conversation(
                    db=db,
                    conversation_id=conversation_id,
                    project_id=str(endpoint.project_id),
                    organization_id=str(endpoint.organization_id),
                )

                # Fallback: if Turn 1's spans haven't been ingested yet,
                # the trace_id is still in the pending links cache from
                # _link_first_turn_trace().
                if existing_trace_id is None:
                    from rhesis.backend.app.services.telemetry.conversation_linking import (
                        get_trace_id_from_pending_links,
                    )

                    existing_trace_id = get_trace_id_from_pending_links(conversation_id)
                    if existing_trace_id:
                        logger.debug(
                            f"Found trace_id from pending links cache: {existing_trace_id}"
                        )

        return conversation_id, existing_trace_id, mapped_input

    def _inject_conversation_context(
        self,
        conversation_field: Optional[str],
        function_kwargs: Dict[str, Any],
    ) -> Optional[str]:
        """Inject conversation context into ``function_kwargs`` (WebSocket/RPC path).

        The SDK connector executor pops ``ConversationConstants.CONTEXT_KEY``
        from kwargs and writes it into SDK telemetry ContextVars so the
        tracer reuses ``existing_trace_id`` for the root span.

        Returns the resolved ``conversation_id`` (or ``None`` for first turn).
        """
        endpoint = self.context.endpoint
        conversation_id, existing_trace_id, mapped_input = (
            self._resolve_conversation_trace_context(conversation_field)
        )

        if conversation_id and endpoint.project_id:
            function_kwargs[ConversationConstants.CONTEXT_KEY] = {
                ConversationConstants.Fields.CONVERSATION_ID: conversation_id,
                ConversationConstants.Fields.TRACE_ID: existing_trace_id,
                ConversationConstants.Fields.MAPPED_INPUT: mapped_input,
            }
            logger.debug(
                f"Injected conversation context: id={conversation_id}, trace_id={existing_trace_id}"
            )
        elif endpoint.project_id:
            # First turn: no conversation_id yet, but still send
            # mapped_input so the SDK tracer stamps it on the span.
            function_kwargs[ConversationConstants.CONTEXT_KEY] = {
                ConversationConstants.Fields.MAPPED_INPUT: mapped_input,
            }

        return conversation_id

    @staticmethod
    @asynccontextmanager
    async def _local_telemetry_context(
        conv_id: Optional[str],
        conv_trace_id: Optional[str],
        mapped_input: str,
    ):
        """Thread conversation context into SDK telemetry ContextVars.

        Mirrors what ``sdk/rhesis/sdk/connector/executor.py`` does around
        the user function on the WebSocket path.  The SDK tracer reads
        ``get_conversation_trace_id()`` and reuses it as the root span's
        trace_id; without this, every local turn would generate a fresh
        trace_id and the "link traces" tasks would never fire.

        Resets ``_root_trace_id`` on enter so the inner ``@endpoint``
        tracer treats this call as the root span.  Clears all four
        ContextVars on exit so they do not leak into subsequent calls
        sharing the same async Task.
        """
        from rhesis.sdk.telemetry.context import (
            set_conversation_id,
            set_conversation_mapped_input,
            set_conversation_trace_id,
            set_root_trace_id,
        )

        if conv_id:
            set_conversation_id(conv_id)
        if conv_trace_id:
            set_conversation_trace_id(conv_trace_id)
        if mapped_input:
            set_conversation_mapped_input(mapped_input)
        set_root_trace_id(None)
        try:
            yield
        finally:
            set_conversation_id(None)
            set_conversation_trace_id(None)
            set_conversation_mapped_input(None)
            set_root_trace_id(None)

    def _park_mapped_output(
        self,
        result: Dict[str, Any],
        mapped_response: Dict[str, Any],
    ) -> None:
        """Park the response-mapped output for injection at span ingest time.

        The SDK tracer sets ``rhesis.conversation.input`` per-span, but cannot
        set ``rhesis.conversation.output`` because it only has the raw function
        return value.  We park the mapped output here; it will be injected into
        the span's attributes when the SDK exports it to the telemetry ingest
        endpoint — before storage.
        """
        endpoint = self.context.endpoint
        raw_output = mapped_response.get("output", "")
        if isinstance(raw_output, (dict, list)):
            mapped_output = json.dumps(raw_output)
        else:
            mapped_output = str(raw_output) or None
        if result.get("trace_id") and endpoint.project_id and mapped_output:
            from rhesis.backend.app.services.telemetry.conversation_linking import (
                register_pending_output,
            )

            register_pending_output(
                trace_id=result["trace_id"],
                mapped_output=mapped_output,
            )

    def _park_input_files(
        self,
        result: Dict[str, Any],
    ) -> None:
        """Park input files for creation when SDK spans arrive.

        Files are available at invocation time but the SDK trace record
        hasn't been created yet (spans arrive asynchronously via
        ``BatchSpanProcessor``).  We park the file metadata here; File
        records will be created and linked to the stored Trace when
        the spans arrive at the telemetry ingest endpoint — after storage.
        """
        endpoint = self.context.endpoint
        input_data = self.context.input_data
        files = input_data.get("files")
        if result.get("trace_id") and endpoint.project_id and files:
            from rhesis.backend.app.services.telemetry.conversation_linking import (
                register_pending_files,
            )

            register_pending_files(
                trace_id=result["trace_id"],
                files=files,
                organization_id=str(endpoint.organization_id),
            )

    async def invoke(
        self,
        db=None,
        endpoint=None,
        input_data=None,
        *,
        test_execution_context=None,
        trace_id=None,
    ) -> Union[Dict[str, Any], ErrorResponse]:
        """Invoke SDK function through WebSocket connection.

        Returns:
            Standardized response dict with output and metadata, or ErrorResponse for errors
        """
        # Backward-compat: callers that pass positional args build a temporary context.
        if db is not None or endpoint is not None:
            from .context import InvocationContext

            self.context = InvocationContext(
                db=db,
                endpoint=endpoint,
                input_data=input_data or {},
                test_execution_context=test_execution_context,
                trace_id=trace_id,
            )
        db = self.context.db
        endpoint = self.context.endpoint
        input_data = self.context.input_data
        test_execution_context = self.context.test_execution_context
        trace_id = self.context.trace_id
        try:
            # Step 1: Validate and extract metadata
            function_name, project_id, environment = self._validate_and_extract_metadata()

            # Step 2: Prepare function kwargs
            _, conversation_field = self._prepare_conversation_context(endpoint, input_data)
            function_kwargs = self._prepare_function_kwargs(function_name)

            # Step 3: Local registry short-circuit — call backend-resident
            # functions directly without a WebSocket round-trip.
            from rhesis.backend.app.services.local_function_registry import (
                ensure_local_functions_registered,
                registry,
            )

            ensure_local_functions_registered()

            if function_name in registry:
                from rhesis.backend.app.services.local_function_registry import (
                    LocalInvocationContext,
                )
                from rhesis.sdk.telemetry.context import (
                    get_root_trace_id,
                    set_tracing_disabled,
                )

                logger.info(f"Invoking local backend function: {function_name}")
                self._strip_user_rhesis_keys(function_kwargs)

                if endpoint.disable_tracing:
                    set_tracing_disabled(True)

                ctx = LocalInvocationContext(
                    organization_id=str(endpoint.organization_id),
                    user_id=str(endpoint.user_id) if endpoint.user_id else None,
                    db=db,
                    endpoint_id=endpoint.id,
                )

                # Resolve conversation_id + existing trace_id so the SDK
                # tracer (driven by the @endpoint decorator on the
                # registered function) reuses the conversation's trace_id
                # for every turn -- and so first-turn linking fires once
                # the result dict carries trace_id back to the EndpointService.
                conv_id, conv_trace_id, mapped_input = (
                    self._resolve_conversation_trace_context(conversation_field)
                )

                actual_trace_id: Optional[str] = None
                started = time.perf_counter()
                try:
                    async with self._local_telemetry_context(
                        conv_id, conv_trace_id, mapped_input
                    ):
                        raw = await asyncio.wait_for(
                            registry[function_name](ctx=ctx, **function_kwargs),
                            timeout=SDK_FUNCTION_TIMEOUT,
                        )
                        # Read inside the context manager: the SDK tracer
                        # sets _root_trace_id during the call and the
                        # finally block below clears it.
                        actual_trace_id = get_root_trace_id()
                finally:
                    if endpoint.disable_tracing:
                        set_tracing_disabled(False)

                duration_ms = int((time.perf_counter() - started) * 1000)
                # Pass a dict to _map_sdk_response so the ResponseMapper can
                # apply JSONPath/Jinja2 expressions without hitting
                # `dict(json_string)` (which fails on single-char iteration).
                # Pydantic models → model_dump(); plain dicts pass through;
                # strings are parsed if valid JSON, kept as-is otherwise.
                if hasattr(raw, "model_dump"):
                    output = raw.model_dump()
                elif isinstance(raw, dict):
                    output = raw
                elif isinstance(raw, str):
                    try:
                        output = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        output = raw
                else:
                    output = raw

                # Build the canonical SDK-shaped result so _park_mapped_output /
                # _park_input_files behave identically to the WebSocket path.
                raw_result = {
                    "status": "success",
                    "output": output,
                    "error": None,
                    "duration_ms": duration_ms,
                    "trace_id": actual_trace_id,
                }
                mapped_response = self._map_sdk_response(raw_result, function_name)
                self._ensure_conversation_field(mapped_response, conversation_field)

                if actual_trace_id:
                    # Surface trace_id on the mapped response so
                    # EndpointService.invoke_endpoint can call
                    # _link_first_turn_trace() when conversation_id is
                    # discovered in the response.
                    mapped_response["trace_id"] = actual_trace_id

                # Park mapped output and input files only when tracing is
                # active; there are no spans to attach them to otherwise.
                if not endpoint.disable_tracing and actual_trace_id:
                    self._park_mapped_output(raw_result, mapped_response)
                    self._park_input_files(raw_result)

                logger.info(
                    f"Local function {function_name} completed in {duration_ms}ms, "
                    f"trace_id={actual_trace_id}"
                )
                return mapped_response

            # Step 4: Determine invocation context (RPC vs direct WebSocket)
            use_rpc, context_type = self._determine_invocation_context(project_id, environment)
            logger.info(f"SDK invocation context: {context_type}")

            # Strip any user-supplied _rhesis_* keys to prevent injection,
            # then set the internal flag if the endpoint has tracing disabled.
            self._strip_user_rhesis_keys(function_kwargs)
            if endpoint.disable_tracing:
                function_kwargs["_rhesis_disable_tracing"] = True

            # Inject test and conversation context into function kwargs
            if test_execution_context:
                context = TestExecutionContext(**test_execution_context)
                function_kwargs[TestContextConstants.CONTEXT_KEY] = context.model_dump(mode="json")

            conversation_id = self._inject_conversation_context(conversation_field, function_kwargs)

            logger.info(
                f"Invoking SDK function: {function_name} "
                f"(project: {project_id}, env: {environment}, use_rpc: {use_rpc})"
            )
            logger.debug(f"Function kwargs: {function_kwargs}")

            # Execute via RPC or direct WebSocket
            invocation_id = f"invoke_{uuid.uuid4().hex[:12]}"
            execute_extras = self._connector_parameter_extras()

            if use_rpc:
                result = await self._execute_via_rpc(
                    project_id,
                    environment,
                    invocation_id,
                    function_name,
                    function_kwargs,
                    execute_extras=execute_extras,
                )
            else:
                result = await self._execute_via_websocket(
                    project_id,
                    environment,
                    invocation_id,
                    function_name,
                    function_kwargs,
                    execute_extras=execute_extras,
                )

            # Check for execution errors
            if isinstance(result, ErrorResponse):
                return result

            logger.debug(
                f"Raw SDK result keys: {list(result.keys())}, trace_id={result.get('trace_id')}"
            )

            error_response = self._check_result_errors(result, function_name)
            if error_response:
                return error_response

            # Map response and propagate trace/conversation fields
            mapped_response = self._map_sdk_response(result, function_name)
            self._ensure_conversation_field(mapped_response, conversation_field)

            if result.get("trace_id"):
                mapped_response["trace_id"] = result["trace_id"]

            # Park mapped output and files only when tracing is active;
            # there are no spans to attach them to when tracing is disabled.
            if not endpoint.disable_tracing:
                self._park_mapped_output(result, mapped_response)
                self._park_input_files(result)

            logger.info(
                f"SDK function {function_name} completed successfully "
                f"in {result.get('duration_ms', 0)}ms, "
                f"trace_id={result.get('trace_id')}"
            )

            return mapped_response

        except HTTPException:
            # Re-raise HTTPExceptions (configuration errors)
            raise
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for SDK function after {SDK_FUNCTION_TIMEOUT}s")
            return self._create_error_response(
                error_type="sdk_timeout",
                output_message="SDK function execution timed out",
                message=f"Function did not respond within {SDK_FUNCTION_TIMEOUT} seconds",
                request_details=self._safe_request_details(locals(), "SDK"),
            )
        except Exception as e:
            logger.error(f"Unexpected error invoking SDK function: {e}", exc_info=True)
            return self._create_error_response(
                error_type="sdk_unexpected_error",
                output_message=f"Unexpected SDK error: {str(e)}",
                message=str(e),
                request_details=self._safe_request_details(locals(), "SDK"),
            )
