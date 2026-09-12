"""``services/tool`` must not query the database on the event loop.

``POST /tools/test-connection`` and ``POST /tools/jira/create-ticket-from-task``
are ``async def`` handlers holding an ``OffLoopSession``. The session work they
delegate to these services has to run inside ``anyio.to_thread.run_sync``.
``tests/backend/test_no_sync_db_on_loop.py`` cannot see inside a handler; these
tests are the check that the work actually left the loop.
"""

import threading
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.app.routers import tools as tools_router
from rhesis.backend.app.services.tool.mcp import operations as mcp_operations
from rhesis.backend.app.services.tool.rest import health as rest_health
from rhesis.backend.app.services.tool.rest import jira as rest_jira
from rhesis.backend.app.services.tool.rest.jira import JiraRestClient
from tests.backend._helpers import records_thread as _recorder


@pytest.mark.unit
@pytest.mark.asyncio
class TestRestHealthCheckRunsDatabaseWorkOffTheLoop:
    async def test_tool_lookup_happens_in_a_worker_thread(self):
        threads: list = []
        tool = MagicMock(credentials='{"NOTION_TOKEN": "tok"}')
        tool.tool_provider_type.type_value = "notion"
        client = MagicMock(health_check=AsyncMock(return_value={"is_authenticated": "Yes"}))

        with (
            patch.object(rest_health, "tool_crud") as tool_crud,
            patch.object(rest_health, "build_client", return_value=client),
        ):
            tool_crud.get_tool.side_effect = _recorder(threads, tool)
            result = await rest_health.run_rest_health_check(
                MagicMock(), "org", tool_id=str(uuid.uuid4()), user_id="user"
            )

        assert result == {"is_authenticated": "Yes"}
        assert threads and threading.get_ident() not in threads

    async def test_provider_type_lookup_happens_in_a_worker_thread(self):
        threads: list = []
        client = MagicMock(health_check=AsyncMock(return_value={"is_authenticated": "Yes"}))

        with (
            patch.object(rest_health, "type_lookup_crud") as type_lookup_crud,
            patch.object(rest_health, "build_client", return_value=client),
        ):
            type_lookup_crud.get_type_lookup.side_effect = _recorder(
                threads, MagicMock(type_value="github")
            )
            await rest_health.run_rest_health_check(
                MagicMock(), "org", provider_type_id=uuid.uuid4(), credentials={}
            )

        assert threads and threading.get_ident() not in threads


@pytest.mark.unit
@pytest.mark.asyncio
class TestJiraTicketCreationRunsDatabaseWorkOffTheLoop:
    async def test_reads_and_writeback_happen_in_worker_threads(self):
        threads: list = []
        task_id = uuid.uuid4()
        tool_id = str(uuid.uuid4())

        task = MagicMock(title="Fix it", description="details", task_metadata={})
        tool = MagicMock(tool_metadata={"space_key": "PROJ"})
        client = MagicMock(spec=JiraRestClient)
        client.create_issue = AsyncMock(
            return_value={"issue_key": "PROJ-1", "issue_url": "https://j/browse/PROJ-1"}
        )

        with (
            patch.object(rest_jira, "task_crud") as task_crud,
            patch.object(rest_jira, "tool_crud") as tool_crud,
            patch(
                "rhesis.backend.app.services.tool.rest.config.get_rest_client",
                return_value=client,
            ),
        ):
            task_crud.get_task.side_effect = _recorder(threads, task)
            task_crud.update_task.side_effect = _recorder(threads)
            tool_crud.get_tool.return_value = tool

            result = await rest_jira.create_jira_ticket_from_task(
                task_id, tool_id, MagicMock(), "org", "user"
            )

        assert result["issue_key"] == "PROJ-1"
        assert task.task_metadata["jira_issue"]["issue_key"] == "PROJ-1"
        assert len(threads) == 2  # the load segment and the write-back segment
        assert threading.get_ident() not in threads


@pytest.mark.unit
@pytest.mark.asyncio
class TestMcpHealthCheckResolvesClientsOffTheLoop:
    async def test_saved_tool_client_is_resolved_in_a_worker_thread(self):
        threads: list = []
        answer = {"success": True, "final_answer": '{"authenticated": true, "identity": "a"}'}

        with (
            patch.object(
                mcp_operations,
                "_resolve_tool_client",
                _recorder(threads, (object(), "gitlab", None)),
            ),
            patch.object(mcp_operations, "_run_agent", new=AsyncMock(return_value=answer)),
        ):
            result = await mcp_operations.mcp_health_check(
                organization_id="org", user_id="user", tool_id="t1"
            )

        assert result["is_authenticated"] == "Yes"
        assert threads and threading.get_ident() not in threads

    async def test_unsaved_credentials_client_is_resolved_in_a_worker_thread(self):
        threads: list = []
        answer = {"success": True, "final_answer": '{"authenticated": true, "identity": "a"}'}

        with (
            patch.object(
                mcp_operations,
                "_resolve_params_client",
                _recorder(threads, (object(), "gitlab", None)),
            ),
            patch.object(mcp_operations, "_run_agent", new=AsyncMock(return_value=answer)),
        ):
            await mcp_operations.mcp_health_check(
                organization_id="org",
                user_id="user",
                provider_type_id="pt1",
                credentials={"TOKEN": "x"},
            )

        assert threads and threading.get_ident() not in threads


