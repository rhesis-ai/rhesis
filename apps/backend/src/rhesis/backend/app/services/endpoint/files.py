"""File handling for endpoint invocation.

Responsible for three concerns:

- Detecting whether an endpoint's request_mapping exposes a ``{{ files }}``
  template variable (and therefore can receive raw file dicts directly).
- Enriching raw base64 file dicts with ``extracted_text`` via the appropriate
  extractor (DocumentExtractor → vision-model fallback when text is empty).
- Injecting extracted file content into a plain-text ``input`` message for
  endpoints that have no native file support.
"""

import logging
from typing import Optional

from rhesis.backend.app.models.endpoint import Endpoint
from rhesis.backend.app.services.invokers.conversation.tracker import (
    mapping_has_template_variable,
)
from rhesis.backend.app.services.model_resolution import resolve_model_for_extraction

logger = logging.getLogger(__name__)


def endpoint_supports_files(endpoint: Endpoint) -> bool:
    """Return True when the endpoint's request_mapping contains ``{{ files }}``.

    Endpoints that expose a ``files`` parameter (e.g. SDK connectors with an
    explicit files field) can receive the full file dict — including base64
    data and extracted_text — and process the content themselves.

    Endpoints that do NOT expose ``{{ files }}`` are plain-text endpoints;
    Rhesis injects the extracted text directly into the ``input`` message so
    the content still reaches the model.
    """
    return mapping_has_template_variable(endpoint, "files")


def inject_file_content_into_input(input_text: str, files: list) -> str:
    """Append extracted file content to a plain-text input message.

    Called when the target endpoint has no native file support.  Each file's
    extracted text is appended as a clearly delimited block so the model can
    reference it, while the original user message is preserved verbatim.

    Files whose content could not be extracted are noted with a placeholder so
    the model knows a file was present but unreadable.
    """
    if not files:
        return input_text

    blocks = []
    for f in files:
        filename = f.get("filename", "file") if isinstance(f, dict) else "file"
        content = (f.get("extracted_text") or "").strip() if isinstance(f, dict) else ""
        if not content:
            content = "[File content could not be extracted]"
        blocks.append(f"--- {filename} ---\n{content}\n--- end of {filename} ---")

    file_section = "\n\n".join(blocks)
    return f"{input_text}\n\n[Attached file(s):]\n\n{file_section}"


def enrich_files_with_extraction(
    files: list,
    db,
    user_id: Optional[str],
) -> list:
    """Add ``extracted_text`` to file entries that don't already have it.

    Files arriving from the test execution path already carry ``extracted_text``
    (set by ``_load_input_files``).  Files from the playground or direct-invoke
    paths are raw base64 dicts that are enriched here so every invocation path
    gets the same extraction behaviour.

    Delegates to ``extract_with_vision_fallback`` (SDK) which owns the full
    strategy: text-layer extraction → vision-model fallback for image-heavy
    documents → EXIF-only fallback when no model is configured.

    Resolves the user's generation model when db and user_id are available;
    runs text-layer extraction only (no vision fallback) when they are not.
    """
    import base64

    from rhesis.sdk.services.extractor import extract_with_vision_fallback

    # Fast path: all files already have extracted text — skip model resolution.
    if files and all(isinstance(f, dict) and "extracted_text" in f for f in files):
        return files

    resolved_model = None
    if db and user_id:
        try:
            from rhesis.backend.app import crud
            from rhesis.backend.app.utils.user_model_utils import get_user_generation_model

            user = crud.get_user_by_id(db, user_id)
            if user:
                resolved_model = resolve_model_for_extraction(get_user_generation_model(db, user))
        except Exception as exc:
            logger.warning("Could not resolve generation model for file extraction: %s", exc)

    logger.info(
        "Enriching %d file(s) for extraction (model=%s)",
        len(files),
        getattr(resolved_model, "model_name", resolved_model),
    )

    enriched = []
    for f in files:
        if not isinstance(f, dict):
            enriched.append(f)
            continue

        if "extracted_text" in f:
            logger.debug("File %s already has extracted_text, skipping", f.get("filename"))
            enriched.append(f)
            continue

        raw_data = f.get("data")
        filename = f.get("filename", "")
        content_type = f.get("content_type", "")

        if raw_data and filename:
            try:
                file_bytes = base64.b64decode(raw_data)
                extracted = extract_with_vision_fallback(
                    file_bytes, filename, content_type, model=resolved_model
                )
                logger.info(
                    "Extracted %d chars from %s (type=%s)",
                    len(extracted or ""),
                    filename,
                    content_type,
                )
                entry = dict(f)
                entry["extracted_text"] = extracted
                enriched.append(entry)
                continue
            except Exception as exc:
                logger.warning("Extraction failed for playground file %s: %s", filename, exc)

        enriched.append(f)

    return enriched
