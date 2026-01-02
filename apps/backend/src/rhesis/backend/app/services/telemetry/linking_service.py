"""Trace linking service for connecting traces to test results.

This service handles the linking of traces to test results, which can happen
at two different points in time:
1. After test result creation (catches traces that arrived early)
2. After trace ingestion (catches traces that arrive late)

The service uses a shared implementation to avoid code duplication.
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.constants import TestExecutionContext

logger = logging.getLogger(__name__)


class TraceLinkingService:
    """Service for linking traces to test results.

    This service provides two entry points for linking traces:
    - link_traces_for_test_result: Called after test result creation
    - link_traces_for_incoming_batch: Called after trace ingestion

    Both use the same underlying implementation to ensure consistency.
    """

    def __init__(self, db: Session):
        """Initialize the linking service.

        Args:
            db: Database session
        """
        self.db = db

    def link_traces_for_test_result(
        self,
        test_run_id: str,
        test_id: str,
        test_configuration_id: str,
        test_result_id: str,
        organization_id: str,
    ) -> int:
        """Link traces after test result creation.

        This is called immediately after a test result is created to link
        any traces that have already arrived (early batches from BatchSpanProcessor).

        Args:
            test_run_id: Test run UUID string
            test_id: Test UUID string
            test_configuration_id: Test configuration UUID string
            test_result_id: Test result UUID string
            organization_id: Organization UUID string

        Returns:
            Number of traces linked
        """
        logger.debug(
            f"[LINKING] Linking traces for test result: "
            f"test_result_id={test_result_id}, test_run_id={test_run_id}"
        )

        return self._find_and_link(
            test_run_id=test_run_id,
            test_id=test_id,
            test_configuration_id=test_configuration_id,
            test_result_id=test_result_id,
            organization_id=organization_id,
        )

    def link_traces_for_incoming_batch(
        self,
        spans: List[models.Trace],
        organization_id: str,
    ) -> int:
        """Link traces after span ingestion.

        This is called after traces are stored in the database to link them
        to test results that may have been created while the traces were in flight
        (late batches from BatchSpanProcessor).

        Args:
            spans: List of stored trace spans
            organization_id: Organization UUID string

        Returns:
            Number of traces linked (0 if no test context or test result not found)
        """
        if not spans:
            return 0

        # Extract test execution context from first span
        # All spans in a batch should have the same test context
        first_span = spans[0]

        # Check if this is a test trace
        test_run_id = first_span.test_run_id
        test_id = first_span.test_id

        if not test_run_id or not test_id:
            # Not a test trace, skip linking
            logger.debug("[LINKING] Skipping non-test traces")
            return 0

        # Extract test_configuration_id from attributes
        test_configuration_id = first_span.attributes.get(
            TestExecutionContext.SpanAttributes.TEST_CONFIGURATION_ID
        )

        if not test_configuration_id:
            logger.warning(
                f"[LINKING] Test trace missing test_configuration_id in attributes: "
                f"test_run_id={test_run_id}, test_id={test_id}"
            )
            return 0

        logger.debug(
            f"[LINKING] Found test trace batch: "
            f"test_run_id={test_run_id}, test_id={test_id}, "
            f"test_configuration_id={test_configuration_id}, spans={len(spans)}"
        )

        # Query for the test result
        test_result = self._find_test_result(
            test_run_id=str(test_run_id),
            test_id=str(test_id),
            test_configuration_id=test_configuration_id,
            organization_id=organization_id,
        )

        if not test_result:
            logger.debug(
                f"[LINKING] Test result not found yet for incoming batch: "
                f"test_run_id={test_run_id}, test_id={test_id}"
            )
            return 0

        # Link the traces
        return self._find_and_link(
            test_run_id=str(test_run_id),
            test_id=str(test_id),
            test_configuration_id=test_configuration_id,
            test_result_id=str(test_result.id),
            organization_id=organization_id,
        )

    def _find_test_result(
        self,
        test_run_id: str,
        test_id: str,
        test_configuration_id: str,
        organization_id: str,
    ) -> Optional[models.TestResult]:
        """Find test result by test execution context.

        Args:
            test_run_id: Test run UUID string
            test_id: Test UUID string
            test_configuration_id: Test configuration UUID string
            organization_id: Organization UUID string

        Returns:
            TestResult model or None if not found
        """
        from uuid import UUID

        try:
            test_run_uuid = UUID(test_run_id)
            test_id_uuid = UUID(test_id)
            test_config_uuid = UUID(test_configuration_id)
            org_uuid = UUID(organization_id)
        except (ValueError, AttributeError) as e:
            logger.error(f"[LINKING] Invalid UUID in test context: {e}")
            return None

        result = (
            self.db.query(models.TestResult)
            .filter(
                models.TestResult.test_run_id == test_run_uuid,
                models.TestResult.test_id == test_id_uuid,
                models.TestResult.test_configuration_id == test_config_uuid,
                models.TestResult.organization_id == org_uuid,
            )
            .first()
        )

        return result

    def _find_and_link(
        self,
        test_run_id: str,
        test_id: str,
        test_configuration_id: str,
        test_result_id: str,
        organization_id: str,
    ) -> int:
        """Shared implementation for linking traces to test result.

        This method is called by both entry points to perform the actual linking.
        It delegates to the CRUD layer for the database operation.

        Args:
            test_run_id: Test run UUID string
            test_id: Test UUID string
            test_configuration_id: Test configuration UUID string
            test_result_id: Test result UUID string
            organization_id: Organization UUID string

        Returns:
            Number of traces linked
        """
        return crud.update_traces_with_test_result_id(
            db=self.db,
            test_run_id=test_run_id,
            test_id=test_id,
            test_configuration_id=test_configuration_id,
            test_result_id=test_result_id,
            organization_id=organization_id,
        )