@pytest.mark.unit
class TestConnectionTargetResolution:
    """``_resolve_connection_target`` keeps the pre-await behaviour of the route."""

    def test_saved_tool_override_swaps_in_the_stored_provider_and_metadata(self):
        tool_id = str(uuid.uuid4())
        provider_type_id = uuid.uuid4()
        existing = MagicMock(
            credentials='{"GITLAB_API_URL": "https://gl/api/v4"}',
            tool_metadata={"project": {"namespace": "group/proj"}},
            tool_provider_type_id=provider_type_id,
        )
        existing.tool_provider_type.type_value = "gitlab"
        request = MagicMock(
            tool_id=tool_id,
            provider_type_id=None,
            credentials={"GITLAB_PERSONAL_ACCESS_TOKEN": "tok"},
            tool_metadata=None,
        )

        with (
            patch.object(tools_router, "tool_crud") as tool_crud,
            patch.object(tools_router, "resolve_provider", return_value="gitlab"),
        ):
            tool_crud.get_tool.return_value = existing
            target = tools_router._resolve_connection_target(MagicMock(), request, "org", "user")

        assert target.provider == "gitlab"
        assert target.tool_id is None  # credentials are tested, not the saved tool
        assert target.provider_type_id == provider_type_id
        assert target.credentials["GITLAB_API_URL"] == "https://gl/api/v4"
        assert target.tool_metadata == {"project": {"namespace": "group/proj"}}

    def test_plain_request_passes_through_to_resolve_provider(self):
        provider_type_id = uuid.uuid4()
        request = MagicMock(
            tool_id=None,
            provider_type_id=provider_type_id,
            credentials={"NOTION_TOKEN": "tok"},
            tool_metadata=None,
        )

        with patch.object(tools_router, "resolve_provider", return_value="notion") as resolve:
            target = tools_router._resolve_connection_target(MagicMock(), request, "org", "user")

        assert target.provider == "notion"
        assert target.provider_type_id == provider_type_id
        assert resolve.call_args.kwargs["tool_id"] is None


@pytest.mark.unit
@pytest.mark.asyncio
class TestMcpQueryResolvesItsClientOffTheLoop:
    """``POST /services/mcp/query`` never put a Session in its handler signature,
    so the guard test never flagged it -- but ``query_mcp`` opened one through
    ``ctx.get_db()`` on the event loop all the same."""

    async def test_tool_config_is_resolved_in_a_worker_thread(self):
        threads: list = []
        answer = {"success": True, "final_answer": "done"}

        with (
            patch.object(
                mcp_operations,
                "_resolve_query_client",
                _recorder(threads, (object(), "notion", None)),
            ),
            patch.object(mcp_operations, "_run_agent", new=AsyncMock(return_value=answer)),
        ):
            result = await mcp_operations.query_mcp(
                query="list the pages",
                tool_id="t1",
                ctx=MagicMock(organization_id="org", user_id="user"),
            )

        assert result == answer
        assert threads and threading.get_ident() not in threads

    async def test_the_context_session_factory_is_what_gets_used(self):
        """``ctx.get_db()``, not ``get_db_with_tenant_variables`` -- the caller's
        project scope has to survive the move into the thread."""
        ctx = MagicMock(organization_id="org", user_id="user")
        db = ctx.get_db.return_value.__enter__.return_value

        with patch.object(
            mcp_operations, "_get_mcp_tool_config", return_value=(object(), "notion", None)
        ) as get_config:
            mcp_operations._resolve_query_client(ctx, "t1")

        get_config.assert_called_once_with(db, "t1", "org", "user")

    async def test_missing_user_id_still_raises_before_any_lookup(self):
        resolve = MagicMock()

        with patch.object(mcp_operations, "_resolve_query_client", resolve):
            with pytest.raises(ValueError, match="user_id is required"):
                await mcp_operations.query_mcp(
                    query="list the pages",
                    tool_id="t1",
                    ctx=MagicMock(organization_id="org", user_id=""),
                )

        resolve.assert_not_called()
