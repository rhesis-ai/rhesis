"""Lifecycle tests for HaystackIntegration.

Covers the parts ``auto_instrument`` depends on: the install probe, the provider precondition, and
that enable/disable leave no residue.
"""

import pytest

pytest.importorskip("haystack")

from haystack import tracing
from opentelemetry import trace as otel_trace

from rhesis.sdk.telemetry.integrations import get_all_integrations
from rhesis.sdk.telemetry.integrations.haystack import (
    integration as integration_module,
)
from rhesis.sdk.telemetry.integrations.haystack.integration import (
    HaystackIntegration,
    get_integration,
    get_trace_id,
    get_trace_url,
    get_tracer,
)


class TestRegistration:
    def test_registered_under_its_framework_name(self):
        assert get_all_integrations()["haystack"] is get_integration()

    def test_framework_name(self):
        assert get_integration().framework_name == "haystack"

    def test_get_integration_is_a_singleton(self):
        assert get_integration() is get_integration()

    def test_no_alias_is_claimed(self):
        """Unlike ``maf``/``adk``, Haystack has one obvious name; no alias should exist."""
        names = get_all_integrations()
        haystack_names = [n for n, i in names.items() if i is get_integration()]
        assert haystack_names == ["haystack"]


class TestIsInstalled:
    def test_true_when_haystack_tracing_is_importable(self):
        assert get_integration().is_installed() is True

    def test_false_when_the_tracing_module_is_missing(self, monkeypatch):
        """The probe is two-step because a ``haystack`` package alone is not enough.

        ``haystack`` is also the name of an abandoned unrelated PyPI distribution, and
        farm-haystack 1.x ships a ``haystack`` package with no ``haystack.tracing`` at all.
        A ``sys.modules`` entry of ``None`` is what the import system treats as "not importable".
        """
        import sys

        monkeypatch.setitem(sys.modules, "haystack.tracing", None)
        assert HaystackIntegration().is_installed() is False


class TestEnableRequiresAProvider:
    def test_refuses_without_an_sdk_tracer_provider(self, monkeypatch, caplog):
        """The default global is a no-op proxy whose tracers silently drop every span."""
        monkeypatch.setattr(
            otel_trace, "get_tracer_provider", lambda: otel_trace.ProxyTracerProvider()
        )
        integration = HaystackIntegration()
        with caplog.at_level("WARNING"):
            assert integration.enable() is False
        assert "RhesisClient" in caplog.text
        assert integration.enabled is False

    def test_enables_against_an_sdk_provider(self, sdk_provider):
        integration = get_integration()
        assert integration.enable() is True
        assert integration.enabled is True

    def test_registers_its_tracer_with_haystack(self, sdk_provider):
        integration = get_integration()
        integration.enable()
        assert tracing.tracer.actual_tracer is integration.callback()


class TestLifecycle:
    def test_enable_is_idempotent(self, sdk_provider):
        integration = get_integration()
        assert integration.enable() is True
        first = integration.callback()
        assert integration.enable() is True
        assert integration.callback() is first

    def test_disable_unregisters_and_clears_state(self, sdk_provider):
        integration = get_integration()
        integration.enable()
        ours = integration.callback()
        integration.disable()

        assert integration.enabled is False
        assert integration.telemetry is None
        # Haystack swaps in its own no-op tracer, so runs after this emit nothing at all.
        assert tracing.tracer.actual_tracer is not ours

    def test_spans_stop_after_disable(self, sdk_provider):
        from haystack import Pipeline, component

        exporter, _ = sdk_provider
        integration = get_integration()
        integration.enable()

        @component
        class Noop:
            @component.output_types(out=str)
            def run(self, q: str) -> dict:
                return {"out": q}

        pipe = Pipeline()
        pipe.add_component("noop", Noop())
        pipe.run({"noop": {"q": "x"}})
        assert exporter.get_finished_spans()

        integration.disable()
        exporter.clear()
        pipe.run({"noop": {"q": "y"}})
        assert exporter.get_finished_spans() == ()

    def test_disable_before_enable_is_a_noop(self):
        integration = HaystackIntegration()
        integration.disable()
        assert integration.enabled is False

    def test_re_enable_after_disable_works(self, sdk_provider):
        integration = get_integration()
        assert integration.enable() is True
        integration.disable()
        assert integration.enable() is True
        assert integration.enabled is True

    def test_flush_is_safe_when_disabled(self):
        HaystackIntegration().flush()  # must not raise


