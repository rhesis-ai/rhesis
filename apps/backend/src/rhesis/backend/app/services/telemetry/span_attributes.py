"""The attribute catalogue: which keys each span kind carries, for building span targets."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.crud.telemetry import AttributeSample, span_attribute_stats
from rhesis.backend.app.schemas.telemetry import (
    AttributeValueCount,
    AttributeValueType,
    SpanAttributeCatalogue,
    SpanAttributeSummary,
    SpanKindAttributes,
)

#: Most recent spans the catalogue reads per kind, so it stays cheap on large projects.
SAMPLE_SIZE = 2000
TOP_VALUES = 10
#: Longer values are cut in ``top_values``.
VALUE_MAX_LENGTH = 200
#: A key is ``unique`` when this share of the spans carrying it have their own value...
UNIQUE_RATIO = 0.9
#: ...and enough spans carry it for that to say something.
UNIQUE_MIN_SPANS = 5


def _value_type(types: list) -> AttributeValueType:
    present = {t for t in types if t != AttributeValueType.NULL}
    if not present:
        return AttributeValueType.NULL
    if len(present) > 1:
        return AttributeValueType.MIXED
    return AttributeValueType(present.pop())


def _is_unique(count: int, distinct: int) -> bool:
    return count >= UNIQUE_MIN_SPANS and distinct >= UNIQUE_RATIO * count


def _summary(row) -> SpanAttributeSummary:
    return SpanAttributeSummary(
        key=row.key,
        coverage=row.count / row.spans,
        type=_value_type(row.types),
        top_values=[AttributeValueCount(**value) for value in row.top_values or []],
        distinct=row.distinct_values,
        unique=_is_unique(row.count, row.distinct_values),
    )


def get_attribute_catalogue(
    db: Session,
    organization_id: str,
    project_id: Optional[str],
    kind: Optional[str],
    days: int,
    limit: int,
) -> SpanAttributeCatalogue:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    sample = AttributeSample(
        since=since,
        kind=kind,
        sample_size=SAMPLE_SIZE,
        attribute_limit=limit,
        value_limit=TOP_VALUES,
        value_length=VALUE_MAX_LENGTH,
    )
    kinds: dict[str, SpanKindAttributes] = {}
    for row in span_attribute_stats(db, organization_id, project_id, sample):
        entry = kinds.setdefault(row.kind, SpanKindAttributes(spans=row.spans, attributes=[]))
        if row.key is not None:
            entry.attributes.append(_summary(row))
    return SpanAttributeCatalogue(
        kinds=kinds,
        sampled_spans=sum(entry.spans for entry in kinds.values()),
        since=since,
    )
