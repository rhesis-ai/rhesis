"""Build the model for each agent role. The only module that knows about providers.

Switching provider is config only:

    DOCS_ASSISTANT_PROVIDER=gemini|openai|anthropic|openai_compatible|litellm   (default gemini)
    DOCS_ASSISTANT_MODEL=<model>                  answer role, and the default for the others
    DOCS_ASSISTANT_<ROLE>_MODEL=<model>           per-role override (TRIAGE, CRITIC)
    DOCS_ASSISTANT_BASE_URL / DOCS_ASSISTANT_API_KEY   override the preset endpoint and key
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from agents import (
    Model,
    ModelSettings,
    OpenAIChatCompletionsModel,
    set_default_openai_api,
    set_trace_processors,
    set_tracing_disabled,
)
from openai import AsyncOpenAI

Role = Literal["answer", "triage", "critic"]

MISSING_KEY_MESSAGE = (
    "No API key for the docs assistant's model provider ({provider}). Set {keys} in "
    "agents/docs-assistant/.env, or DOCS_ASSISTANT_API_KEY."
)


@dataclass(frozen=True)
class Preset:
    base_url: str | None
    key_envs: tuple[str, ...]
    models: dict[str, str]


PRESETS: dict[str, Preset] = {
    "gemini": Preset(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        key_envs=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        models={"answer": "gemini-3.5-flash", "triage": "gemini-3.5-flash-lite"},
    ),
    "openai": Preset(base_url=None, key_envs=("OPENAI_API_KEY",), models={}),
    "anthropic": Preset(
        base_url="https://api.anthropic.com/v1/", key_envs=("ANTHROPIC_API_KEY",), models={}
    ),
    "openai_compatible": Preset(base_url=None, key_envs=(), models={}),
    "litellm": Preset(base_url=None, key_envs=(), models={}),
}

ROLE_SETTINGS: dict[str, ModelSettings] = {
    "answer": ModelSettings(temperature=0.2, include_usage=True),
    "triage": ModelSettings(temperature=0.0, include_usage=True),
    "critic": ModelSettings(temperature=0.0, include_usage=True),
}


def configure_sdk() -> None:
    """Chat Completions only, and no trace upload to OpenAI (it 401s without an OpenAI key)."""
    set_default_openai_api("chat_completions")
    set_tracing_disabled(True)
    set_trace_processors([])


def provider_name() -> str:
    name = os.getenv("DOCS_ASSISTANT_PROVIDER", "gemini").strip().lower()
    if name not in PRESETS:
        raise RuntimeError(
            f"Unknown DOCS_ASSISTANT_PROVIDER={name!r}; use one of {', '.join(PRESETS)}."
        )
    return name


def model_name(role: Role, provider: str | None = None) -> str:
    preset = PRESETS[provider or provider_name()]
    name = (
        os.getenv(f"DOCS_ASSISTANT_{role.upper()}_MODEL")
        or os.getenv("DOCS_ASSISTANT_MODEL")
        or preset.models.get(role)
        or preset.models.get("answer")
    )
    if not name:
        raise RuntimeError(
            f"Set DOCS_ASSISTANT_MODEL for provider {provider or provider_name()}; "
            "it has no default model."
        )
    return name


def api_key(provider: str) -> str | None:
    preset = PRESETS[provider]
    for env in ("DOCS_ASSISTANT_API_KEY", *preset.key_envs):
        if value := os.getenv(env):
            return value
    return None


def base_url(provider: str) -> str | None:
    url = os.getenv("DOCS_ASSISTANT_BASE_URL") or PRESETS[provider].base_url
    if provider == "openai_compatible" and not url:
        raise RuntimeError(
            "DOCS_ASSISTANT_PROVIDER=openai_compatible needs DOCS_ASSISTANT_BASE_URL."
        )
    return url


def build_model(role: Role = "answer") -> Model:
    configure_sdk()
    provider = provider_name()
    name = model_name(role, provider)
    key = api_key(provider)
    if provider == "litellm":
        return _litellm_model(name, key)
    if not key:
        keys = " or ".join(PRESETS[provider].key_envs) or "DOCS_ASSISTANT_API_KEY"
        raise RuntimeError(MISSING_KEY_MESSAGE.format(provider=provider, keys=keys))
    client = AsyncOpenAI(api_key=key, base_url=base_url(provider))
    return OpenAIChatCompletionsModel(model=name, openai_client=client)


def _litellm_model(name: str, key: str | None) -> Model:
    try:
        from agents.extensions.models.litellm_model import LitellmModel
    except ImportError as exc:
        raise RuntimeError(
            "DOCS_ASSISTANT_PROVIDER=litellm needs the extra: uv sync --extra litellm"
        ) from exc
    return LitellmModel(model=name, api_key=key, base_url=os.getenv("DOCS_ASSISTANT_BASE_URL"))


def model_settings(role: Role) -> ModelSettings:
    return ROLE_SETTINGS[role]


@dataclass(frozen=True)
class AgentModels:
    """One model per agent role, so tests can script each role on its own."""

    triage: Model
    answer: Model
    # None turns the critic off; the code checks still run.
    critic: Model | None = None

    @classmethod
    def from_env(cls, *, critic: bool = True) -> AgentModels:
        return cls(
            triage=build_model("triage"),
            answer=build_model("answer"),
            critic=build_model("critic") if critic else None,
        )
