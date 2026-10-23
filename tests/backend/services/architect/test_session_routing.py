"""The workflow path chosen in one Architect turn carries into the next (issue #3009).

Without it every turn started unrouted, so a follow-up such as "Change: drop R3"
lost the PRD guidance. Runs the runner's real save and rebuild against the test
database; only the model and the tool providers are stubbed.
"""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app.services.architect import runner
from rhesis.sdk.agents.architect.agent import ArchitectAgent
from rhesis.sdk.agents.architect.workflow import WorkflowPath
from rhesis.sdk.models.base import BaseLLM


@pytest.fixture
def runner_db(test_db: Session):
    @contextmanager
    def _same_session(*_args, **_kwargs):
        yield test_db

    with patch.object(runner, "get_db_with_tenant_variables", _same_session):
        yield test_db


def _model():
    model = MagicMock(spec=BaseLLM)
    model.model_name = "stub"
    model.a_generate = AsyncMock()
    return model


async def _rebuild(org, user, session_id):
    _, data = await runner.prepare_and_load_session(
        org, user, "Change: drop R3", None, True, session_id
    )
    with (
        patch(
            "rhesis.backend.app.utils.user_model_utils.build_model_or_raise",
            return_value=_model(),
        ),
        patch("rhesis.backend.app.mcp_server.local_tools.LocalToolProvider"),
        patch("rhesis.sdk.agents.tools.ExploreEndpointTool"),
    ):
        agent, _, _ = await runner.build_agent(data, session_id, org, user, None)
    return agent


@pytest.mark.integration
class TestSessionRouting:
    @pytest.mark.asyncio
    async def test_the_workflow_path_survives_to_the_next_turn(
        self, runner_db, test_org_id, authenticated_user_id
    ):
        org, user = test_org_id, authenticated_user_id
        session_id, _ = await runner.prepare_and_load_session(
            org, user, "Turn my PRD into a test foundation", None, True, None
        )
        first = ArchitectAgent(model=_model(), tools=[])
        first._workflow_path = WorkflowPath.PRD
        await runner.persist_state(first, "Here is the plan.", session_id, org, user, False, "x")

        agent = await _rebuild(org, user, session_id)

        assert agent._workflow_path == WorkflowPath.PRD

    @pytest.mark.asyncio
    async def test_a_session_saved_before_the_path_was_kept_starts_unrouted(
        self, runner_db, test_org_id, authenticated_user_id
    ):
        org, user = test_org_id, authenticated_user_id
        session_id, _ = await runner.prepare_and_load_session(org, user, "hi", None, True, None)

        agent = await _rebuild(org, user, session_id)

        assert agent._workflow_path == WorkflowPath.UNSET
