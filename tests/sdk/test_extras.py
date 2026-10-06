"""The single missing-feature error for features that need ``rhesis-sdk[all]``."""

import importlib
import sys

import pytest

from rhesis.sdk._extras import (
    INSTALL_DOCS_URL,
    FullSDKRequiredError,
    full_sdk_message,
    requires_full_sdk,
)

EXPECTED_MESSAGE = (
    "DeepEvalAnswerRelevancy needs the full SDK. Install it with:\n"
    '    pip install "rhesis-sdk[all]"\n'
    "See https://docs.rhesis.ai/sdk/installation#what-to-install"
)


def _uninstall(monkeypatch, package: str) -> None:
    """Make ``import package`` fail as if it were not installed."""
    for name in [m for m in sys.modules if m.startswith(package + ".")]:
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.setitem(sys.modules, package, None)


def _forget(monkeypatch, prefix: str) -> None:
    """Drop already-imported SDK modules so the next import runs their guards again."""
    for name in [m for m in sys.modules if m == prefix or m.startswith(prefix + ".")]:
        monkeypatch.delitem(sys.modules, name)
        parent, _, child = name.rpartition(".")
        # `from parent import child` reads the attribute before sys.modules.
        if parent in sys.modules and hasattr(sys.modules[parent], child):
            monkeypatch.delattr(sys.modules[parent], child)


class TestHelper:
    def test_message(self):
        assert full_sdk_message("DeepEvalAnswerRelevancy") == EXPECTED_MESSAGE
        assert INSTALL_DOCS_URL in EXPECTED_MESSAGE

    def test_missing_package_raises_full_sdk_error(self, monkeypatch):
        _uninstall(monkeypatch, "deepeval")
        with pytest.raises(FullSDKRequiredError) as excinfo:
            with requires_full_sdk("DeepEvalAnswerRelevancy"):
                import deepeval  # noqa: F401

        assert str(excinfo.value) == EXPECTED_MESSAGE
        assert excinfo.value.name == "deepeval"
        # Callers that catch ImportError keep working.
        assert isinstance(excinfo.value, ImportError)

    def test_missing_submodule_of_missing_package(self, monkeypatch):
        _uninstall(monkeypatch, "markitdown")
        with pytest.raises(FullSDKRequiredError):
            with requires_full_sdk("Document extraction"):
                from markitdown._stream_info import StreamInfo  # noqa: F401

    def test_our_own_missing_module_passes_through(self):
        with pytest.raises(ModuleNotFoundError) as excinfo:
            with requires_full_sdk("Something"):
                importlib.import_module("rhesis.sdk.no_such_module")
        assert not isinstance(excinfo.value, FullSDKRequiredError)

    def test_unlisted_package_passes_through(self, monkeypatch):
        _uninstall(monkeypatch, "torch")
        with pytest.raises(ModuleNotFoundError) as excinfo:
            with requires_full_sdk("Something"):
                import torch  # noqa: F401
        assert not isinstance(excinfo.value, FullSDKRequiredError)

    def test_missing_submodule_of_installed_package_passes_through(self):
        # A version mismatch, not a missing install: the real error is more useful.
        with pytest.raises(ModuleNotFoundError) as excinfo:
            with requires_full_sdk("Something"):
                importlib.import_module("litellm.no_such_module")
        assert not isinstance(excinfo.value, FullSDKRequiredError)

    def test_plain_import_error_passes_through(self):
        with pytest.raises(ImportError) as excinfo:
            with requires_full_sdk("Something"):
                raise ImportError("cannot import name 'x' from 'litellm'", name="litellm")
        assert not isinstance(excinfo.value, FullSDKRequiredError)

    def test_outer_guard_names_the_feature(self, monkeypatch):
        _uninstall(monkeypatch, "chonkie")
        with pytest.raises(FullSDKRequiredError) as excinfo:
            with requires_full_sdk("Outer"):
                with requires_full_sdk("Inner"):
                    import chonkie  # noqa: F401
        assert str(excinfo.value).startswith("Outer needs the full SDK.")
        assert not isinstance(excinfo.value.__cause__, FullSDKRequiredError)


class TestGuardedImports:
    def test_deepeval_metric(self, monkeypatch):
        _forget(monkeypatch, "rhesis.sdk.metrics.providers.deepeval")
        _uninstall(monkeypatch, "deepeval")
        import rhesis.sdk.metrics as metrics

        with pytest.raises(FullSDKRequiredError, match="^DeepEvalAnswerRelevancy needs"):
            metrics.DeepEvalAnswerRelevancy  # noqa: B018

    def test_deepeval_provider_module(self, monkeypatch):
        _forget(monkeypatch, "rhesis.sdk.metrics.providers.deepeval")
        _uninstall(monkeypatch, "deepeval")
        with pytest.raises(FullSDKRequiredError, match="^DeepEval metrics needs"):
            importlib.import_module("rhesis.sdk.metrics.providers.deepeval")

    def test_litellm_model(self, monkeypatch):
        _forget(monkeypatch, "rhesis.sdk.models.providers")
        _uninstall(monkeypatch, "litellm")
        import rhesis.sdk.models as models

        with pytest.raises(FullSDKRequiredError, match="^LiteLLM needs"):
            models.LiteLLM  # noqa: B018

    def test_get_model_third_party_provider(self, monkeypatch):
        _forget(monkeypatch, "rhesis.sdk.models.providers")
        _uninstall(monkeypatch, "litellm")
        from rhesis.sdk.models import get_model

        with pytest.raises(FullSDKRequiredError, match="^The 'openai' model provider needs"):
            get_model("openai/gpt-4o")

    def test_litellm_proxy_module(self, monkeypatch):
        _forget(monkeypatch, "rhesis.sdk.models.providers.litellm_proxy")
        _uninstall(monkeypatch, "litellm")
        with pytest.raises(FullSDKRequiredError, match="^The LiteLLM proxy model provider"):
            importlib.import_module("rhesis.sdk.models.providers.litellm_proxy")

    def test_document_extractor(self, monkeypatch):
        _forget(monkeypatch, "rhesis.sdk.services.extractor")
        _uninstall(monkeypatch, "markitdown")
        import rhesis.sdk.services as services

        with pytest.raises(FullSDKRequiredError, match="^DocumentExtractor needs"):
            services.DocumentExtractor  # noqa: B018

    def test_chunker(self, monkeypatch):
        _forget(monkeypatch, "rhesis.sdk.services.chunker")
        _uninstall(monkeypatch, "chonkie")
        with pytest.raises(FullSDKRequiredError, match="^Document chunking needs"):
            importlib.import_module("rhesis.sdk.services.chunker")

    def test_agents(self, monkeypatch):
        _forget(monkeypatch, "rhesis.sdk.agents")
        _uninstall(monkeypatch, "mcp")
        with pytest.raises(FullSDKRequiredError, match=r"^rhesis\.sdk\.agents needs"):
            importlib.import_module("rhesis.sdk.agents")
