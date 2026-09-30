import pytest
from agents import OpenAIChatCompletionsModel

from docs_assistant import models

PROVIDER_ENVS = [
    "DOCS_ASSISTANT_PROVIDER",
    "DOCS_ASSISTANT_MODEL",
    "DOCS_ASSISTANT_TRIAGE_MODEL",
    "DOCS_ASSISTANT_CRITIC_MODEL",
    "DOCS_ASSISTANT_BASE_URL",
    "DOCS_ASSISTANT_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in PROVIDER_ENVS:
        monkeypatch.delenv(name, raising=False)


def _base_url(model) -> str:
    return str(model._client.base_url)


def test_gemini_is_the_default(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    model = models.build_model("answer")
    assert isinstance(model, OpenAIChatCompletionsModel)
    assert model.model == "gemini-3.5-flash"
    assert _base_url(model) == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert models.build_model("triage").model == "gemini-3.5-flash-lite"
    # No triage default for critic, so it follows the answer model.
    assert models.build_model("critic").model == "gemini-3.5-flash"


def test_model_overrides_per_role(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g-key")
    monkeypatch.setenv("DOCS_ASSISTANT_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("DOCS_ASSISTANT_TRIAGE_MODEL", "gemini-3.1-flash-lite")
    assert models.build_model("answer").model == "gemini-3.8-flash"
    assert models.build_model("triage").model == "gemini-3.1-flash-lite"
    assert models.build_model("critic").model == "gemini-3.8-flash"


def test_openai_uses_its_default_endpoint_and_needs_a_model(monkeypatch):
    monkeypatch.setenv("DOCS_ASSISTANT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "o-key")
    with pytest.raises(RuntimeError, match="Set DOCS_ASSISTANT_MODEL"):
        models.build_model()
    monkeypatch.setenv("DOCS_ASSISTANT_MODEL", "some-openai-model")
    model = models.build_model()
    assert model.model == "some-openai-model"
    assert _base_url(model).startswith("https://api.openai.com/")


def test_anthropic_preset(monkeypatch):
    monkeypatch.setenv("DOCS_ASSISTANT_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a-key")
    monkeypatch.setenv("DOCS_ASSISTANT_MODEL", "some-claude-model")
    assert _base_url(models.build_model()) == "https://api.anthropic.com/v1/"


def test_openai_compatible_needs_a_base_url(monkeypatch):
    monkeypatch.setenv("DOCS_ASSISTANT_PROVIDER", "openai_compatible")
    monkeypatch.setenv("DOCS_ASSISTANT_MODEL", "local-model")
    monkeypatch.setenv("DOCS_ASSISTANT_API_KEY", "k")
    with pytest.raises(RuntimeError, match="needs DOCS_ASSISTANT_BASE_URL"):
        models.build_model()
    monkeypatch.setenv("DOCS_ASSISTANT_BASE_URL", "http://localhost:11434/v1/")
    assert _base_url(models.build_model()) == "http://localhost:11434/v1/"


def test_missing_key_names_the_env_vars(monkeypatch):
    with pytest.raises(RuntimeError, match="API key.*GOOGLE_API_KEY or GEMINI_API_KEY"):
        models.build_model()


def test_unknown_provider(monkeypatch):
    monkeypatch.setenv("DOCS_ASSISTANT_PROVIDER", "nope")
    with pytest.raises(RuntimeError, match="Unknown DOCS_ASSISTANT_PROVIDER"):
        models.build_model()


def test_litellm_without_the_extra_says_how_to_install(monkeypatch):
    monkeypatch.setenv("DOCS_ASSISTANT_PROVIDER", "litellm")
    monkeypatch.setenv("DOCS_ASSISTANT_MODEL", "gemini/gemini-3.5-flash")
    try:
        import litellm  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="uv sync --extra litellm"):
            models.build_model()
    else:
        pytest.skip("litellm extra installed")
