"""Input files are looked up only for tests known to have some."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.jobs.execution.batch.invocation import load_input_files_lazy

_LOAD = (
    "rhesis.backend.jobs.execution.executors.output_providers.SingleTurnOutput._load_input_files"
)


def _ctx(tests_with_files):
    ctx = MagicMock()
    ctx.input_files = {}
    ctx.tests_with_files = tests_with_files
    ctx.organization_id, ctx.user_id, ctx.project_id = "org", "user", "project"
    return ctx


@pytest.mark.unit
class TestLoadInputFilesLazy:
    def test_a_test_without_files_opens_no_session(self):
        with (
            patch("rhesis.backend.app.database.get_db_with_tenant_variables") as session,
            patch(_LOAD) as load,
        ):
            assert asyncio.run(load_input_files_lazy(_ctx(set()), "t1")) is None
        session.assert_not_called()
        load.assert_not_called()

    @pytest.mark.parametrize("known", [{"t1"}, None])
    def test_a_test_with_files_or_unknown_is_looked_up(self, known):
        with (
            patch("rhesis.backend.app.database.get_db_with_tenant_variables"),
            patch(_LOAD, return_value=["file"]) as load,
        ):
            ctx = _ctx(known)
            assert asyncio.run(load_input_files_lazy(ctx, "t1")) == ["file"]
        load.assert_called_once()
        assert ctx.input_files["t1"] == ["file"]
