"""Give every span one type, using Langfuse's rule.

https://langfuse.com/integrations/native/opentelemetry -- in order:
1. ``ai.operation.type`` if set
2. else ``llm.invoke`` if the span names a model (``ai.model.name``)
3. else ``span``

The backfill migration (alembic/versions/e3b7a1c4d9f2_add_trace_span_type.py)
repeats this rule in SQL. Change both together; tests/backend/alembic/
test_trace_span_type_migration.py runs them against the same cases.
"""

from typing import Any, Mapping

from rhesis.backend.app.constants import AISpanAttributes, SpanType


def _set(value: Any) -> bool:
    # Only a non-empty string counts: SQL's ->> turns a JSON number, bool or null
    # into text, so accepting those here would split the two versions of the rule.
    return isinstance(value, str) and value != ""


def classify_span_type(attributes: Mapping[str, Any] | None) -> str:
    attributes = attributes or {}
    operation_type = attributes.get(AISpanAttributes.OPERATION_TYPE)
    if _set(operation_type):
        return operation_type[: SpanType.MAX_LENGTH]
    if _set(attributes.get(AISpanAttributes.MODEL_NAME)):
        return SpanType.LLM_INVOKE
    return SpanType.SPAN
