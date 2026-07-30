import asyncio
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.database import _SCOPE_KEY
from rhesis.backend.app.scope import RequestScope
from rhesis.backend.app.services.explorer.invocation import NO_OUTPUT, EndpointInvoker

# The invoker resolves these at call time, so the source modules are the patch targets.
_DB_CTX_PATCH = "rhesis.backend.app.database.get_db_with_tenant_variables"
_SVC_PATCH = "rhesis.backend.app.dependencies.get_endpoint_service"


def _recording_db_context(test_db, calls):
    """Context manager that records the args each inner session was opened with."""

    @contextmanager
    def _ctx(*args, **kwargs):
        calls.append((args, kwargs))
        yield test_db

    return _ctx


def _invoker(test_db, organization_id, user_id, max_concurrency=10, endpoint_id=None):
    return EndpointInvoker(
        db=test_db,
        endpoint_id=endpoint_id or str(uuid.uuid4()),
        organization_id=organization_id,
        user_id=user_id,
        max_concurrency=max_concurrency,
    )


@pytest.mark.integration
@pytest.mark.service
@pytest.mark.asyncio
class TestEndpointInvoker:
    """Test the shared endpoint invocation helper."""

    async def test_returns_endpoint_output(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """A successful invocation returns the extracted output and no error."""
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "  hello  "})

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _recording_db_context(test_db, [])),
        ):
            invoker = _invoker(test_db, test_org_id, authenticated_user_id)
            output, error = await invoker.invoke("some input")

        assert output == "hello"
        assert error is None

    @pytest.mark.parametrize("endpoint_result", [None, {}, ""])
    async def test_empty_result_becomes_sentinel(
        self, test_db: Session, test_org_id, authenticated_user_id, endpoint_result
    ):
        """An endpoint returning nothing at all yields the NO_OUTPUT sentinel, not an error.

        ``process_endpoint_result`` short-circuits a falsy result to ``{}``, which is the
        only route to the sentinel — see the sibling test for what a present-but-empty
        output does instead.
        """
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value=endpoint_result)

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _recording_db_context(test_db, [])),
        ):
            invoker = _invoker(test_db, test_org_id, authenticated_user_id)
            output, error = await invoker.invoke("some input")

        assert output == NO_OUTPUT
        assert error is None

    async def test_blank_output_uses_extractor_fallback(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """A result with a blank output goes through the extractor's own fallback chain.

        Pins pre-existing behaviour: the sentinel does not apply here, because
        ``process_endpoint_result`` has already substituted its placeholder by the time
        the invoker looks at the output.
        """
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": ""})

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _recording_db_context(test_db, [])),
        ):
            invoker = _invoker(test_db, test_org_id, authenticated_user_id)
            output, error = await invoker.invoke("some input")

        assert output == "No output or metadata available"
        assert error is None

    async def test_failure_is_captured_not_raised(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """Invocation errors come back as ('', message) rather than propagating."""
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(side_effect=RuntimeError("endpoint exploded"))

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _recording_db_context(test_db, [])),
        ):
            invoker = _invoker(test_db, test_org_id, authenticated_user_id)
            output, error = await invoker.invoke("some input")

        assert output == ""
        assert error == "endpoint exploded"

    async def test_inner_sessions_inherit_project_scope(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """The caller's project scope is propagated to every per-invocation session.

        This is the path that has no other coverage: the outer session carries a project,
        and the sessions opened per invocation must be opened with the same one or the
        endpoint lookup inside them comes back empty.
        """
        project_id = str(uuid.uuid4())
        calls = []
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "ok"})

        test_db.info[_SCOPE_KEY] = RequestScope(
            organization_id=test_org_id,
            user_id=authenticated_user_id,
            project_id=project_id,
        )
        try:
            with (
                patch(_SVC_PATCH, return_value=mock_svc),
                patch(_DB_CTX_PATCH, _recording_db_context(test_db, calls)),
            ):
                invoker = _invoker(test_db, test_org_id, authenticated_user_id)
                await invoker.invoke("a")
                await invoker.invoke("b")
        finally:
            test_db.info.pop(_SCOPE_KEY, None)

        assert len(calls) == 2
        for args, _kwargs in calls:
            assert args == (test_org_id, authenticated_user_id, project_id)

    async def test_no_project_scope_passes_empty_string(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """With no project in scope the session factory gets "", its documented default."""
        calls = []
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "ok"})

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _recording_db_context(test_db, calls)),
        ):
            invoker = _invoker(test_db, test_org_id, authenticated_user_id)
            await invoker.invoke("a")

        assert calls[0][0] == (test_org_id, authenticated_user_id, "")

    async def test_concurrency_is_capped(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """No more than max_concurrency invocations are in flight at once."""
        in_flight = 0
        peak = 0

        async def _slow_invoke(**_kwargs):
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1
            return {"output": "ok"}

        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(side_effect=_slow_invoke)

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _recording_db_context(test_db, [])),
        ):
            invoker = _invoker(test_db, test_org_id, authenticated_user_id, max_concurrency=3)
            await asyncio.gather(*[invoker.invoke(f"input {i}") for i in range(12)])

        assert peak <= 3
        assert mock_svc.invoke_endpoint.await_count == 12

    async def test_endpoint_and_tenant_are_passed_through(
        self, test_db: Session, test_org_id, authenticated_user_id
    ):
        """The endpoint id and tenant identity reach invoke_endpoint unchanged."""
        endpoint_id = str(uuid.uuid4())
        mock_svc = MagicMock()
        mock_svc.invoke_endpoint = AsyncMock(return_value={"output": "ok"})

        with (
            patch(_SVC_PATCH, return_value=mock_svc),
            patch(_DB_CTX_PATCH, _recording_db_context(test_db, [])),
        ):
            invoker = _invoker(test_db, test_org_id, authenticated_user_id, endpoint_id=endpoint_id)
            await invoker.invoke("the input")

        kwargs = mock_svc.invoke_endpoint.await_args.kwargs
        assert kwargs["endpoint_id"] == endpoint_id
        assert kwargs["input_data"] == {"input": "the input"}
        assert kwargs["organization_id"] == test_org_id
        assert kwargs["user_id"] == authenticated_user_id
