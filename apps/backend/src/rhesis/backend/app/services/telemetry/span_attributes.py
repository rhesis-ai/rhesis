"""The attribute catalogue: which keys each span kind carries, for building span targets."""

import difflib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

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

#: A metric's ``where`` keys are checked against the spans of this many days...
KEY_CHECK_DAYS = 7
#: ...reading up to this many keys per kind, the most the catalogue route returns.
KEY_CHECK_LIMIT = 500
#: How alike an unknown key and a known one must be for the known one to be suggested.
KEY_SUGGESTION_CUTOFF = 0.6


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


def where_attribute_keys(target: Any) -> List[str]:
    """The attribute keys a target's ``where`` conditions read; special fields aren't keys."""
    from rhesis.sdk.metrics.conditions import ATTRIBUTE_PREFIX, SPECIAL_FIELDS

    keys: List[str] = []
    for condition in target.where or ():
        if condition.field in SPECIAL_FIELDS:
            continue
        key = condition.field.removeprefix(ATTRIBUTE_PREFIX)
        if key not in keys:
            keys.append(key)
    return keys


def _best_coverage(catalogue: SpanAttributeCatalogue) -> Dict[str, tuple]:
    """Each key in the catalogue, with the span kind that carries it most and its coverage."""
    best: Dict[str, tuple] = {}
    for kind, entry in catalogue.kinds.items():
        for attribute in entry.attributes:
            if attribute.key not in best or attribute.coverage > best[attribute.key][1]:
                best[attribute.key] = (kind, attribute.coverage)
    return best


def unknown_key_warnings(keys: List[str], catalogue: SpanAttributeCatalogue) -> List[str]:
    """A warning for each key no sampled span carries, naming the nearest key that one does."""
    known = _best_coverage(catalogue)
    warnings = []
    for key in keys:
        if key in known:
            continue
        warning = f"No recent span carries {key}"
        nearest = difflib.get_close_matches(key, known, n=1, cutoff=KEY_SUGGESTION_CUTOFF)
        if nearest:
            kind, coverage = known[nearest[0]]
            warning += f"; {nearest[0]} is set on {coverage:.0%} of {kind} spans"
        warnings.append(warning)
    return warnings


def target_key_warnings(
    db: Session, organization_id: str, project_id: Optional[str], config: Optional[dict]
) -> List[str]:
    """Warnings for the attribute keys a metric's target reads that no recent span of its
    project carries. A key may be right before its first trace arrives, so this never
    refuses. Reads the catalogue once, and only when there is a project and a key to check.
    """
    target = (config or {}).get("target")
    if not project_id or target is None:
        return []
    try:
        from rhesis.backend.app.schemas.metric import read_target

        keys = where_attribute_keys(read_target(target))
    except (ImportError, ValueError):  # a core install, or a target the write refuses anyway
        return []
    if not keys:
        return []
    catalogue = get_attribute_catalogue(
        db,
        organization_id,
        str(project_id),
        kind=None,
        days=KEY_CHECK_DAYS,
        limit=KEY_CHECK_LIMIT,
    )
    return unknown_key_warnings(keys, catalogue)
