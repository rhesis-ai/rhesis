"""Shared model-resolution utilities.

These helpers convert an evaluation-model value — which may arrive as a
plain string (e.g. ``"openai/gpt-4o"``), a ``BaseLLM`` instance, or
``None`` — into a concrete ``BaseLLM`` that SDK extractors and other
vision-capable components can use.

Placing the logic here makes it accessible to both the service layer
(``app/services/endpoint/``) and the task layer (``tasks/execution/``)
without either having to reach into the other's package.
"""

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from rhesis.sdk.models.base import BaseLLM

logger = logging.getLogger(__name__)


def resolve_model_for_extraction(model) -> Optional["BaseLLM"]:
    """Return a ``BaseLLM`` instance suitable for vision-based extraction.

    Accepts:
    - A ``BaseLLM`` instance — returned as-is.
    - A model-name string such as ``"openai/gpt-4o"`` or
      ``"vertex_ai/gemini-2.5-flash"`` — resolved via
      ``get_language_model``.
    - ``None`` or any other type — returns ``None`` so callers can fall
      back gracefully (e.g. EXIF-only image extraction).

    Exceptions from ``get_language_model`` (missing credentials, unknown
    provider, etc.) are caught and logged as warnings so that the caller
    can continue without a vision model rather than failing entirely.
    """
    from rhesis.sdk.models.base import BaseLLM

    if isinstance(model, BaseLLM):
        return model
    if isinstance(model, str):
        try:
            from rhesis.sdk.models.factory import get_language_model

            return get_language_model(model)
        except Exception as exc:
            logger.warning("Could not resolve model '%s' for extraction: %s", model, exc)
    return None
