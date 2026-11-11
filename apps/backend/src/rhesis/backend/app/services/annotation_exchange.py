"""The exchange an annotation judged: what went in and what came back.

Best effort, in a few batched reads. A single-turn test result reads its test's prompt
and the stored output. A multi-turn one reads one turn of its conversation: the turn a
turn annotation names, the first turn a metric's judge pointed at, or else turn 1. A
trace reads the conversation attributes on the annotated span, or on the first root span
of its trace that carries them, falling back to the endpoint's result for the reply. A
test reads its prompt and the explorer output kept in its metadata.
"""

import json
import uuid
from typing import Any, Dict, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import AnnotationTarget, EntityType
from rhesis.backend.app.crud.prompt import get_prompt_contents
from rhesis.backend.app.crud.telemetry import get_root_spans_for_traces, get_spans_by_ids
from rhesis.backend.app.crud.test import get_tests_with_prompts
from rhesis.backend.app.crud.test_result import get_test_results_with_prompts
from rhesis.backend.app.services.annotation_override.common import (
    find_metric_key,
    parse_turn_number,
)

CONVERSATION_INPUT = "rhesis.conversation.input"
CONVERSATION_OUTPUT = "rhesis.conversation.output"
# What an endpoint returned, recorded by the SDK on the turn's root span.
FUNCTION_RESULT = "function.result"

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


def annotated_turn(annotation: models.Annotation, test_metrics: Any) -> Optional[int]:
    """The turn a multi-turn annotation is about, or None for the whole conversation.

    A metric annotation takes the first turn that metric's judge based its verdict on.
    """
    reference = annotation.target_reference or ""
    if annotation.target_type == AnnotationTarget.TURN.value:
        return parse_turn_number(reference)
    if annotation.target_type != AnnotationTarget.METRIC.value:
        return None
    metrics = test_metrics.get("metrics") if isinstance(test_metrics, dict) else None
    if not isinstance(metrics, dict):
        return None
    key = find_metric_key(metrics, reference)
    turns = (metrics.get(key) or {}).get("relevant_turns") if key else None
    numbers = [t for t in turns or [] if isinstance(t, int)]
    return min(numbers) if numbers else None


def conversation_turn(test_output: Any, turn: Optional[int]) -> Optional[Exchange]:
    """One turn of a multi-turn result as (user message, reply); turn 1 when unnamed."""
    summary = test_output.get("conversation_summary") if isinstance(test_output, dict) else None
    if not isinstance(summary, list) or not summary:
        return None
    entries = [e for e in summary if isinstance(e, dict)]
    chosen = next((e for e in entries if str(e.get("turn")) == str(turn)), None)
    chosen = chosen or (entries[0] if entries else None)
    if chosen is None:
        return None
    return _text(chosen.get("penelope_message")), _text(chosen.get("target_response"))


def _test_result_exchanges(
    db: Session, annotations: Sequence[models.Annotation]
) -> Dict[uuid.UUID, Exchange]:
    """``{annotation_id: exchange}``: two annotations on one result can name different turns."""
    results = get_test_results_with_prompts(db, _ids_of(annotations, EntityType.TEST_RESULT))
    # A result whose test is gone still names the prompt it ran.
    orphan_prompts = get_prompt_contents(
        db,
        [r.prompt_id for r in results.values() if r.prompt_id and not (r.test and r.test.prompt)],
    )
    exchanges = {}
    for annotation in annotations:
        result = results.get(annotation.entity_id)
        if result is None:
            continue
        turn = conversation_turn(
            result.test_output, annotated_turn(annotation, result.test_metrics)
        )
        if turn:
            exchanges[annotation.id] = turn
            continue
        prompt = result.test.prompt if result.test else None
        prompt_text = prompt.content if prompt else orphan_prompts.get(result.prompt_id)
        exchanges[annotation.id] = (_text(prompt_text), output_text(result.test_output))
    return exchanges


def _function_result(value: Any) -> Optional[str]:
    """The reply inside an endpoint's recorded result, which may be JSON text."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return _text(value)
    return output_text(value)


def _span_io(span: models.Trace) -> Exchange:
    attributes = span.attributes or {}
    output = _text(attributes.get(CONVERSATION_OUTPUT)) or _function_result(
        attributes.get(FUNCTION_RESULT)
    )
    return _text(attributes.get(CONVERSATION_INPUT)), output


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
    by_entity.update(_trace_exchanges(db, _ids_of(annotations, EntityType.TRACE)))
    by_entity.update(_test_exchanges(db, _ids_of(annotations, EntityType.TEST)))
    by_annotation = _test_result_exchanges(db, annotations)
    return {
        a.id: by_annotation.get(a.id) or by_entity.get(a.entity_id, (None, None))
        for a in annotations
    }
