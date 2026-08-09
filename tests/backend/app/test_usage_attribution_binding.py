"""The two places the ambient org actually gets bound: FastAPI and Celery.

Both are easy to break in a way no other test would catch -- the binding
just stops happening and tokens quietly stop being billed -- so they are
pinned here against the real dependency and the real signal handlers.
"""

from __future__ import annotations

import pytest
from celery.signals import task_postrun, task_prerun
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
        # Shaped like a real request at prerun: the org is in `headers`, and
        # the `organization_id` attribute does NOT exist yet, because
        # BaseTask.before_start has not run. An earlier version of these
        # tests set the attribute directly, which meant they asserted the
        # implementation's assumption rather than Celery's actual behaviour,
        # and passed while every Celery task went unattributed.
        return type("_Req", (), {"headers": {"organization_id": organization_id}})()

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


class TestCeleryBindingEndToEnd:
    """Drives Celery's real tracer rather than calling the handlers directly.

    The hand-called tests above can only ever confirm that the handlers do
    what their author expected. This one confirms Celery agrees, which is
    where the bug was: the tracer fires `task_prerun` *before*
    `Task.before_start`, so `request.organization_id` is still unset and
    reading it left every Celery task's tokens unattributed.
    """

    def test_the_org_is_bound_while_the_task_body_runs(self):
        from celery import Celery

        from rhesis.backend.celery.signals import (
            bind_usage_attribution_for_task,
            clear_usage_attribution_for_task,
        )

        app = Celery("usage_attribution_probe", broker="memory://")
        app.conf.task_always_eager = True

        @app.task(name="usage_attribution_probe.observe")
        def observe():
            return current_usage_org()

        # Connect to this app only, so the probe cannot disturb the real one.
        task_prerun.connect(bind_usage_attribution_for_task, weak=False)
        task_postrun.connect(clear_usage_attribution_for_task, weak=False)
        try:
            result = observe.apply_async(headers={"organization_id": "org-from-headers"})
            assert result.get() == "org-from-headers"
        finally:
            task_prerun.disconnect(bind_usage_attribution_for_task)
            task_postrun.disconnect(clear_usage_attribution_for_task)

        assert current_usage_org() is None


class TestWorkerSinkInstallation:
    """The sink has to actually get installed in the worker process.

    Nothing else notices if it does not: models still work, tokens are just
    never counted. This deployment runs `--pool threads`, and
    `worker_process_init` is sent only by the prefork and solo pools, so a
    handler connected to that alone would never fire in production.
    """

    def _reset(self):
        from rhesis.backend.app.utils.usage_tracking import uninstall_usage_sink

        uninstall_usage_sink()

    def test_celeryd_init_installs_the_sink(self):
        """celeryd_init fires for every pool, including threads."""
        from celery.signals import celeryd_init

        from rhesis.backend.app.utils.usage_tracking import accrue_model_tokens
        from rhesis.sdk.models.base import get_default_usage_callback

        self._reset()
        assert get_default_usage_callback() is None

        try:
            celeryd_init.send(sender="main@testhost")
            assert get_default_usage_callback() is accrue_model_tokens
        finally:
            self._reset()

    def test_worker_process_init_also_installs_it(self):
        """Prefork children, where the parent's install does not carry over
        if the platform spawns rather than forks."""
        from celery.signals import worker_process_init

        from rhesis.backend.app.utils.usage_tracking import accrue_model_tokens
        from rhesis.sdk.models.base import get_default_usage_callback

        self._reset()
        try:
            worker_process_init.send(sender=None)
            assert get_default_usage_callback() is accrue_model_tokens
        finally:
            self._reset()
