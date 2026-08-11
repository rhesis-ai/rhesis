"""Contract tests for the BaseLLM streaming fallback.

Guards the invariant behind a 38-hour architect worker deadlock: the
default ``generate_stream`` must reach a provider without crossing the
sync bridge (``run_sync``).  Crossing it from the background event loop
self-deadlocks -- the loop blocks on a coroutine only it can run.

A provider satisfies the contract by overriding ``generate_stream`` (true
streaming) or by implementing ``a_generate`` (the awaited fallback).
"""

import importlib

import pytest

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.factory import (
    UNIFIED_MODEL_REGISTRY,
    ModelType,
    _ProviderSpec,
)


def _language_provider_specs():
    """Every registered language provider, as pytest params keyed by name."""
    params = []
    for provider, by_type in sorted(UNIFIED_MODEL_REGISTRY.items()):
        spec = by_type.get(ModelType.LANGUAGE)
        # Callable entries are special-case wrappers, not plain class specs.
        if isinstance(spec, _ProviderSpec):
            params.append(pytest.param(spec, id=provider))
    return params


@pytest.mark.parametrize("spec", _language_provider_specs())
def test_provider_streams_without_sync_bridge(spec):
    """Each provider either streams natively or supports the async fallback."""
    try:
        module = importlib.import_module(spec.module)
    except ImportError as exc:  # optional heavy deps (e.g. torch)
        pytest.skip(f"provider dependencies unavailable: {exc}")

    cls = getattr(module, spec.class_name)
    assert issubclass(cls, BaseLLM)

    overrides_stream = cls.generate_stream is not BaseLLM.generate_stream
    implements_a_generate = cls.a_generate is not BaseLLM.a_generate

    assert overrides_stream or implements_a_generate, (
        f"{cls.__name__} inherits the BaseLLM.generate_stream fallback but "
        "does not implement a_generate(), so streaming would raise "
        "NotImplementedError. Override generate_stream() for true streaming "
        "or implement a_generate()."
    )


def test_base_fallback_yields_from_a_generate():
    """The inherited fallback awaits a_generate rather than calling generate.

    Calling the sync ``generate()`` here is what deadlocked the worker:
    it bridges through ``run_sync`` while already on the event loop.
    """
    calls = []

    class StubLLM(BaseLLM):
        def load_model(self, *args, **kwargs):
            return None

        def generate(self, *args, **kwargs):
            calls.append("generate")
            return "sync"

        async def a_generate(self, *args, **kwargs):
            calls.append("a_generate")
            return "async"

        def generate_batch(self, *args, **kwargs):
            return []

    llm = StubLLM(model_name="stub")

    async def collect():
        return [chunk async for chunk in llm.generate_stream(prompt="hi")]

    import asyncio

    assert asyncio.run(collect()) == ["async"]
    assert calls == ["a_generate"], f"fallback took the sync path: {calls}"
