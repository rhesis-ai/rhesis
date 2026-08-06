"""The two places the ambient org actually gets bound: FastAPI and Celery.

Both are easy to break in a way no other test would catch -- the binding
just stops happening and tokens quietly stop being billed -- so they are
pinned here against the real dependency and the real signal handlers.
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from rhesis.backend.app.dependencies import bind_usage_attribution, get_tenant_context
from rhesis.backend.app.usage_attribution import current_usage_org


def _app_seeing_the_org():
    """An app whose routes report whatever org is ambient when they run."""
    app = FastAPI()
    app.dependency_overrides[get_tenant_context] = lambda: ("org-from-request", "user-1")

    @app.get("/async", dependencies=[Depends(bind_usage_attribution)])
    async def async_route():
        return {"org": current_usage_org()}

    @app.get("/sync", dependencies=[Depends(bind_usage_attribution)])
    def sync_route():
        return {"org": current_usage_org()}

    return app


class TestFastAPIBinding:
    """``bind_usage_attribution`` must stay ``async def``.

    A sync dependency runs in the anyio threadpool, and a ContextVar set in
    a child thread is invisible to the request's own task -- which is why
    ``app.scope``'s ContextVar is documented as unusable from handlers. If
    someone drops the ``async``, these fail.
    """

    def test_async_route_sees_the_org(self):
        with TestClient(_app_seeing_the_org()) as client:
            assert client.get("/async").json() == {"org": "org-from-request"}

    def test_sync_route_sees_the_org(self):
        with TestClient(_app_seeing_the_org()) as client:
            assert client.get("/sync").json() == {"org": "org-from-request"}

    def test_the_dependency_is_a_coroutine_function(self):
        import inspect

        assert inspect.isasyncgenfunction(bind_usage_attribution), (
            "bind_usage_attribution must be async; a sync dependency runs in "
            "the anyio threadpool and its ContextVar is invisible to the handler"
        )

    def test_binding_does_not_outlive_the_request(self):
        with TestClient(_app_seeing_the_org()) as client:
            client.get("/async")
        assert current_usage_org() is None

    def test_tenant_db_session_pulls_the_binding_in(self):
        """Attribution rides along with the session dependency rather than
        being opted into per route -- that opt-in is the bug this replaces."""
        import inspect

        from rhesis.backend.app.dependencies import get_tenant_db_session

        depends_on = [
            p.default.dependency
            for p in inspect.signature(get_tenant_db_session).parameters.values()
            if isinstance(p.default, type(Depends(lambda: None)))
        ]
        assert bind_usage_attribution in depends_on


class TestCeleryBinding:
    """Prefork workers reuse a process across tasks, so a binding left in
    place bills the next task's tokens to the previous task's org."""

    def _request(self, organization_id):
        return type("_Req", (), {"organization_id": organization_id})()

    def _task(self, organization_id):
        return type("_Task", (), {"request": self._request(organization_id)})()

    def test_prerun_binds_the_tasks_org(self):
        from rhesis.backend.celery.signals import (
            bind_usage_attribution_for_task,
            clear_usage_attribution_for_task,
        )

        bind_usage_attribution_for_task(task_id="t1", task=self._task("org-1"))
        try:
            assert current_usage_org() == "org-1"
        finally:
            clear_usage_attribution_for_task(task_id="t1")

    def test_postrun_unbinds_so_the_next_task_does_not_inherit_it(self):
        from rhesis.backend.celery.signals import (
            bind_usage_attribution_for_task,
            clear_usage_attribution_for_task,
        )

        bind_usage_attribution_for_task(task_id="t1", task=self._task("org-1"))
        clear_usage_attribution_for_task(task_id="t1")

        assert current_usage_org() is None

    def test_a_task_with_no_org_binds_nothing(self):
        """Rather than inheriting whatever the previous task left behind."""
        from rhesis.backend.celery.signals import (
            bind_usage_attribution_for_task,
            clear_usage_attribution_for_task,
        )

        bind_usage_attribution_for_task(task_id="t1", task=self._task("org-1"))
        clear_usage_attribution_for_task(task_id="t1")
        bind_usage_attribution_for_task(task_id="t2", task=self._task(None))
        try:
            assert current_usage_org() is None
        finally:
            clear_usage_attribution_for_task(task_id="t2")

    def test_postrun_for_an_unknown_task_is_harmless(self):
        """postrun can fire for a task whose prerun never ran (e.g. a task
        rejected before start)."""
        from rhesis.backend.celery.signals import clear_usage_attribution_for_task

        clear_usage_attribution_for_task(task_id="never-started")  # must not raise

    def test_a_prerun_without_a_task_id_binds_nothing(self):
        """Nothing to key the reset token by, so binding would leak into the
        next task in this process. Not falling back to id(task) is deliberate:
        Celery instantiates one task object per task type per worker, so
        concurrent runs of the same task would share a key."""
        from rhesis.backend.celery.signals import (
            _usage_attribution_tokens,
            bind_usage_attribution_for_task,
        )

        bind_usage_attribution_for_task(task_id=None, task=self._task("org-1"))

        assert current_usage_org() is None
        assert None not in _usage_attribution_tokens

    def test_a_taskless_signal_does_not_blow_up(self):
        from rhesis.backend.celery.signals import (
            bind_usage_attribution_for_task,
            clear_usage_attribution_for_task,
        )

        bind_usage_attribution_for_task(task_id="t1", task=None)
        try:
            assert current_usage_org() is None
        finally:
            clear_usage_attribution_for_task(task_id="t1")


@pytest.fixture(autouse=True)
def no_leaked_binding():
    yield
    assert current_usage_org() is None, "a test leaked a usage-attribution binding"
