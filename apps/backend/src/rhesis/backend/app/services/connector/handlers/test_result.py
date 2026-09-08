"""Test result message handler for SDK WebSocket connections."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.services.connector.schemas import TestResultMessage
from rhesis.backend.app.services.connector.session import DbSessionFactory, resolve_session

logger = logging.getLogger(__name__)


class TestResultHandler:
    """Handles test result messages from SDK WebSocket connections."""

    async def handle_test_result_message(
        self,
        project_id: str,
        environment: str,
        message: Dict[str, Any],
        db: Optional[Session] = None,
        db_factory: Optional[DbSessionFactory] = None,
    ) -> None:
        """
        Handle test result message from SDK.

        Only ``validation_`` run ids touch the database, so that check runs
        before any session is acquired — every other result is the hot path and
        must not pay for a session it never uses.

        Args:
            project_id: Project identifier
            environment: Environment name
            message: Test result message
            db: Open session, when the caller already owns one
            db_factory: Opens a session on demand, for the late-validation path
        """
        try:
            result = TestResultMessage(**message)
        except Exception as e:
            logger.error(f"Error parsing test result: {e}")
            return

        self._log_test_result(project_id, environment, result)

        if not result.test_run_id.startswith("validation_"):
            return

        with resolve_session(db, db_factory) as session:
            if session is not None:
                await self._handle_late_validation_result(project_id, environment, result, session)

    def _log_test_result(
        self, project_id: str, environment: str, result: TestResultMessage
    ) -> None:
        """Log one record per result, with the payload only at DEBUG.

        This runs once per inbound result on the WebSocket loop, and every record
        is JSON-formatted and regex-redacted before it reaches stdout, so the
        number of records matters more than what is in them.
        """
        if result.status != "success":
            logger.error(
                "Test result %s:%s run=%s failed after %sms: %s",
                project_id,
                environment,
                result.test_run_id,
                result.duration_ms,
                result.error,
            )
            return

        logger.info(
            "Test result %s:%s run=%s status=%s duration=%sms",
            project_id,
            environment,
            result.test_run_id,
            result.status,
            result.duration_ms,
        )
        if logger.isEnabledFor(logging.DEBUG):
            output_str = str(result.output)
            if len(output_str) > 500:
                output_str = f"{output_str[:500]}...{output_str[-100:]}"
            logger.debug("Test result %s output: %s", result.test_run_id, output_str)

    async def _handle_late_validation_result(
        self,
        project_id: str,
        environment: str,
        result: TestResultMessage,
        db: Session,
    ) -> None:
        """
        Handle late-arriving validation results and update endpoint status.

        When validation tests timeout but results arrive later, we should update
        the endpoint status based on the actual test result.

        Args:
            project_id: Project identifier
            environment: Environment name
            result: Parsed test result, already known to be a validation run
            db: Database session
        """
        try:
            logger.info(f"🔄 Processing late validation result for {result.test_run_id}")

            # Find the endpoint by project_id, environment, and function name
            # We need to extract function name from the test execution context
            # Query endpoints for this project/environment that are currently in Error status
            # and were recently updated (within last 30 seconds to catch recent validations)
            from rhesis.backend.app.models.endpoint import Endpoint
            from rhesis.backend.app.models.status import Status
            from rhesis.backend.app.utils.query_utils import QueryBuilder

            recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)

            # First, get a sample endpoint to determine the organization
            # We'll use this to filter statuses by organization for tenant isolation
            # Use QueryBuilder which properly handles soft delete filtering
            sample_endpoint = (
                QueryBuilder(db, Endpoint)
                .with_custom_filter(
                    lambda q: q.filter(
                        Endpoint.project_id == project_id,
                        Endpoint.environment == environment,
                    )
                )
                .first()
            )

            if not sample_endpoint:
                logger.debug(f"No endpoints found for {project_id}:{environment}")
                return

            organization_id = sample_endpoint.organization_id

            # Query Error status with organization filter for tenant isolation
            error_status = (
                db.query(Status)
                .filter(Status.name == "Error", Status.organization_id == organization_id)
                .first()
            )
            if not error_status:
                logger.warning(
                    f"Could not find Error status in database for organization {organization_id}"
                )
                return

            # Find recently created/updated endpoints in Error status for this project
            # Use QueryBuilder which properly handles soft delete filtering
            recent_error_endpoints = (
                QueryBuilder(db, Endpoint)
                .with_organization_filter(str(organization_id))
                .with_custom_filter(
                    lambda q: q.filter(
                        Endpoint.project_id == project_id,
                        Endpoint.environment == environment,
                        Endpoint.status_id == error_status.id,
                        Endpoint.updated_at >= recent_cutoff,
                    )
                )
                .all()
            )

            if not recent_error_endpoints:
                logger.debug(f"No recent error endpoints found for {project_id}:{environment}")
                return

            # Try to match endpoint by function name from metadata
            target_endpoint = None
            for endpoint in recent_error_endpoints:
                endpoint_metadata = endpoint.endpoint_metadata or {}
                sdk_connection = endpoint_metadata.get("sdk_connection", {})
                function_name = sdk_connection.get("function_name")

                # We don't have the function name directly in the test result,
                # but we can infer it from the endpoint that was recently validated
                # For now, if there's only one recent error endpoint, assume it's the one
                if len(recent_error_endpoints) == 1:
                    target_endpoint = endpoint
                    break

            if not target_endpoint:
                logger.debug(
                    f"Could not identify target endpoint for validation result {result.test_run_id}"
                )
                return

            # Safely access endpoint_metadata (may be None)
            endpoint_metadata = target_endpoint.endpoint_metadata or {}
            function_name = endpoint_metadata.get("sdk_connection", {}).get(
                "function_name", "unknown"
            )

            # Update endpoint status based on test result
            if result.status == "success":
                # Test passed - update to Active status
                # Filter by organization_id for tenant isolation
                active_status = (
                    db.query(Status)
                    .filter(
                        Status.name == "Active",
                        Status.organization_id == target_endpoint.organization_id,
                    )
                    .first()
                )
                if active_status:
                    target_endpoint.status_id = active_status.id
                    db.commit()
                    logger.info(
                        f"🟢 Late validation result: {function_name} updated to Active status"
                    )
                else:
                    logger.error(
                        f"Could not find Active status in database for organization "
                        f"{target_endpoint.organization_id}"
                    )
            else:
                # Test failed - keep Error status but log the actual error
                logger.info(
                    f"Late validation result: {function_name} confirmed as Error - {result.error}"
                )

        except Exception as e:
            logger.error(f"Error handling late validation result: {e}", exc_info=True)


# Global test result handler instance
test_result_handler = TestResultHandler()
