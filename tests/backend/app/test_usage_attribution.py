"""Does the ambient org survive the boundaries real work crosses?

An ambient mechanism fails silently: lose the context and nothing errors,
the tokens just get billed to nobody. So each boundary the code actually
crosses gets its own test, and the two that do *not* propagate on their own
are pinned as such -- if a future Python makes ThreadPoolExecutor copy
context, the explicit wrapper becomes redundant and we should know.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from rhesis.backend.app.usage_attribution import (
    current_usage_org,
    usage_attribution,
    with_usage_attribution,
)


class TestBinding:
    def test_unbound_by_default(self):
        assert current_usage_org() is None

    def test_binds_and_restores(self):
        with usage_attribution("org-1"):
            assert current_usage_org() == "org-1"
        assert current_usage_org() is None

    def test_nests(self):
        with usage_attribution("outer"):
            with usage_attribution("inner"):
                assert current_usage_org() == "inner"
            assert current_usage_org() == "outer"

    def test_restores_even_when_the_body_raises(self):
        with pytest.raises(RuntimeError):
            with usage_attribution("org-1"):
                raise RuntimeError("boom")
        assert current_usage_org() is None

    @pytest.mark.parametrize("empty", ["", None])
    def test_empty_org_binds_as_unattributed(self, empty):
        """The task paths read organization_id off a nullable column. An
        empty string must not become a literal org id of ""."""
        with usage_attribution(empty):
            assert current_usage_org() is None

    @pytest.mark.parametrize("stringified_null", ["None", "none", "null", "NULL", " None "])
    def test_a_stringified_null_binds_as_unattributed(self, stringified_null):
        """`str(user.organization_id)` on an orgless user yields "None", a
        truthy string that passes every `if organization_id:` guard and only
        fails later when the accrual task casts it to a UUID. Review of #2355
        caught exactly that reaching dispatch_accrual."""
        with usage_attribution(stringified_null):
            assert current_usage_org() is None


class TestPropagation:
    @pytest.mark.asyncio
    async def test_survives_asyncio_to_thread(self):
        """The batch runner's persistence hop and the invocation path."""
        with usage_attribution("org-1"):
            assert await asyncio.to_thread(current_usage_org) == "org-1"

    @pytest.mark.asyncio
    async def test_survives_task_fanout(self):
        """The batch runner fans tests out as asyncio Tasks."""
        with usage_attribution("org-1"):
            results = await asyncio.gather(
                *(asyncio.to_thread(current_usage_org) for _ in range(3))
            )
        assert results == ["org-1"] * 3

    def test_thread_pool_executor_loses_it_without_help(self):
        """Pinned deliberately: this is why with_usage_attribution exists.
        The LLM-judge metric strategies and the Penelope target both fan out
        through a raw ThreadPoolExecutor."""
        with usage_attribution("org-1"), ThreadPoolExecutor() as pool:
            assert pool.submit(current_usage_org).result() is None

    def test_thread_pool_executor_keeps_it_when_wrapped(self):
        with usage_attribution("org-1"), ThreadPoolExecutor() as pool:
            assert pool.submit(with_usage_attribution(current_usage_org)).result() == "org-1"

    def test_wrapper_captures_at_wrap_time_not_call_time(self):
        """with_usage_attribution copies the context where it is called, so
        wrapping inside the bound block is what matters -- submitting later
        still bills the org that was ambient at wrap time."""
        with usage_attribution("org-1"):
            wrapped = with_usage_attribution(current_usage_org)

        with ThreadPoolExecutor() as pool:
            assert pool.submit(wrapped).result() == "org-1"

    def test_a_thread_does_not_leak_its_binding_back_out(self):
        """Contexts copy downward only, so a nested bind cannot corrupt the
        caller -- the property that makes per-request binding safe."""

        def bind_inside():
            with usage_attribution("org-other"):
                return current_usage_org()

        with usage_attribution("org-1"), ThreadPoolExecutor() as pool:
            assert pool.submit(with_usage_attribution(bind_inside)).result() == "org-other"
            assert current_usage_org() == "org-1"