class TestConfigure:
    def test_trace_name_reaches_the_root_span(self, sdk_provider):
        from haystack import Pipeline, component

        exporter, _ = sdk_provider
        integration = get_integration()
        integration.configure(name="My App")
        integration.enable()

        @component
        class Noop:
            @component.output_types(out=str)
            def run(self, q: str) -> dict:
                return {"out": q}

        pipe = Pipeline()
        pipe.add_component("noop", Noop())
        pipe.run({"noop": {"q": "x"}})

        roots = [s for s in exporter.get_finished_spans() if s.parent is None]
        assert roots[0].attributes["haystack.trace.name"] == "My App"

    def test_trace_name_can_come_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("RHESIS_HAYSTACK_TRACE_NAME", "From Env")
        assert HaystackIntegration()._trace_name == "From Env"

    def test_configure_while_enabled_rebuilds_the_tracer(self, sdk_provider):
        integration = get_integration()
        integration.enable()
        first = integration.callback()
        integration.configure(name="Renamed")
        assert integration.enabled is True
        assert integration.callback() is not first

    def test_custom_span_handler_is_used(self, sdk_provider):
        from rhesis.sdk.telemetry.integrations.haystack.tracer import DefaultSpanHandler

        seen = []

        class RecordingHandler(DefaultSpanHandler):
            def handle(self, span, component_type):
                seen.append(span.operation_name)
                super().handle(span, component_type)

        integration = get_integration()
        integration.configure(span_handler=RecordingHandler())
        integration.enable()
        assert isinstance(integration.callback()._span_handler, RecordingHandler)

        from haystack import Pipeline, component

        @component
        class Noop:
            @component.output_types(out=str)
            def run(self, q: str) -> dict:
                return {"out": q}

        pipe = Pipeline()
        pipe.add_component("noop", Noop())
        pipe.run({"noop": {"q": "x"}})
        # The override is the documented redaction hook, so it has to actually be called.
        assert "haystack.component.run" in seen

    def test_frontend_url_from_configure_wins(self, sdk_provider):
        integration = get_integration()
        integration.configure(frontend_url="https://ui.example/")
        integration.enable()
        assert integration.telemetry.frontend_url == "https://ui.example"


class TestTraceHelpers:
    def test_helpers_are_empty_when_not_enabled(self):
        assert get_tracer() is None
        assert get_trace_id() == ""
        assert get_trace_url() == ""

    def test_trace_id_and_url_are_populated_during_a_run(self, sdk_provider):
        from haystack import Pipeline, component

        integration = get_integration()
        integration.enable()

        captured = {}

        @component
        class Peek:
            @component.output_types(out=str)
            def run(self, q: str) -> dict:
                captured["trace_id"] = get_trace_id()
                captured["trace_url"] = get_trace_url()
                return {"out": q}

        pipe = Pipeline()
        pipe.add_component("peek", Peek())
        pipe.run({"peek": {"q": "x"}})

        assert len(captured["trace_id"]) == 32
        assert captured["trace_url"].startswith("http://localhost:3000/traces?open_trace=")
        assert "project_id=proj-test" in captured["trace_url"]
        # Outside the run there is no open trace to point at.
        assert get_trace_id() == ""


class TestResolveConfig:
    def test_reads_the_default_client_when_one_exists(self, sdk_provider):
        project_id, environment, base_url = integration_module._resolve_config()
        assert project_id == "proj-test"
        assert environment == "test"
        assert base_url == "http://localhost:8080"

    def test_falls_back_to_the_environment(self, monkeypatch):
        monkeypatch.setattr("rhesis.sdk.decorators.get_default_client", lambda: None)
        monkeypatch.setenv("RHESIS_PROJECT_ID", "env-proj")
        monkeypatch.setenv("RHESIS_ENVIRONMENT", "staging")
        project_id, environment, _ = integration_module._resolve_config()
        assert project_id == "env-proj"
        assert environment == "staging"
