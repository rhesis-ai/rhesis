import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.adaptive_testing import generate_outputs_for_tests, get_tree_tests


def _mock_db_context(test_db):
    """Return a context manager that yields the test DB session.

    Used to patch ``get_db_with_tenant_variables`` so that per-task sessions
    in ``generate_outputs_for_tests`` reuse the same test session.
    """

    @contextmanager
    def _ctx(*_args, **_kwargs):
        yield test_db

    return _ctx


# Patch target for the per-task session factory imported inside the function.
_DB_CTX_PATCH = "rhesis.backend.app.database.get_db_with_tenant_variables"
_SVC_PATCH = "rhesis.backend.app.dependencies.get_endpoint_service"


@pytest.mark.integration
@pytest.mark.service
@pytest.mark.asyncio
class TestGenerateOutputsForTests:
    """Test generate_outputs_for_tests with mocked endpoint response."""

    async def test_updates_test_metadata_output(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        """Endpoint response output is stored in each test's test_metadata."""
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "mocked endpoint response"})
        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            result = await generate_outputs_for_tests(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                endpoint_id=str(uuid.uuid4()),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                overwrite=True,
            )

        assert result["generated"] == 3
        assert len(result["failed"]) == 0
        assert len(result["updated"]) == 3

        test_db.commit()
        nodes = get_tree_tests(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        for node in nodes:
            assert node.output == "mocked endpoint response"

    async def test_test_set_not_found_raises(
        self,
        test_db: Session,
        test_org_id,
        authenticated_user_id,
    ):
        """Unknown test set identifier raises ValueError."""
        mock_svc = MagicMock()
        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            with pytest.raises(ValueError, match="Test set not found"):
                await generate_outputs_for_tests(
                    db=test_db,
                    test_set_identifier=str(uuid.uuid4()),
                    endpoint_id=str(uuid.uuid4()),
                    organization_id=test_org_id,
                    user_id=authenticated_user_id,
                )
        mock_svc.invoke_endpoint.assert_not_called()

    async def test_filter_by_test_ids(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        """When test_ids is provided, only those tests are invoked."""
        tests = get_tree_tests(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        one_test_id = tests[0].id

        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "single test output"})
        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            result = await generate_outputs_for_tests(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                endpoint_id=str(uuid.uuid4()),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                test_ids=[uuid.UUID(one_test_id)],
                overwrite=True,
            )

        assert result["generated"] == 1
        assert len(result["updated"]) == 1
        assert result["updated"][0]["test_id"] == one_test_id
        assert result["updated"][0]["output"] == "single test output"
        assert mock_svc.invoke_endpoint.await_count == 1

    async def test_failed_invocation_recorded(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        """When invoke_endpoint raises for one test, it is recorded in failed."""
        _ = get_tree_tests(
            db=test_db,
            test_set_id=adaptive_test_set.id,
            organization_id=test_org_id,
            user_id=authenticated_user_id,
        )
        call_count = 0

        async def mock_invoke(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Endpoint timeout")
            return {"output": "ok"}

        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(side_effect=mock_invoke)
        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            result = await generate_outputs_for_tests(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                endpoint_id=str(uuid.uuid4()),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                overwrite=True,
            )

        assert result["generated"] == 2
        assert len(result["failed"]) == 1
        assert len(result["updated"]) == 2
        assert "timeout" in result["failed"][0]["error"]

    async def test_generate_outputs_filter_by_topic_include_subtopics(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        """With topic set and include_subtopics=True, generates for topic and all subtopics."""
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "generated"})
        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            result = await generate_outputs_for_tests(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                endpoint_id=str(uuid.uuid4()),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                topic="Safety",
                include_subtopics=True,
                overwrite=True,
            )
        # Safety has 1 test; Safety/Violence has 2 tests -> 3 total
        assert result["generated"] == 3
        assert len(result["failed"]) == 0
        assert len(result["updated"]) == 3
        assert mock_svc.invoke_endpoint.await_count == 3

    async def test_generate_outputs_filter_by_topic_exclude_subtopics(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        """include_subtopics=False: only tests directly under the topic are generated."""
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "generated"})
        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            result = await generate_outputs_for_tests(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                endpoint_id=str(uuid.uuid4()),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                topic="Safety",
                include_subtopics=False,
                overwrite=True,
            )
        # Only 1 test is directly under Safety (not under Safety/Violence)
        assert result["generated"] == 1
        assert len(result["failed"]) == 0
        assert len(result["updated"]) == 1
        assert mock_svc.invoke_endpoint.await_count == 1

    async def test_generate_outputs_filter_by_leaf_topic(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        """Filtering by leaf topic (Safety/Violence) generates only that topic's tests."""
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "generated"})
        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            result = await generate_outputs_for_tests(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                endpoint_id=str(uuid.uuid4()),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                topic="Safety/Violence",
                include_subtopics=False,
                overwrite=True,
            )
        assert result["generated"] == 2
        assert len(result["updated"]) == 2
        assert mock_svc.invoke_endpoint.await_count == 2

    async def test_skips_tests_with_existing_output(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        """When overwrite=False, tests that already have outputs are skipped."""
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "generated"})
        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            result = await generate_outputs_for_tests(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                endpoint_id=str(uuid.uuid4()),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                overwrite=False,
            )
        assert result["generated"] == 0
        assert result["skipped"] == 3

    async def test_overwrite_regenerates_existing_output(
        self,
        test_db: Session,
        adaptive_test_set,
        test_org_id,
        authenticated_user_id,
    ):
        """When overwrite=True, tests are regenerated even if they have outputs."""
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "regenerated"})
        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _mock_db_context(test_db)),
        ):
            result = await generate_outputs_for_tests(
                db=test_db,
                test_set_identifier=str(adaptive_test_set.id),
                endpoint_id=str(uuid.uuid4()),
                organization_id=test_org_id,
                user_id=authenticated_user_id,
                overwrite=True,
            )
        assert result["generated"] == 3
        assert result["skipped"] == 0
