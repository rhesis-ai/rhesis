"""Tests for Google ADK auto-instrumentation integration."""

from unittest.mock import MagicMock

import pytest

from rhesis.sdk.telemetry.integrations.google_adk import (
    GoogleADKIntegration,
    GoogleADKPatchState,
    RHESIS_PLUGIN_NAME,
)


@pytest.fixture(autouse=True)
def reset_patch_state():
    GoogleADKPatchState.reset()
    yield
    GoogleADKPatchState.reset()


class FakeBasePlugin:
    def __init__(self, name: str = "plugin"):
        self.name = name


class FakeCallbackContext:
    def __init__(self):
        self.state = {}


def test_enable_injects_plugin_into_runner(monkeypatch):
    class FakeRunner:
        def __init__(self, *args, **kwargs):
            self.plugins = kwargs.get("plugins", [])

        async def run(self, *args, **kwargs):
            return "ok"

    fake_plugin_module = MagicMock()
    fake_plugin_module.BasePlugin = FakeBasePlugin
    fake_runners = MagicMock()
    fake_runners.Runner = FakeRunner
    fake_google = MagicMock()
    fake_google.adk = MagicMock()
    fake_google.adk.plugins = MagicMock()
    fake_google.adk.plugins.base_plugin = fake_plugin_module
    fake_google.adk.runners = fake_runners

    monkeypatch.setitem(__import__("sys").modules, "google", fake_google)
    monkeypatch.setitem(__import__("sys").modules, "google.adk", fake_google.adk)
    monkeypatch.setitem(__import__("sys").modules, "google.adk.plugins", fake_google.adk.plugins)
    monkeypatch.setitem(
        __import__("sys").modules,
        "google.adk.plugins.base_plugin",
        fake_plugin_module,
    )
    monkeypatch.setitem(__import__("sys").modules, "google.adk.runners", fake_runners)

    integration = GoogleADKIntegration()
    assert integration.enable() is True
    assert GoogleADKPatchState.is_done() is True

    runner = FakeRunner(plugins=[])
    assert any(getattr(plugin, "name", "") == RHESIS_PLUGIN_NAME for plugin in runner.plugins)


def test_disable_resets_runner_patch(monkeypatch):
    class FakeRunner:
        def __init__(self, *args, **kwargs):
            self.plugins = kwargs.get("plugins", [])

    fake_plugin_module = MagicMock()
    fake_plugin_module.BasePlugin = FakeBasePlugin
    fake_runners = MagicMock()
    fake_runners.Runner = FakeRunner
    fake_google = MagicMock()
    fake_google.adk = MagicMock()
    fake_google.adk.plugins = MagicMock()
    fake_google.adk.plugins.base_plugin = fake_plugin_module
    fake_google.adk.runners = fake_runners

    monkeypatch.setitem(__import__("sys").modules, "google", fake_google)
    monkeypatch.setitem(__import__("sys").modules, "google.adk", fake_google.adk)
    monkeypatch.setitem(__import__("sys").modules, "google.adk.plugins", fake_google.adk.plugins)
    monkeypatch.setitem(
        __import__("sys").modules,
        "google.adk.plugins.base_plugin",
        fake_plugin_module,
    )
    monkeypatch.setitem(__import__("sys").modules, "google.adk.runners", fake_runners)

    integration = GoogleADKIntegration()
    integration.enable()
    integration.disable()

    assert integration.enabled is False
    assert GoogleADKPatchState.is_done() is False
