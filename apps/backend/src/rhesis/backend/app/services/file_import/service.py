"""Main ImportService orchestrator.

Coordinates file upload, parsing, mapping, validation, and
final test set creation through a stateful multi-step flow.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.models.user import User

from .builder import rows_to_test_data
from .mapping import auto_map_columns, is_llm_available, llm_map_columns
from .parsers import detect_format, extract_headers_and_sample, parse_file
from .storage import MAX_ROWS_PER_IMPORT, ImportSessionStore
from .transforms import apply_mapping, detect_test_type_mismatch, normalize_row
from .validators import validate_rows

logger = logging.getLogger(__name__)


class ImportService:
    """Orchestrates the multi-step file import flow."""

    # ── Step 1: Analyze ──────────────────────────────────────────

    @staticmethod
    def analyze(
        file_bytes: bytes,
        filename: str,
        db: Optional[Session] = None,
        user: Optional[User] = None,
        user_id: str = "",
        organization_id: str = "",
    ) -> Dict[str, Any]:
        """Upload a file, detect format, extract headers/sample, suggest mapping.

        Args:
            file_bytes: Raw uploaded file content.
            filename: Original filename (used for format detection).
            db: Optional DB session (needed for LLM mapping).
            user: Optional current user (needed for LLM mapping).
            user_id: Owning user ID (stored for session verification).
            organization_id: Owning org ID.

        Returns:
            Dict with import_id, file_info, headers, sample_rows,
            suggested_mapping, and confidence.
        """
        file_format = detect_format(filename)
        headers, sample_rows = extract_headers_and_sample(file_bytes, file_format)

        session = ImportSessionStore.create_session(
            file_bytes=file_bytes,
            filename=filename,
            file_format=file_format,
            user_id=user_id,
            organization_id=organization_id,
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
            if llm_result.get("confidence", 0.0) > mapping_result["confidence"]:
                mapping_result = llm_result

        session.suggested_mapping = mapping_result.get("mapping", {})
        session.mapping_confidence = mapping_result.get("confidence", 0.0)

        ImportSessionStore.persist_session(session)

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
        user_id: str = "",
    ) -> Dict[str, Any]:
        """Parse the full file with the confirmed column mapping.

        Args:
            import_id: Session identifier from the analyze step.
            mapping: Confirmed column mapping {source_col: target_field}.
            test_type: The test type for the entire import
                       ("Single-Turn" or "Multi-Turn").
            user_id: Current user for ownership verification.

        Returns:
            Dict with total_rows, validation_summary, and first
            page of preview data.
        """
        session = ImportSessionStore.get_session(import_id, user_id=user_id)
        if session is None:
            raise ValueError(f"Import session not found: {import_id}")

        raw_rows = parse_file(session.file_bytes, session.file_format)

        if len(raw_rows) > MAX_ROWS_PER_IMPORT:
            raise ValueError(
                f"File contains {len(raw_rows)} rows which exceeds "
                f"the maximum of {MAX_ROWS_PER_IMPORT}. "
                f"Please split the file into smaller parts."
            )

        mapped_rows = apply_mapping(raw_rows, mapping)
        normalized = [normalize_row(row, default_test_type=test_type) for row in mapped_rows]

        row_errors, row_warnings, summary = validate_rows(normalized)

        session.test_type = test_type
        session.parsed_rows = normalized
        session.row_errors = row_errors
        session.row_warnings = row_warnings
        session.validation_summary = summary

        ImportSessionStore.persist_session(session)

        preview = ImportSessionStore.get_preview_page(
            import_id, page=1, page_size=50, user_id=user_id
        )

        detected_type, type_warning = detect_test_type_mismatch(mapped_rows, test_type)

        return {
            "total_rows": summary["total_rows"],
            "validation_summary": summary,
            "preview": preview,
            "detected_test_type": detected_type,
            "test_type_warning": type_warning,
        }

    # ── Step 3: Preview (paginated) ──────────────────────────────

    @staticmethod
    def preview(
        import_id: str,
        page: int = 1,
        page_size: int = 50,
        user_id: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Return a page of parsed preview data."""
        return ImportSessionStore.get_preview_page(
            import_id, page=page, page_size=page_size, user_id=user_id
        )

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
        from rhesis.backend.app.constants import TestSetType
        from rhesis.backend.app.services.test_set import bulk_create_test_set

        session = ImportSessionStore.get_session(import_id, user_id=user_id)
        if session is None:
            raise ValueError(f"Import session not found: {import_id}")

        if not session.parsed_rows:
            raise ValueError("No parsed data to import. Run parse first.")

        valid_rows = [
            row
            for i, row in enumerate(session.parsed_rows)
            if not (session.row_errors[i] if i < len(session.row_errors) else [])
        ]

        logger.info(
            f"Filtered {len(session.parsed_rows) - len(valid_rows)} rows with errors. "
            f"Importing {len(valid_rows)} valid rows."
        )

        tests_payload = rows_to_test_data(valid_rows)

        if not tests_payload:
            raise ValueError("No valid tests to import after filtering.")

        test_set_type = (
            TestSetType.MULTI_TURN if session.test_type == "Multi-Turn" else TestSetType.SINGLE_TURN
        )

        payload = {
            "name": name or f"Import: {session.filename}",
            "description": description,
            "short_description": short_description,
            "test_set_type": test_set_type.value,
            "tests": tests_payload,
        }

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

        ImportSessionStore.delete_session(import_id, user_id=user_id)

        return test_set

    # ── Step 5: Cancel ───────────────────────────────────────────

    @staticmethod
    def cancel(import_id: str, user_id: str = "") -> bool:
        """Cancel and clean up an import session."""
        return ImportSessionStore.delete_session(import_id, user_id=user_id)

    # ── Re-map with LLM ─────────────────────────────────────────

    @staticmethod
    def remap_with_llm(
        import_id: str,
        db: Optional[Session] = None,
        user: Optional[User] = None,
        user_id: str = "",
    ) -> Dict[str, Any]:
        """Re-run mapping using LLM for an existing session.

        Returns the new mapping result, or the existing auto-mapping
        if LLM is not available.
        """
        session = ImportSessionStore.get_session(import_id, user_id=user_id)
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

        ImportSessionStore.persist_session(session)

        return {
            "mapping": session.suggested_mapping,
            "confidence": session.mapping_confidence,
            "llm_available": True,
        }
