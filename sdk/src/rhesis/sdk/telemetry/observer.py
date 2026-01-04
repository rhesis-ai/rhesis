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
        *frameworks: Specific frameworks ("langchain", "langgraph", "autogen").
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
    """
    from rhesis.sdk.telemetry.integrations import get_all_integrations

    available = get_all_integrations()

    if not frameworks:
        # Auto-detect: try all available
        to_instrument = available.values()
        logger.info("Auto-detecting AI frameworks...")
    else:
        # Explicit: only specified frameworks
        to_instrument = [available[name] for name in frameworks if name in available]

        # Warn about unknown frameworks
        unknown = set(frameworks) - set(available.keys())
        if unknown:
            logger.warning(f"Unknown frameworks: {', '.join(unknown)}")

    global _instrumented_frameworks
    instrumented = []

    for integration in to_instrument:
        if integration.enable():
            instrumented.append(integration.framework_name)
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
