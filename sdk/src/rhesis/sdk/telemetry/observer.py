"""Global AI framework auto-instrumentation."""

import logging
from typing import List

logger = logging.getLogger(__name__)

_instrumented_frameworks = []


def auto_instrument(*frameworks: str) -> List[str]:
    """
    Automatically instrument AI framework operations.

    Traces LangChain chains, LLM calls, tools, etc. with zero configuration.
    Only instruments AI operations (not every function).

    Args:
        *frameworks: Specific frameworks. Recognized values:
                     ``"langchain"``, ``"langgraph"``, ``"autogen"``,
                     ``"agent_framework"`` (alias: ``"maf"`` for
                     Microsoft Agent Framework).
                     If empty, auto-detects all installed frameworks.

    Returns:
        List of successfully instrumented frameworks

    Examples:
        # Auto-detect and instrument (most common)
        from rhesis.sdk.telemetry import auto_instrument
        auto_instrument()

        # Now all LangChain operations are traced
        from langchain.chains import LLMChain
        chain = LLMChain(...)
        result = chain.run("query")  # Automatically traced!

        # Instrument specific framework only
        auto_instrument("langchain")

        # Microsoft Agent Framework
        auto_instrument("agent_framework")  # or "maf"
    """
    from rhesis.sdk.telemetry.integrations import get_all_integrations

    available = get_all_integrations()

    if not frameworks:
        # Auto-detect: try every distinct integration once. The dict can
        # contain aliases pointing at the same instance, so deduplicate by
        # identity to avoid enabling the same integration twice.
        to_instrument = list({id(v): v for v in available.values()}.values())
        logger.info("Auto-detecting AI frameworks...")
    else:
        # Explicit: resolve names through aliases, dedupe identical integrations.
        seen: dict[int, object] = {}
        for name in frameworks:
            integration = available.get(name)
            if integration is not None:
                seen.setdefault(id(integration), integration)
        to_instrument = list(seen.values())

        # Warn about unknown frameworks
        unknown = set(frameworks) - set(available.keys())
        if unknown:
            logger.warning(f"Unknown frameworks: {', '.join(unknown)}")

    global _instrumented_frameworks
    instrumented = []

    for integration in to_instrument:
        if integration.enable():  # type: ignore[attr-defined]
            instrumented.append(integration.framework_name)  # type: ignore[attr-defined]
            _instrumented_frameworks.append(integration)

    if instrumented:
        logger.info(f"Instrumented: {', '.join(instrumented)}")
    else:
        logger.info("No AI frameworks detected")

    return instrumented


def disable_auto_instrument():
    """Disable all auto-instrumentation."""
    global _instrumented_frameworks
    for integration in _instrumented_frameworks:
        integration.disable()
    _instrumented_frameworks = []
    logger.info("Auto-instrumentation disabled")
