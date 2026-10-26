"""How a retrieval span records the documents it returned, the same way in every integration.

The ``ai.retrieval.results`` event holds a JSON list of the documents' texts, which is what
``Trace.context`` reads. An empty retrieval records ``[]``.
"""

import json
from typing import Any, Iterable, List, Optional

from rhesis.telemetry.attributes import MAX_CONTENT_LENGTH, AIAttributes, AIEvents


def document_text(document: Any) -> str:
    """The text of one retrieved document: LangChain's ``page_content``, Haystack's
    ``content``, a dict carrying either (or ``text``), or the value itself."""
    if isinstance(document, str):
        return document
    for name in ("page_content", "content", "text"):
        value = document.get(name) if isinstance(document, dict) else getattr(document, name, None)
        if isinstance(value, str):
            return value
    if isinstance(document, (dict, list)):
        return json.dumps(document, default=str)
    return str(document)


def documents_json(documents: Optional[Iterable[Any]], limit: int = MAX_CONTENT_LENGTH) -> str:
    """The documents' texts as a JSON list no longer than ``limit``.

    Whole documents are kept in order while they fit; the first that doesn't is shortened to
    the room left, and the rest are dropped, so the list always parses.
    """
    kept: List[str] = []
    for text in (document_text(d) for d in documents or []):
        if len(json.dumps(kept + [text])) <= limit:
            kept.append(text)
            continue
        room = limit - len(json.dumps(kept + [""]))
        # Escapes make the JSON longer than the text, so shorten until it fits.
        while room > 0 and (over := len(json.dumps(kept + [text[:room]])) - limit) > 0:
            room -= over
        if room > 0:
            kept.append(text[:room])
        break
    return json.dumps(kept)


def record_documents(span: Any, documents: Optional[Iterable[Any]]) -> None:
    """Add the retrieval results event to an OpenTelemetry span."""
    span.add_event(
        AIEvents.RETRIEVAL_RESULTS,
        {AIAttributes.COMPLETION_CONTENT: documents_json(documents)},
    )
