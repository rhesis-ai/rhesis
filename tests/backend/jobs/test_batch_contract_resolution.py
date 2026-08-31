"""Evaluation contract resolution and threading for batch multi-turn tests.

The batch executor pre-fetches ``test`` objects into ``ExecutionContext`` in a session that
has since closed (see ``ExecutionContext``'s docstring), so resolving a test's contract here
needs its own short-lived session and a fresh re-query -- these tests pin that mechanism down,
plus the fact that it delegates to the same usability rule the live (non-batch) path uses.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rhesis.backend.jobs.execution.batch.context import ExecutionContext
from rhesis.backend.jobs.execution.batch.invocation import (
    _run_multi_turn,
    resolve_contract_lazy,
)

_RESOLVE_MULTI_TURN_CONTRACT = (
    "rhesis.backend.jobs.execution.executors.output_providers.resolve_multi_turn_contract"
)
_RUN_MULTI_TURN = "rhesis.backend.jobs.execution.batch.invocation._run_multi_turn"


def _ctx(**overrides) -> ExecutionContext:
    defaults = dict(
        test_config=MagicMock(),
        test_run=MagicMock(),
        test_set=MagicMock(),
        endpoint=MagicMock(),
        organization_id="org-1",
        user_id="user-1",
    )
    defaults.update(overrides)
    return ExecutionContext(**defaults)


class TestResolveContractLazy:
    """resolve_contract_lazy: fresh session, fresh query, delegates to the shared rule."""

    @pytest.mark.asyncio
    async def test_re_queries_the_test_fresh_and_resolves_its_contract(self):
        ctx = _ctx()
        fresh_test = MagicMock()

        with (
            patch("rhesis.backend.app.database.get_db_with_tenant_variables") as mock_get_db,
            patch(
                "rhesis.backend.app.utils.crud_utils.get_item_detail", return_value=fresh_test
            ) as mock_get_item_detail,
            patch(
                _RESOLVE_MULTI_TURN_CONTRACT,
                return_value=({"prohibited_behavior": ["X"]}, True),
            ) as mock_resolve,
        ):
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db
            mock_get_db.return_value.__exit__.return_value = False

            contract, usable = await resolve_contract_lazy(
                ctx, "3a51f7ae-f7b2-4ff4-8454-9e8f4826afa1"
            )

        mock_get_item_detail.assert_called_once()
        mock_resolve.assert_called_once_with(mock_db, fresh_test, ctx.user_id)
        assert contract == {"prohibited_behavior": ["X"]}
        assert usable is True

    @pytest.mark.asyncio
    async def test_missing_test_is_unusable(self):
        """A test that vanished between prefetch and now must not silently score."""
        ctx = _ctx()

        with (
            patch("rhesis.backend.app.database.get_db_with_tenant_variables") as mock_get_db,
            patch("rhesis.backend.app.utils.crud_utils.get_item_detail", return_value=None),
        ):
            mock_get_db.return_value.__enter__.return_value = MagicMock()
            mock_get_db.return_value.__exit__.return_value = False

            contract, usable = await resolve_contract_lazy(
                ctx, "3a51f7ae-f7b2-4ff4-8454-9e8f4826afa1"
            )

        assert contract is None
        assert usable is False

    @pytest.mark.asyncio
    async def test_an_exception_fails_safe_rather_than_propagating(self):
        """Mirrors load_input_files_lazy's own resilience: one test's infra hiccup must not
        crash the whole batch task."""
        ctx = _ctx()

        with patch(
            "rhesis.backend.app.database.get_db_with_tenant_variables",
            side_effect=RuntimeError("db unavailable"),
        ):
            contract, usable = await resolve_contract_lazy(
                ctx, "3a51f7ae-f7b2-4ff4-8454-9e8f4826afa1"
            )

        assert contract is None
        assert usable is False


class TestRunMultiTurnContractThreading:
    """_run_multi_turn: the resolved contract reaches Penelope, and usability is reported
    back without being applied to penelope_metrics here -- see the returned dict's comment:
    the caller must discard AFTER merging in any additional (non-goal) metrics, or those
    could mask a discarded verdict."""

    @staticmethod
    def _agent(metrics=None):
        agent = MagicMock()
        result = MagicMock()
        result.model_dump.return_value = {
            "conversation_summary": [],
            "metrics": metrics or {},
        }
        agent.a_execute_test = AsyncMock(return_value=result)
        return agent

    @pytest.mark.asyncio
    async def test_resolved_contract_is_passed_to_penelope(self):
        ctx = _ctx()
        test = MagicMock()
        test.test_configuration = {"goal": "Test goal"}
        agent = self._agent(metrics={"goal_achievement": {"is_successful": True}})

        with (
            patch(
                _RESOLVE_MULTI_TURN_CONTRACT, return_value=({"prohibited_behavior": ["X"]}, True)
            ),
            patch("rhesis.backend.app.utils.crud_utils.get_item_detail", return_value=test),
            patch("rhesis.backend.app.database.get_db_with_tenant_variables") as mock_get_db,
            patch("rhesis.backend.jobs.execution.penelope_target.BackendEndpointTarget"),
        ):
            mock_get_db.return_value.__enter__.return_value = MagicMock()
            mock_get_db.return_value.__exit__.return_value = False

            result = await _run_multi_turn(
                ctx, test, "3a51f7ae-f7b2-4ff4-8454-9e8f4826afa1", {}, [], agent
            )

        assert agent.a_execute_test.call_args.kwargs["contract"] == {"prohibited_behavior": ["X"]}
        assert result["contract_usable"] is True
        assert result["penelope_metrics"] == {"goal_achievement": {"is_successful": True}}

    @pytest.mark.asyncio
    async def test_unusable_contract_does_not_run_the_conversation(self):
        """Nothing this run produced could be scored, so the batch path must not run it either.

        Mirrors the live path (see ``test_output_providers``): every verdict would be discarded
        downstream, so running the conversation would only spend target and judge tokens on a
        guaranteed Error.
        """
        ctx = _ctx()
        test = MagicMock()
        test.test_configuration = {"goal": "Test goal"}
        agent = self._agent(metrics={"goal_achievement": {"is_successful": True, "score": 1.0}})

        with (
            patch(_RESOLVE_MULTI_TURN_CONTRACT, return_value=(None, False)),
            patch("rhesis.backend.app.utils.crud_utils.get_item_detail", return_value=test),
            patch("rhesis.backend.app.database.get_db_with_tenant_variables") as mock_get_db,
            patch("rhesis.backend.jobs.execution.penelope_target.BackendEndpointTarget"),
        ):
            mock_get_db.return_value.__enter__.return_value = MagicMock()
            mock_get_db.return_value.__exit__.return_value = False

            result = await _run_multi_turn(
                ctx, test, "3a51f7ae-f7b2-4ff4-8454-9e8f4826afa1", {}, [], agent
            )

        agent.a_execute_test.assert_not_called()
        assert result["contract_usable"] is False
        assert result["penelope_metrics"] == {}
        assert result["output"]["status"] == "error"
