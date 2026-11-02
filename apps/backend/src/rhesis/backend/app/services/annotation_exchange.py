"""The exchange an annotation judged: what went in and what came back.

Best effort, in a few batched reads. A test result reads its test's prompt and the
stored output; a trace reads the conversation attributes on the annotated span, or
on the first root span of its trace that carries them; a test reads its prompt and
the explorer output kept in its metadata.
"""

import uuid
from typing import Any, Dict, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import EntityType
from rhesis.backend.app.crud.prompt import get_prompt_contents
from rhesis.backend.app.crud.telemetry import get_root_spans_for_traces, get_spans_by_ids
from rhesis.backend.app.crud.test import get_tests_with_prompts
from rhesis.backend.app.crud.test_result import get_test_results_with_prompts

CONVERSATION_INPUT = "rhesis.conversation.input"
CONVERSATION_OUTPUT = "rhesis.conversation.output"

Exchange = Tuple[Optional[str], Optional[str]]


def _text(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value
    return None


def output_text(test_output: Any) -> Optional[str]:
    """What the system under test answered, out of a stored output blob."""
    if isinstance(test_output, dict):
        for key in ("response", "output"):
            text = _text(test_output.get(key))
            if text:
                return text
        return None
    return _text(test_output)


def _ids_of(annotations: Sequence[models.Annotation], entity_type: EntityType) -> list:
    return list({a.entity_id for a in annotations if a.entity_type == entity_type.value})


def _test_result_exchanges(db: Session, ids: list) -> Dict[uuid.UUID, Exchange]:
    results = get_test_results_with_prompts(db, ids)
    # A result whose test is gone still names the prompt it ran.
    orphan_prompts = get_prompt_contents(
        db,
        [r.prompt_id for r in results.values() if r.prompt_id and not (r.test and r.test.prompt)],
    )
    exchanges = {}
    for result_id, result in results.items():
        prompt = result.test.prompt if result.test else None
        prompt_text = prompt.content if prompt else orphan_prompts.get(result.prompt_id)
        exchanges[result_id] = (_text(prompt_text), output_text(result.test_output))
    return exchanges


def _span_io(span: models.Trace) -> Exchange:
    attributes = span.attributes or {}
    return _text(attributes.get(CONVERSATION_INPUT)), _text(attributes.get(CONVERSATION_OUTPUT))


def _trace_exchanges(db: Session, ids: list) -> Dict[uuid.UUID, Exchange]:
    spans = get_spans_by_ids(db, ids)
    roots: Dict[str, Exchange] = {}
    for root in get_root_spans_for_traces(db, list({s.trace_id for s in spans.values()})):
        io = _span_io(root)
        if root.trace_id not in roots and (io[0] or io[1]):
            roots[root.trace_id] = io
    exchanges = {}
    for span_id, span in spans.items():
        io = _span_io(span)
        exchanges[span_id] = io if (io[0] or io[1]) else roots.get(span.trace_id, (None, None))
    return exchanges


def _test_exchanges(db: Session, ids: list) -> Dict[uuid.UUID, Exchange]:
    exchanges = {}
    for test_id, test in get_tests_with_prompts(db, ids).items():
        metadata = test.test_metadata if isinstance(test.test_metadata, dict) else {}
        prompt_text = test.prompt.content if test.prompt else None
        exchanges[test_id] = (_text(prompt_text), _text(metadata.get("output")))
    return exchanges


def exchanges_for(
    db: Session, annotations: Sequence[models.Annotation]
) -> Dict[uuid.UUID, Exchange]:
    """``{annotation_id: (input, output)}``; ``(None, None)`` when nothing can be found."""
    by_entity: Dict[uuid.UUID, Exchange] = {}
    by_entity.update(_test_result_exchanges(db, _ids_of(annotations, EntityType.TEST_RESULT)))
    by_entity.update(_trace_exchanges(db, _ids_of(annotations, EntityType.TRACE)))
    by_entity.update(_test_exchanges(db, _ids_of(annotations, EntityType.TEST)))
    return {a.id: by_entity.get(a.entity_id, (None, None)) for a in annotations}
