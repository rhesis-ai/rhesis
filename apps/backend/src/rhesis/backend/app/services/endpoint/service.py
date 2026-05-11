"""Core endpoint service — orchestrates endpoint invocation."""

import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.schemas.endpoint import EndpointTestRequest
from rhesis.backend.app.services.invokers import create_invoker
from rhesis.backend.app.services.invokers.common.errors import EndpointInvocationError
from rhesis.backend.app.services.invokers.context import InvocationContext
from rhesis.backend.app.services.invokers.conversation import (
    ConversationTracker,
    find_conversation_id,
    get_conversation_store,
)

from . import sdk_sync
from .files import (
    endpoint_supports_files,
    enrich_files_with_extraction,
    inject_file_content_into_input,
)
from .testing import test_endpoint as _test_endpoint

logger = logging.getLogger(__name__)


class EndpointService:
    """Orchestrates endpoint invocation across all connection types.

    The service is intentionally thin: it enriches input data, manages
    stateless conversation history, delegates file handling to ``files.py``,
    and hands off to the appropriate ``BaseEndpointInvoker`` subclass.

    Endpoint testing (transient configs) is handled by ``testing.py``.
    SDK endpoint sync is handled by ``sdk_sync.py``.
    """

    def __init__(self, schema_path: str = None):
        if schema_path:
            self.schema_path = schema_path
        else:
            services_dir = os.path.dirname(os.path.dirname(__file__))
            self.schema_path = os.path.join(services_dir, "endpoint_schema.json")

    async def invoke_endpoint(
        self,
        db: Optional[Session],
        endpoint_id: str,
        input_data: Dict[str, Any],
        organization_id: str = None,
        user_id: str = None,
        test_execution_context: Optional[Dict[str, str]] = None,
        endpoint: Optional[Endpoint] = None,
        deferred_trace: bool = False,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Invoke an endpoint with the given input data.

        Args:
            db: Database session (can be None when endpoint is pre-fetched and
                deferred_trace=True for DB-free batch mode).
            endpoint_id: ID of the endpoint to invoke.
            input_data: Input data mapped to the endpoint's request template.
            organization_id: Organization ID for security filtering (CRITICAL).
            user_id: User ID for context injection (CRITICAL).
            test_execution_context: Optional dict with test_run_id, test_result_id, test_id.
            endpoint: Optional pre-fetched Endpoint model (skips DB lookup).
            deferred_trace: When True, trace data is collected in-memory and
                returned in the result dict under ``_deferred_trace``.
            trace_id: Optional trace_id to reuse (for in-memory multi-turn tracking).

        Returns:
            Dict containing the mapped response from the endpoint.

        Raises:
            HTTPException: If endpoint is not found or invocation fails.
        """
        if endpoint is None:
            endpoint = self._get_endpoint(db, endpoint_id, organization_id)
        logger.debug(f"Invoking endpoint {endpoint.name} ({endpoint.connection_type})")

        try:
            # ------------------------------------------------------------------
            # Input enrichment — inject server-side context fields
            # ------------------------------------------------------------------
            # organization_id and user_id are injected by the backend, NOT from
            # user input (SECURITY CRITICAL).
            enriched_input_data = input_data.copy()
            if organization_id:
                enriched_input_data["organization_id"] = organization_id
            if user_id:
                enriched_input_data["user_id"] = user_id
            if test_execution_context:
                for key in ("test_id", "test_run_id", "test_configuration_id"):
                    value = test_execution_context.get(key)
                    if value is not None:
                        enriched_input_data[key] = value

            # ------------------------------------------------------------------
            # File handling
            # ------------------------------------------------------------------
            # Must run BEFORE stateless message building so that Case B text
            # injection into ``input`` is picked up when the messages list is
            # assembled below.
            #
            # A) Endpoint supports {{ files }}: enrich each file with
            #    extracted_text and forward the full dict to the endpoint.
            # B) Endpoint has no {{ files }}: extract text and inject it into
            #    the {{ input }} message so plain-text endpoints (including
            #    stateless {{ messages }} endpoints) still receive file content.
            if enriched_input_data.get("files"):
                supports_files = endpoint_supports_files(endpoint)
                if supports_files:
                    enriched_input_data["files"] = enrich_files_with_extraction(
                        enriched_input_data["files"],
                        db=db,
                        user_id=user_id,
                    )
                    logger.debug(
                        "Endpoint '%s' supports files — forwarding %d enriched file(s)",
                        endpoint.name,
                        len(enriched_input_data["files"]),
                    )
                else:
                    enriched_files = enrich_files_with_extraction(
                        enriched_input_data.pop("files"),
                        db=db,
                        user_id=user_id,
                    )
                    # Preserve lightweight metadata for tracing (filename +
                    # content_type only — no base64 payload).
                    enriched_input_data["files_metadata"] = [
                        {
                            "filename": f.get("filename", ""),
                            "content_type": f.get("content_type", ""),
                        }
                        for f in enriched_files
                        if isinstance(f, dict)
                    ]
                    if "input" in enriched_input_data and isinstance(
                        enriched_input_data["input"], str
                    ):
                        enriched_input_data["input"] = inject_file_content_into_input(
                            enriched_input_data["input"], enriched_files
                        )
                        logger.info(
                            "Endpoint '%s' has no file support — injected %d file(s) into input",
                            endpoint.name,
                            len(enriched_files),
                        )
                    else:
                        logger.warning(
                            "Endpoint '%s' has no file support and no 'input' field — "
                            "file content cannot be injected",
                            endpoint.name,
                        )

            # ------------------------------------------------------------------
            # Stateless conversation management
            # ------------------------------------------------------------------
            # For stateless endpoints (detected via {{ messages }} in
            # request_mapping) the backend manages conversation history
            # server-side.  Callers use ``conversation_id`` exactly like they
            # would for stateful endpoints — the difference is transparent.
            #
            # Two-phase commit: the user message is appended to a *temporary*
            # messages list for the request body, but is only committed to the
            # store after a successful invocation.  This avoids leaving the
            # conversation in an inconsistent state when the endpoint errors.
            is_stateless = ConversationTracker.detect_stateless_mode(endpoint)
            stateless_conversation_id = None
            stateless_user_input = None

            if is_stateless and "messages" not in enriched_input_data:
                store = get_conversation_store()
                incoming_cid = enriched_input_data.get("conversation_id")
                # Read input *after* any file injection so file content is
                # included in the user message appended to the messages list.
                stateless_user_input = enriched_input_data.get("input", "")

                if incoming_cid and store.exists(incoming_cid):
                    stateless_conversation_id = incoming_cid
                else:
                    system_prompt = ConversationTracker.extract_system_prompt(endpoint)
                    stateless_conversation_id = store.create(system_prompt=system_prompt)
                    if incoming_cid:
                        logger.warning(
                            f"Conversation {incoming_cid} not found, "
                            f"created new: {stateless_conversation_id}"
                        )

                messages = store.get_messages(stateless_conversation_id)
                if stateless_user_input:
                    messages.append({"role": "user", "content": stateless_user_input})
                enriched_input_data["messages"] = messages

                # Remove conversation_id — it's an internal tracking field and
                # must not leak into the external request body.
                enriched_input_data.pop("conversation_id", None)

                logger.debug(
                    "Stateless conversation %s: %d message(s)",
                    stateless_conversation_id,
                    len(messages),
                )

            # ------------------------------------------------------------------
            # Prompt preprocessing
            # ------------------------------------------------------------------
            if "input" in enriched_input_data and isinstance(enriched_input_data["input"], str):
                from rhesis.backend.app.services.prompt_preprocessor import prompt_preprocessor

                enriched_input_data["input"] = prompt_preprocessor.process(
                    enriched_input_data["input"],
                    endpoint=endpoint,
                )

            # ------------------------------------------------------------------
            # Invocation
            # ------------------------------------------------------------------
            trace_conversation_id = stateless_conversation_id or find_conversation_id(input_data)

            context = InvocationContext(
                db=db,
                endpoint=endpoint,
                input_data=enriched_input_data,
                test_execution_context=test_execution_context,
                trace_id=trace_id,
            )
            invoker = create_invoker(context)

            if not invoker.automatic_tracing:
                if endpoint.disable_tracing:
                    result = await invoker.invoke()
                else:
                    from rhesis.backend.app.services.invokers.tracing import create_invocation_trace

                    async with create_invocation_trace(
                        db,
                        endpoint,
                        organization_id,
                        test_execution_context,
                        conversation_id=trace_conversation_id,
                        input_data=enriched_input_data,
                        deferred=deferred_trace,
                        trace_id=trace_id,
                    ) as trace_ctx:
                        result = await invoker.invoke()
                        trace_ctx["result"] = result

                    if deferred_trace and isinstance(result, dict):
                        deferred_data = trace_ctx.get("_deferred_trace")
                        if deferred_data:
                            result["_deferred_trace"] = deferred_data
            else:
                result = await invoker.invoke()

            # ------------------------------------------------------------------
            # Post-invocation: commit stateless conversation on success
            # ------------------------------------------------------------------
            if is_stateless and stateless_conversation_id and result:
                result_dict = result if isinstance(result, dict) else None
                if result_dict is not None:
                    store = get_conversation_store()
                    if stateless_user_input:
                        store.add_user_message(stateless_conversation_id, stateless_user_input)
                    output = result_dict.get("output", "")
                    if output:
                        output_text = (
                            json.dumps(output) if isinstance(output, (dict, list)) else str(output)
                        )
                        store.add_assistant_message(
                            stateless_conversation_id,
                            output_text,
                            tool_calls=result_dict.get("tool_calls"),
                        )
                    result_dict["conversation_id"] = stateless_conversation_id

            # ------------------------------------------------------------------
            # Guarantee conversation_id in every dict response
            # ------------------------------------------------------------------
            if not is_stateless and isinstance(result, dict) and not find_conversation_id(result):
                incoming_conversation_id = input_data.get("conversation_id")
                if incoming_conversation_id:
                    result["conversation_id"] = incoming_conversation_id

            # ------------------------------------------------------------------
            # First-turn trace linking
            # ------------------------------------------------------------------
            if not trace_conversation_id and isinstance(result, dict) and result.get("trace_id"):
                response_conversation_id = find_conversation_id(result)
                if response_conversation_id:
                    if deferred_trace:
                        deferred_data = result.get("_deferred_trace")
                        if deferred_data:
                            deferred_data.first_turn_link = {
                                "trace_id": result["trace_id"],
                                "conversation_id": response_conversation_id,
                            }
                    elif db:
                        self._link_first_turn_trace(
                            db=db,
                            trace_id=result["trace_id"],
                            conversation_id=response_conversation_id,
                            organization_id=organization_id,
                        )

            logger.debug(f"Endpoint invocation completed: {endpoint.name}")
            return result

        except EndpointInvocationError:
            raise
        except ValueError as e:
            logger.error(f"ValueError invoking endpoint: {e}")
            raise EndpointInvocationError(
                str(e), transient=False, status_code=400, error_type="validation_error"
            )
        except (TimeoutError, ConnectionError, OSError) as e:
            logger.error(f"Transient error invoking endpoint: {e}", exc_info=True)
            raise EndpointInvocationError(
                str(e), transient=True, status_code=502, error_type="network_error"
            )
        except Exception as e:
            logger.error(f"Exception invoking endpoint: {e}", exc_info=True)
            raise EndpointInvocationError(
                str(e), transient=False, status_code=500, error_type="internal_error"
            )

    @staticmethod
    def _link_first_turn_trace(
        db: Session,
        trace_id: str,
        conversation_id: str,
        organization_id: str,
    ) -> None:
        """Retroactively set conversation_id on a first-turn trace.

        For stateful endpoints the first turn has no conversation_id at
        invocation time — the endpoint generates it in its response.  This
        stamps the discovered ID onto the already-stored trace spans so future
        turns can find and reuse the same trace_id.

        If the immediate UPDATE matches 0 rows (SDK spans not yet ingested),
        the mapping is parked for deferred application when spans arrive.
        """
        updated_count = crud.update_conversation_id_for_trace(
            db=db,
            trace_id=trace_id,
            conversation_id=conversation_id,
            organization_id=organization_id,
        )
        if updated_count == 0:
            from rhesis.backend.app.services.telemetry.conversation_linking import (
                register_pending_conversation_link,
            )

            register_pending_conversation_link(
                trace_id=trace_id,
                conversation_id=conversation_id,
                organization_id=organization_id,
            )

    def _get_endpoint(self, db: Session, endpoint_id: str, organization_id: str = None) -> Endpoint:
        """Fetch an endpoint by ID, applying organization-level security filtering."""
        query = db.query(Endpoint).filter(Endpoint.id == endpoint_id)
        if organization_id:
            from uuid import UUID

            query = query.filter(Endpoint.organization_id == UUID(organization_id))
        endpoint = query.first()
        if not endpoint:
            raise HTTPException(status_code=404, detail="Endpoint not found or not accessible")
        return endpoint

    def get_schema(self) -> Dict[str, Any]:
        """Return the endpoint schema definition from disk."""
        with open(self.schema_path, "r") as f:
            return json.load(f)

    async def test_endpoint(
        self,
        db: Session,
        test_config: EndpointTestRequest,
        organization_id: str = None,
        user_id: str = None,
    ) -> Dict[str, Any]:
        """Test a transient endpoint configuration without persisting it.

        Delegates to ``testing.test_endpoint``.
        """
        return await _test_endpoint(
            db=db,
            test_config=test_config,
            organization_id=organization_id,
            user_id=user_id,
        )

    async def sync_sdk_endpoints(
        self,
        db: Session,
        project_id: str,
        environment: str,
        functions_data: list,
        organization_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Sync SDK endpoints — delegates to ``sdk_sync``."""
        return await sdk_sync.sync_sdk_endpoints(
            db=db,
            project_id=project_id,
            environment=environment,
            functions_data=functions_data,
            organization_id=organization_id,
            user_id=user_id,
        )
