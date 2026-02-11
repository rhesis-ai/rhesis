"""Main ImportService orchestrator.

Coordinates file upload, parsing, mapping, validation, and
final test set creation through a stateful multi-step flow.
"""

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.models.user import User
from rhesis.backend.logging import logger

from .mapping import auto_map_columns, is_llm_available, llm_map_columns
from .parsers import detect_format, extract_headers_and_sample, parse_file
from .storage import ImportSessionStore
from .validators import validate_rows


class ImportService:
    """Orchestrates the multi-step file import flow."""

    # ── Step 1: Analyze ──────────────────────────────────────────

    @staticmethod
    def analyze(
        file_bytes: bytes,
        filename: str,
        db: Optional[Session] = None,
        user: Optional[User] = None,
    ) -> Dict[str, Any]:
        """Upload a file, detect format, extract headers/sample, suggest mapping.

        Args:
            file_bytes: Raw uploaded file content.
            filename: Original filename (used for format detection).
            db: Optional DB session (needed for LLM mapping).
            user: Optional current user (needed for LLM mapping).

        Returns:
            Dict with import_id, file_info, headers, sample_rows,
            suggested_mapping, and confidence.
        """
        file_format = detect_format(filename)
        headers, sample_rows = extract_headers_and_sample(file_bytes, file_format)

        # Create session and store file
        session = ImportSessionStore.create_session(
            file_bytes=file_bytes,
            filename=filename,
            file_format=file_format,
        )
        session.headers = headers
        session.sample_rows = sample_rows

        # Attempt auto-mapping first
        mapping_result = auto_map_columns(headers)

        # If confidence is low and LLM is available, try LLM
        if mapping_result["confidence"] < 0.7 and is_llm_available(db, user):
            logger.info(
                f"Auto-mapping confidence {mapping_result['confidence']:.2f}"
                f" < 0.7; attempting LLM mapping"
            )
            llm_result = llm_map_columns(headers, sample_rows, db=db, user=user)
            # Use LLM result only if it improves confidence
            llm_confidence = llm_result.get("confidence", 0.0)
            if llm_confidence > mapping_result["confidence"]:
                mapping_result = llm_result

        session.suggested_mapping = mapping_result.get("mapping", {})
        session.mapping_confidence = mapping_result.get("confidence", 0.0)

        return {
            "import_id": session.import_id,
            "file_info": {
                "filename": filename,
                "format": file_format,
                "size_bytes": len(file_bytes),
            },
            "headers": headers,
            "sample_rows": sample_rows,
            "suggested_mapping": session.suggested_mapping,
            "confidence": session.mapping_confidence,
            "llm_available": is_llm_available(db, user),
        }

    # ── Step 2: Parse ────────────────────────────────────────────

    @staticmethod
    def parse(
        import_id: str,
        mapping: Dict[str, str],
        test_type: str = "Single-Turn",
    ) -> Dict[str, Any]:
        """Parse the full file with the confirmed column mapping.

        Args:
            import_id: Session identifier from the analyze step.
            mapping: Confirmed column mapping {source_col: target_field}.
            test_type: The test type for the entire import
                       ("Single-Turn" or "Multi-Turn").

        Returns:
            Dict with total_rows, validation_summary, and first
            page of preview data.
        """
        session = ImportSessionStore.get_session(import_id)
        if session is None:
            raise ValueError(f"Import session not found: {import_id}")

        # Parse the full file
        raw_rows = parse_file(session.file_bytes, session.file_format)

        # Apply mapping: rename columns in each row
        mapped_rows = _apply_mapping(raw_rows, mapping)

        # Normalize flat format to nested (prompt_content -> prompt)
        normalized = [_normalize_row(row, default_test_type=test_type) for row in mapped_rows]

        # Validate
        row_errors, row_warnings, summary = validate_rows(normalized)

        # Store results in session
        session.test_type = test_type
        session.parsed_rows = normalized
        session.row_errors = row_errors
        session.row_warnings = row_warnings
        session.validation_summary = summary

        # Return first page
        preview = ImportSessionStore.get_preview_page(import_id, page=1, page_size=50)

        return {
            "total_rows": summary["total_rows"],
            "validation_summary": summary,
            "preview": preview,
        }

    # ── Step 3: Preview (paginated) ──────────────────────────────

    @staticmethod
    def preview(
        import_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Optional[Dict[str, Any]]:
        """Return a page of parsed preview data."""
        return ImportSessionStore.get_preview_page(import_id, page=page, page_size=page_size)

    # ── Step 4: Confirm ──────────────────────────────────────────

    @staticmethod
    def confirm(
        import_id: str,
        db: Session,
        organization_id: str,
        user_id: str,
        name: str = "",
        description: str = "",
        short_description: str = "",
    ) -> Any:
        """Create the test set from parsed data.

        Calls the existing bulk_create_test_set service internally.
        Cleans up the import session on success.

        Returns:
            The created TestSet ORM model.
        """
        from rhesis.backend.app.services.test_set import (
            bulk_create_test_set,
        )

        session = ImportSessionStore.get_session(import_id)
        if session is None:
            raise ValueError(f"Import session not found: {import_id}")

        if not session.parsed_rows:
            raise ValueError("No parsed data to import. Run parse first.")

        # Filter out rows with validation errors
        valid_rows = []
        for i, row in enumerate(session.parsed_rows):
            row_errors = session.row_errors[i] if i < len(session.row_errors) else []
            if not row_errors:  # Only include rows without errors
                valid_rows.append(row)

        logger.info(
            f"Filtered {len(session.parsed_rows) - len(valid_rows)} rows with errors. "
            f"Importing {len(valid_rows)} valid rows."
        )

        # Build the TestData list for bulk create
        tests_payload = _rows_to_test_data(valid_rows)

        if not tests_payload:
            raise ValueError("No valid tests to import after filtering.")

        test_set_name = name or f"Import: {session.filename}"

        payload = {
            "name": test_set_name,
            "description": description,
            "short_description": short_description,
            "tests": tests_payload,
        }

        # Determine test set type from session
        from rhesis.backend.app.constants import TestType

        test_set_type = (
            TestType.MULTI_TURN if session.test_type == "Multi-Turn" else TestType.SINGLE_TURN
        )

        logger.info(
            f"Confirming import {import_id}: {len(tests_payload)} tests ({session.test_type})"
        )

        test_set = bulk_create_test_set(
            db=db,
            test_set_data=payload,
            organization_id=organization_id,
            user_id=user_id,
            test_set_type=test_set_type,
        )

        # Clean up session
        ImportSessionStore.delete_session(import_id)

        return test_set

    # ── Step 5: Cancel ───────────────────────────────────────────

    @staticmethod
    def cancel(import_id: str) -> bool:
        """Cancel and clean up an import session."""
        return ImportSessionStore.delete_session(import_id)

    # ── Re-map with LLM ─────────────────────────────────────────

    @staticmethod
    def remap_with_llm(
        import_id: str,
        db: Optional[Session] = None,
        user: Optional[User] = None,
    ) -> Dict[str, Any]:
        """Re-run mapping using LLM for an existing session.

        Returns the new mapping result, or the existing auto-mapping
        if LLM is not available.
        """
        session = ImportSessionStore.get_session(import_id)
        if session is None:
            raise ValueError(f"Import session not found: {import_id}")

        if not is_llm_available(db, user):
            return {
                "mapping": session.suggested_mapping,
                "confidence": session.mapping_confidence,
                "llm_available": False,
                "message": (
                    "No LLM is available. Configure a generation "
                    "model in Settings to enable AI-assisted mapping."
                ),
            }

        result = llm_map_columns(session.headers, session.sample_rows, db=db, user=user)
        session.suggested_mapping = result.get("mapping", {})
        session.mapping_confidence = result.get("confidence", 0.0)

        return {
            "mapping": session.suggested_mapping,
            "confidence": session.mapping_confidence,
            "llm_available": True,
        }


# ── Helpers ──────────────────────────────────────────────────────


def _apply_mapping(
    rows: List[Dict[str, Any]],
    mapping: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Rename columns in each row according to the mapping.

    Columns not in the mapping are preserved as-is (they may be
    nested JSON keys like "prompt" that don't need renaming).
    """
    if not mapping:
        return rows

    result = []
    for row in rows:
        new_row: Dict[str, Any] = {}
        for key, value in row.items():
            target = mapping.get(key, key)
            new_row[target] = value
        result.append(new_row)
    return result


def _normalize_row(
    row: Dict[str, Any],
    default_test_type: str = "Single-Turn",
) -> Dict[str, Any]:
    """Normalize flat format to the nested format expected by the SDK.

    Converts prompt_content/expected_response/language_code into a
    nested ``prompt`` dict if they aren't already nested.

    Args:
        row: A single parsed row.
        default_test_type: The test type to assign when the row
            does not already specify one ("Single-Turn" or
            "Multi-Turn").  Comes from the user's selection in
            the import dialog.
    """
    result = dict(row)

    # If we have flat prompt fields, build the nested prompt object
    prompt_content = result.pop("prompt_content", None)
    expected_response = result.pop("expected_response", None)
    language_code = result.pop("language_code", None)

    # If prompt_content is itself a dict (e.g. {"content": "text"}),
    # unwrap it so we don't double-nest.
    if isinstance(prompt_content, dict):
        nested = prompt_content
        prompt_content = nested.get("content")
        if not expected_response:
            expected_response = nested.get("expected_response")
        if not language_code:
            language_code = nested.get("language_code")

    if prompt_content and "prompt" not in result:
        prompt: Dict[str, Any] = {"content": prompt_content}
        if expected_response:
            prompt["expected_response"] = expected_response
        if language_code:
            prompt["language_code"] = language_code
        result["prompt"] = prompt
    elif "prompt" in result and isinstance(result["prompt"], dict):
        # Unwrap double-nesting: if prompt.content is itself a dict
        # with a "content" key, flatten it to the inner value.
        inner = result["prompt"].get("content")
        if isinstance(inner, dict) and "content" in inner:
            flattened = dict(inner)
            for k, v in result["prompt"].items():
                if k != "content" and k not in flattened:
                    flattened[k] = v
            result["prompt"] = flattened

        # Merge any flat fields into existing prompt dict
        if expected_response and "expected_response" not in result["prompt"]:
            result["prompt"]["expected_response"] = expected_response
        if language_code and "language_code" not in result["prompt"]:
            result["prompt"]["language_code"] = language_code

    # Apply default test_type from the user's selection
    if "test_type" not in result:
        result["test_type"] = default_test_type

    # Parse test_configuration if it's a JSON string (e.g. from CSV column)
    config_raw = result.get("test_configuration")
    if isinstance(config_raw, str):
        try:
            result["test_configuration"] = json.loads(config_raw)
        except json.JSONDecodeError:
            pass  # Leave as string; validation will report invalid format

    return result


def _rows_to_test_data(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert normalized rows to the TestData payload format.

    Filters out rows that are completely empty (no category, topic,
    behavior, or prompt content). Multi-turn tests don't require a prompt.
    """
    tests = []
    for row in rows:
        # Skip empty rows
        prompt = row.get("prompt", {})
        prompt_content = prompt.get("content", "") if isinstance(prompt, dict) else ""
        category = row.get("category", "")
        topic = row.get("topic", "")
        behavior = row.get("behavior", "")
        test_type = row.get("test_type", "Single-Turn")

        # Multi-turn tests don't need a prompt, single-turn tests do
        is_multi_turn = test_type == "Multi-Turn"

        # Skip if completely empty
        if is_multi_turn:
            # Multi-turn: need category, topic, behavior, but not prompt
            if not any(str(v or "").strip() for v in [category, topic, behavior]):
                continue
        else:
            # Single-turn: need category, topic, behavior, and prompt
            if not any(str(v or "").strip() for v in [prompt_content, category, topic, behavior]):
                continue

        # Build a clean prompt dict with content as a plain string
        # Multi-turn tests don't have prompts
        clean_prompt = None
        if not is_multi_turn and isinstance(prompt, dict):
            clean_prompt = dict(prompt)
            # Ensure content is a string, not a nested dict
            pc = clean_prompt.get("content")
            if isinstance(pc, dict) and "content" in pc:
                clean_prompt.update(pc)
            elif isinstance(pc, dict):
                clean_prompt["content"] = str(pc)

        test: Dict[str, Any] = {
            "category": category or "Uncategorized",
            "topic": topic or "General",
            "behavior": behavior or "Default",
        }

        # Only add prompt for single-turn tests if it has content
        if clean_prompt is not None and clean_prompt.get("content"):
            test["prompt"] = clean_prompt

        if row.get("test_type"):
            test["test_type"] = row["test_type"]

        # Build test_configuration from separate fields or use existing dict
        config_raw = row.get("test_configuration")
        if config_raw is not None:
            # Parse JSON string if needed (e.g. from CSV column with JSON text)
            if isinstance(config_raw, str):
                try:
                    config_raw = json.loads(config_raw)
                except json.JSONDecodeError:
                    config_raw = None
            if isinstance(config_raw, dict):
                test["test_configuration"] = config_raw
        if "test_configuration" not in test:
            # Build from separate fields: goal, instructions, restrictions, scenario
            test_config = {}
            if row.get("goal"):
                test_config["goal"] = row["goal"]
            if row.get("instructions"):
                test_config["instructions"] = row["instructions"]
            if row.get("restrictions"):
                test_config["restrictions"] = row["restrictions"]
            if row.get("scenario"):
                test_config["scenario"] = row["scenario"]
            if test_config:
                test["test_configuration"] = test_config

        if row.get("metadata"):
            meta = row["metadata"]
            if isinstance(meta, dict):
                test["metadata"] = meta
            else:
                # Column mapped to metadata (e.g. "notes") often has string values
                test["metadata"] = {"notes": str(meta)}

        tests.append(test)

    return tests
