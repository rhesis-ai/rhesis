"""Result processing and storage utilities."""

import base64
import copy
import hashlib
import json
import logging
import uuid as _uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, schemas
from rhesis.backend.app.constants import TestResultStatus
from rhesis.backend.app.models.test import Test
from rhesis.backend.app.utils.crud_utils import get_or_create_status
from rhesis.backend.tasks.execution.response_extractor import extract_response_with_fallback

logger = logging.getLogger(__name__)

# Arguments larger than this are extracted out of test_output JSONB and stored
# as files. Sized to keep typical tool-call payloads inline while preventing
# multi-MB image attachments from blowing up JSONB rows. A single oversize
# argument turned an entire test set page into a 4+ minute load.
_TOOL_CALL_ARGUMENTS_MAX_INLINE_BYTES = 32 * 1024


def serialize_for_json(obj: Any) -> Any:
    """
    Recursively convert to JSON-serializable format.

    Handles datetime objects by converting them to ISO format strings.
    Recursively processes dicts, lists, and other nested structures.

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable version of the object

    Example:
        >>> data = {"timestamp": datetime.now(), "nested": {"date": datetime.now()}}
        >>> serialized = serialize_for_json(data)
        >>> # All datetime objects are now ISO strings
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    elif hasattr(obj, "__dict__"):
        # Handle Pydantic models and other objects with __dict__
        return serialize_for_json(obj.__dict__)
    else:
        return obj


def check_existing_result(
    db: Session,
    test_config_id: str,
    test_run_id: str,
    test_id: str,
    organization_id: str = None,
    user_id: str = None,
) -> Optional[Dict[str, Any]]:
    """Check if a result already exists for this test configuration."""
    filter_str = (
        f"test_configuration_id eq {test_config_id} and "
        f"test_run_id eq {test_run_id} and test_id eq {test_id}"
    )
    existing_results = crud.get_test_results(
        db, limit=1, filter=filter_str, organization_id=organization_id, user_id=user_id
    )

    if not existing_results:
        return None

    existing_result = existing_results[0]
    return {
        "test_id": test_id,
        "execution_time": existing_result.test_metrics.get("execution_time"),
        "metrics": existing_result.test_metrics.get("metrics", {}),
    }


def process_endpoint_result(result: Any) -> Dict:
    """
    Process endpoint result to ensure output field is populated.

    Uses fallback logic from response_extractor.
    Handles both dict results and ErrorResponse Pydantic objects.

    Returns:
        Processed result with output field populated using the fallback hierarchy
    """
    if not result:
        return {}

    # Handle ErrorResponse Pydantic objects by converting to dict
    if hasattr(result, "to_dict"):
        # Use to_dict() method if available (ErrorResponse)
        result_dict = result.to_dict()
    elif hasattr(result, "model_dump"):
        # Use model_dump() for Pydantic v2 models
        result_dict = result.model_dump(exclude_none=True)
    elif hasattr(result, "dict"):
        # Fallback to dict() for Pydantic v1 models
        result_dict = result.dict(exclude_none=True)
    elif isinstance(result, dict):
        # Already a dict
        result_dict = result
    else:
        logger.warning(f"Unexpected result type: {type(result)}, attempting to convert")
        result_dict = dict(result) if result else {}

    # Create a DEEP copy of the result to avoid modifying the original or sharing references
    processed_result = copy.deepcopy(result_dict)

    # Use the existing fallback logic to get the processed output
    processed_output = extract_response_with_fallback(processed_result)

    # Set the output field to the processed response
    processed_result["output"] = processed_output

    return processed_result


def _dedupe_target_interaction(processed_result: Dict) -> int:
    """Collapse ``target_interaction`` into a marker when it equals
    ``executions[-1]``.

    Multi-turn test runs emit a history where each turn carries both an
    ``executions`` list and a ``target_interaction`` object that is, in
    practice, a deep copy of the final execution. Storing both doubles
    every turn's payload (~330 KB per turn in chatbot tests with image
    attachments). Replace the duplicate with a one-key reference so the
    field is still present but cheap.

    Returns the number of entries that were collapsed.
    """
    history = processed_result.get("history") if isinstance(processed_result, dict) else None
    if not isinstance(history, list):
        return 0

    collapsed = 0
    for entry in history:
        if not isinstance(entry, dict):
            continue
        executions = entry.get("executions")
        target = entry.get("target_interaction")
        if (
            isinstance(executions, list)
            and executions
            and isinstance(target, dict)
            and not target.get("__same_as_last_execution__")
            and executions[-1] == target
        ):
            entry["target_interaction"] = {"__same_as_last_execution__": True}
            collapsed += 1
    return collapsed


def _extract_oversize_tool_call_arguments(processed_result: Dict, file_position_start: int) -> int:
    """Move oversize ``tool_calls[*].function.arguments`` payloads out of the
    JSONB into ``processed_result['output_files']`` so they get stored via
    object storage rather than inflating the test_output row.

    The inline ``arguments`` field is replaced with a JSON-envelope string
    (so callers that treat it as a string keep working). The envelope
    carries the filename, byte length, sha256, and a short preview.

    Returns the number of payloads extracted.
    """
    if not isinstance(processed_result, dict):
        return 0

    output_files = processed_result.setdefault("output_files", [])
    if not isinstance(output_files, list):
        return 0

    extracted = 0
    next_position = file_position_start
    # When two tool_call argument blobs hash to the same value within a
    # single test_result, point both inline markers at the same File row
    # rather than creating two storage objects for identical content. This
    # is especially common for multi-turn tests that re-pass the same
    # attachment on every turn.
    sha_to_file_id: Dict[str, str] = {}

    def _walk(node: Any) -> None:
        nonlocal extracted, next_position
        if isinstance(node, dict):
            args = node.get("arguments")
            if isinstance(args, str) and len(args) > _TOOL_CALL_ARGUMENTS_MAX_INLINE_BYTES:
                # Looks like a tool_call.function payload — extract it.
                raw = args.encode("utf-8")
                sha = hashlib.sha256(raw).hexdigest()
                tool_name = node.get("name") if isinstance(node.get("name"), str) else None
                base = tool_name.replace("/", "_") if tool_name else "tool_call_arguments"
                filename = f"{base}_{sha[:12]}.json"
                if sha in sha_to_file_id:
                    file_id = sha_to_file_id[sha]
                else:
                    file_id = str(_uuid.uuid4())
                    sha_to_file_id[sha] = file_id
                    output_files.append(
                        {
                            "file_id": file_id,
                            "data": base64.b64encode(raw).decode("ascii"),
                            "filename": filename,
                            "content_type": "application/json",
                            "position": next_position,
                        }
                    )
                    next_position += 1
                node["arguments"] = json.dumps(
                    {
                        "__file_attached__": True,
                        "file_id": file_id,
                        "filename": filename,
                        "byte_length": len(raw),
                        "sha256": sha,
                        "preview": args[:200],
                    }
                )
                extracted += 1
            for v in node.values():
                if isinstance(v, (dict, list)):
                    _walk(v)
        elif isinstance(node, list):
            for v in node:
                if isinstance(v, (dict, list)):
                    _walk(v)

    _walk(processed_result)
    if not output_files:
        # Don't leave an empty key around — let the existing pop() return None.
        processed_result.pop("output_files", None)
    return extracted


def create_test_result_record(
    db: Session,
    test: Test,
    test_config_id: str,
    test_run_id: str,
    test_id: str,
    organization_id: Optional[str],
    user_id: Optional[str],
    execution_time: float,
    metrics_results: Dict,
    processed_result: Dict,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[UUID]:
    """
    Create and store test result record in database.

    After creating the test result, this function automatically links
    any traces from the test execution to the new test result record.

    Args:
        db: Database session
        test: Test model instance
        test_config_id: UUID string of the test configuration
        test_run_id: UUID string of the test run
        test_id: UUID string of the test
        organization_id: UUID string of the organization (optional)
        user_id: UUID string of the user (optional)
        execution_time: Execution time in milliseconds
        metrics_results: Dictionary of metric evaluation results
        processed_result: Processed endpoint response / Penelope trace
        metadata: Optional provenance metadata to include in test_metrics.
            Used to record the source of the output, e.g.::

                {
                    "source": "rescore",
                    "reference_test_run_id": "uuid-of-original-run",
                }

    Returns:
        UUID of the created test result, or None if creation failed
    """
    # Determine status based on metrics evaluation
    if not metrics_results or len(metrics_results) == 0:
        # No metrics to evaluate - mark as ERROR
        status_value = TestResultStatus.ERROR.value
    else:
        # Check if all metrics passed
        all_metrics_passed = all(
            metric_data.get("is_successful", False)
            for metric_data in metrics_results.values()
            if isinstance(metric_data, dict)
        )
        status_value = (
            TestResultStatus.PASS.value if all_metrics_passed else TestResultStatus.FAIL.value
        )

    test_result_status = get_or_create_status(
        db, status_value, "TestResult", organization_id=organization_id
    )

    # Build test_metrics with optional provenance metadata
    test_metrics: Dict[str, Any] = {
        "execution_time": execution_time,
        "metrics": metrics_results,
    }
    if metadata:
        test_metrics["metadata"] = metadata

    collapsed = _dedupe_target_interaction(processed_result)
    if collapsed:
        logger.info(
            f"[TEST_RESULT] Collapsed {collapsed} duplicate target_interaction "
            f"entries for test_id={test_id}"
        )

    existing_output_files = (
        processed_result.get("output_files") if isinstance(processed_result, dict) else None
    )
    start_position = len(existing_output_files) if isinstance(existing_output_files, list) else 0
    extracted = _extract_oversize_tool_call_arguments(processed_result, start_position)
    if extracted:
        logger.info(
            f"[TEST_RESULT] Extracted {extracted} oversize tool_call arguments "
            f"to output files for test_id={test_id}"
        )

    # Extract output files before storing in JSONB (avoid base64 blobs in JSONB)
    output_files_data = processed_result.pop("output_files", None)

    test_result_data = {
        "test_configuration_id": UUID(test_config_id),
        "test_run_id": UUID(test_run_id),
        "test_id": UUID(test_id),
        "prompt_id": test.prompt_id,
        "status_id": test_result_status.id,
        "user_id": UUID(user_id) if user_id else None,
        "organization_id": UUID(organization_id) if organization_id else None,
        "test_metrics": test_metrics,
        "test_output": processed_result,
    }

    try:
        result = crud.create_test_result(
            db,
            schemas.TestResultCreate(**test_result_data),
            organization_id=organization_id,
            user_id=user_id,
        )

        # Validate that the result has a valid ID
        if not result or not hasattr(result, "id") or result.id is None:
            logger.error(
                f"[TEST_RESULT] Failed to create test result: CRUD operation returned "
                f"invalid result for test_id={test_id}, test_run_id={test_run_id}, "
                f"test_config_id={test_config_id}"
            )
            return None

        result_id = result.id
        logger.info(
            f"[TEST_RESULT] Successfully created test result with ID: {result_id} "
            f"for test_id={test_id}, test_run_id={test_run_id}, "
            f"test_config_id={test_config_id}"
        )

        # Store output files on the test result
        if result_id and output_files_data:
            try:
                _store_output_files(db, result_id, output_files_data, organization_id, user_id)
            except Exception as file_error:
                logger.error(
                    f"[TEST_RESULT] Failed to store output files for "
                    f"test_result_id={result_id}: {file_error}",
                    exc_info=True,
                )

        # Link traces to this test result
        if result_id:
            logger.info(f"[TEST_RESULT] Attempting to link traces to test_result_id={result_id}")
            try:
                from rhesis.backend.app.services.telemetry.linking_service import (
                    TraceLinkingService,
                )

                linking_service = TraceLinkingService(db)
                updated_count = linking_service.link_traces_for_test_result(
                    test_run_id=test_run_id,
                    test_id=test_id,
                    test_configuration_id=test_config_id,
                    test_result_id=str(result_id),
                    organization_id=organization_id,
                )
                logger.info(
                    f"[TEST_RESULT] Trace linking complete: {updated_count} traces "
                    f"linked to test_result_id={result_id}"
                )
            except Exception as trace_error:
                # Don't fail test result creation if trace linking fails
                logger.error(
                    f"[TEST_RESULT] Failed to link traces to test result "
                    f"{result_id}: {trace_error}",
                    exc_info=True,
                )
        else:
            logger.warning(
                "[TEST_RESULT] No result_id returned from create_test_result, "
                "skipping trace linking"
            )

        return result_id

    except Exception as e:
        logger.error(f"[TEST_RESULT] Failed to create test result: {str(e)}", exc_info=True)
        raise


def _is_safe_attachment_storage_path(
    storage_path: Optional[str],
    organization_id: Optional[str],
    test_result_id: UUID,
) -> bool:
    """Return True iff ``storage_path`` is the relative attachments key we'd
    have produced for this org + test result.

    Rejects anything that could be used by an untrusted endpoint output to
    point at storage objects outside its own scope:

    - Absent / non-string values.
    - Absolute paths, scheme-qualified URIs (``file://``, ``gs://``, …),
      or values with backslashes (Windows-style separators).
    - Path traversal segments (``..``, ``.``, empty segments).
    - Anything that doesn't begin with the expected per-entity prefix
      ``attachments/{organization_id}/TestResult/{test_result_id}/``.

    The prefix is rebuilt from server-trusted ``organization_id`` and
    ``test_result_id`` and compared verbatim, so callers cannot smuggle in
    a different org's prefix.
    """
    if not storage_path or not isinstance(storage_path, str):
        return False
    if not organization_id:
        # Without a known org we have no prefix to match — refuse Path A.
        return False
    if storage_path.startswith("/") or "\\" in storage_path:
        return False
    if "://" in storage_path:
        return False
    # Reject traversal / empty segments.
    parts = storage_path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False

    expected_prefix = f"attachments/{organization_id}/TestResult/{test_result_id}/"
    return storage_path.startswith(expected_prefix)


def _store_output_files(
    db: Session,
    test_result_id: UUID,
    output_files_data: List[Dict[str, Any]],
    organization_id: Optional[str],
    user_id: Optional[str],
) -> None:
    """Persist endpoint output files to object storage + File metadata rows.

    Each item in ``output_files_data`` is one of:

    Path A — pre-uploaded:
        ``{signed_url, storage_path, filename, content_type, size_bytes,
        content_hash, file_id?}``.  Only accepted when ``storage_path``
        passes :func:`_is_safe_attachment_storage_path` (relative key under
        ``attachments/{org}/TestResult/{test_result_id}/``).  Anything else
        is dropped with a loud warning — endpoints cannot register
        arbitrary object keys this way (cross-tenant disclosure guard).

    Path B — inline bytes:
        ``{data: base64, filename, content_type, file_id?}``.  Bytes are
        decoded and written through :meth:`StorageService.put_object_bytes`
        (sync — this function may run inside an async task body, so we
        cannot open a fresh event loop here).
    """
    from rhesis.backend.app.services.storage_service import StorageService

    if not isinstance(output_files_data, list):
        logger.warning(
            f"[TEST_RESULT] output_files is not a list, skipping: {type(output_files_data)}"
        )
        return

    storage = StorageService()

    for idx, file_data in enumerate(output_files_data):
        if not isinstance(file_data, dict):
            continue

        filename = file_data.get("filename", f"output_{idx}")
        content_type = file_data.get("content_type", "application/octet-stream")
        # Sanitiser pre-generates a file_id so it can embed it in the inline
        # marker; honour it here so the marker resolves to a real File row.
        prebound_file_id = file_data.get("file_id")

        # Path A: pre-uploaded file with a signed_url.  We MUST validate that
        # the supplied ``storage_path`` is inside this entity's prefix —
        # otherwise a malicious endpoint output could register arbitrary
        # object keys (or absolute paths on file:// backends) and read them
        # back via ``GET /files/{id}/content``.
        if file_data.get("signed_url") and not file_data.get("data"):
            candidate_path = file_data.get("storage_path")
            if not _is_safe_attachment_storage_path(
                candidate_path, organization_id, test_result_id
            ):
                logger.warning(
                    "[TEST_RESULT] Refusing pre-uploaded output file with "
                    "unsafe storage_path=%r for test_result_id=%s — endpoint "
                    "output may only register files under its own attachments "
                    "prefix.",
                    candidate_path,
                    test_result_id,
                )
                continue

            file_create = schemas.FileCreate(
                id=UUID(prebound_file_id) if prebound_file_id else None,
                filename=filename,
                content_type=content_type,
                size_bytes=file_data.get("size_bytes", 0),
                entity_id=test_result_id,
                entity_type="TestResult",
                position=idx,
                storage_path=candidate_path,
                content_hash=file_data.get("content_hash"),
                extraction_status="pending",
            )
            crud.create_file(db, file_create, organization_id=organization_id, user_id=user_id)
            continue

        # Path B: base64-encoded bytes — decode and write to storage.
        content_b64 = file_data.get("data")
        if not content_b64:
            continue

        try:
            content = base64.b64decode(content_b64)
        except Exception:
            logger.warning(f"[TEST_RESULT] Failed to decode base64 for output file {idx}")
            continue

        file_id = UUID(prebound_file_id) if prebound_file_id else _uuid.uuid4()
        dest_path = storage.get_attachment_original_path(
            organization_id=organization_id or "",
            entity_type="TestResult",
            entity_id=str(test_result_id),
            file_id=str(file_id),
            filename=filename,
        )

        try:
            storage_path, content_hash = storage.put_object_bytes(
                content=content,
                dest_path=dest_path,
                content_type=content_type,
            )
        except Exception as exc:
            logger.error(f"[TEST_RESULT] Failed to upload output file {idx}: {exc}")
            continue

        file_create = schemas.FileCreate(
            id=file_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            entity_id=test_result_id,
            entity_type="TestResult",
            position=idx,
            storage_path=storage_path,
            content_hash=content_hash,
            extraction_status="pending",
        )
        crud.create_file(db, file_create, organization_id=organization_id, user_id=user_id)

    logger.info(
        f"[TEST_RESULT] Stored {len(output_files_data)} output files "
        f"for test_result_id={test_result_id}"
    )
