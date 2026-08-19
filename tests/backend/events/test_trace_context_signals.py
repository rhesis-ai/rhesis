"""``task_prerun``/``task_postrun`` attach and detach the dispatching
request's trace context, mirroring ``bind_usage_attribution_for_task`` /
``clear_usage_attribution_for_task`` in the same module -- same shape, same
reason: a prefork worker reuses one process across tasks, so a binding left
in place leaks into whatever runs next.
"""

from opentelemetry import trace

from rhesis.backend.events.correlation import prepare_dispatch, resolve_ids


def _headers_with_traceparent():
    """A headers dict carrying a real, valid traceparent -- built the same
    way launch_job builds one, so these tests exercise the real header shape
    rather than a hand-written string.
    """
    headers = {}
    trace_id, span_id = prepare_dispatch(headers)
    return headers, trace_id, span_id


def _task(headers):
    return type("_Task", (), {"request": type("_Req", (), {"headers": headers})()})()


class TestTraceContextBinding:
    def test_prerun_attaches_the_dispatching_trace(self):
        from rhesis.backend.celery.signals import (
            attach_trace_context_for_task,
            detach_trace_context_for_task,
        )

        headers, trace_id, _span_id = _headers_with_traceparent()

        attach_trace_context_for_task(task_id="t1", task=_task(headers))
        try:
            attached_trace_id, _ = resolve_ids()
            assert attached_trace_id == trace_id
        finally:
            detach_trace_context_for_task(task_id="t1")

    def test_postrun_detaches_so_the_next_task_does_not_inherit_it(self):
        from rhesis.backend.celery.signals import (
            attach_trace_context_for_task,
            detach_trace_context_for_task,
        )

        headers, trace_id, _span_id = _headers_with_traceparent()

        attach_trace_context_for_task(task_id="t1", task=_task(headers))
        detach_trace_context_for_task(task_id="t1")

        after_trace_id, _ = resolve_ids()
        assert after_trace_id != trace_id

    def test_a_task_with_no_traceparent_attaches_nothing(self):
        """No headers at all -- a task dispatched outside launch_job."""
        from rhesis.backend.celery.signals import (
            _trace_context_tokens,
            attach_trace_context_for_task,
        )

        before_trace_id, _ = resolve_ids()

        attach_trace_context_for_task(task_id="t1", task=_task({}))

        assert "t1" not in _trace_context_tokens
        after_trace_id, _ = resolve_ids()
        assert after_trace_id != before_trace_id, (
            "resolve_ids' own fallback mints a fresh id each call with "
            "nothing attached -- this just confirms nothing WAS attached"
        )

    def test_postrun_for_an_unknown_task_is_harmless(self):
        """postrun can fire for a task whose prerun never ran (e.g. one
        rejected before start)."""
        from rhesis.backend.celery.signals import detach_trace_context_for_task

        detach_trace_context_for_task(task_id="never-started")  # must not raise

    def test_a_prerun_without_a_task_id_attaches_nothing(self):
        """Nothing to key the detach token by, so attaching would leak into
        whatever runs next in this process."""
        from rhesis.backend.celery.signals import (
            _trace_context_tokens,
            attach_trace_context_for_task,
        )

        headers, _trace_id, _span_id = _headers_with_traceparent()

        attach_trace_context_for_task(task_id=None, task=_task(headers))

        assert None not in _trace_context_tokens

    def test_a_taskless_signal_does_not_blow_up(self):
        from rhesis.backend.celery.signals import (
            attach_trace_context_for_task,
            detach_trace_context_for_task,
        )

        attach_trace_context_for_task(task_id="t1", task=None)
        try:
            pass  # must not raise; nothing to assert, there is no request to read
        finally:
            detach_trace_context_for_task(task_id="t1")

    def test_round_trip_through_launch_job_into_the_worker(self):
        """The exact scenario the design doc calls out: the job's context is
        a child of the dispatching request's, same trace id, survives the
        real launch_job -> Celery header -> task_prerun path end to end.
        """
        from unittest.mock import MagicMock

        from rhesis.backend.celery.signals import (
            attach_trace_context_for_task,
            detach_trace_context_for_task,
        )
        from rhesis.backend.jobs import launch_job

        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("router-span") as span:
            router_trace_id = format(span.get_span_context().trace_id, "032x")

            task = MagicMock()
            task.name = "rhesis.backend.jobs.generate_and_save_test_set"
            task.apply_async.return_value = MagicMock(id="unused")

            launch_job(task)  # no db: only headers/dispatch are under test here

        dispatch_headers = task.apply_async.call_args.kwargs["headers"]
        assert "traceparent" in dispatch_headers
        assert router_trace_id in dispatch_headers["traceparent"]

        attach_trace_context_for_task(task_id="worker-t1", task=_task(dispatch_headers))
        try:
            worker_trace_id, _ = resolve_ids()
            assert worker_trace_id == router_trace_id
        finally:
            detach_trace_context_for_task(task_id="worker-t1")


class TestNoAllZeroTraceIds:
    """The regression that would silently break correlation for a subset of
    users: telemetry export being off must never produce all-zero ids.
    ``resolve_ids`` and ``prepare_dispatch`` do not depend on a registered
    TracerProvider (see correlation.py's module docstring for why they
    cannot), so this holds regardless of whether telemetry is configured in
    this process at all -- the normal case for this test suite.
    """

    def test_resolve_ids_is_never_all_zero(self):
        trace_id, span_id = resolve_ids()
        assert trace_id != "0" * 32
        assert span_id != "0" * 16

    def test_prepare_dispatch_is_never_all_zero(self):
        trace_id, span_id = prepare_dispatch({})
        assert trace_id != "0" * 32
        assert span_id != "0" * 16
