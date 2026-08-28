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
      ``user_model_utils.ensure_language_model``.
    - ``None`` or any other type — returns ``None`` so callers can fall
      back gracefully (e.g. EXIF-only image extraction).

    Goes through ``ensure_language_model`` rather than the SDK factory
    directly so the resulting instance is stamped: the only caller,
    ``resolve_model_for_extraction`` at the endpoint-files layer, feeds it
    ``resolve_model(db, user, "generation")``, which returns a bare string
    precisely when the user's default model construction failed once
    already and is being retried -- the same case
    ``ensure_language_model`` exists to stamp correctly.

    Exceptions (missing credentials, unknown provider, etc.) are caught and
    logged as warnings so that the caller can continue without a vision
    model rather than failing entirely.
    """
    from rhesis.backend.app.utils.user_model_utils import ensure_language_model
    from rhesis.sdk.models.base import BaseLLM

    if isinstance(model, BaseLLM):
        return model
    if isinstance(model, str):
        try:
            return ensure_language_model(model)
        except Exception as exc:
            logger.warning("Could not resolve model '%s' for extraction: %s", model, exc)
    return None
