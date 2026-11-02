"""Requirement rules that sit above plain CRUD.

The hierarchy check, the type/impact lookups, linked sources, and the annotations
that serve as a requirement's examples.
"""

import uuid
from typing import List, Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.crud import requirement as requirement_crud
from rhesis.backend.app.crud.source import get_source
from rhesis.backend.app.crud.type_lookup import get_type_lookup
from rhesis.backend.app.services.annotation_context import attach_context
from rhesis.backend.app.services.annotation_exchange import exchanges_for

REQUIREMENT_TYPE = "RequirementType"
REQUIREMENT_IMPACT = "RequirementImpact"

_LOOKUP_FIELDS = {"requirement_type_id": REQUIREMENT_TYPE, "impact_id": REQUIREMENT_IMPACT}


def _check_parent(db: Session, parent_id: uuid.UUID, requirement_id: Optional[uuid.UUID]) -> None:
    """The parent must exist and must not sit at or below the requirement itself."""
    if requirement_id is not None and str(parent_id) == str(requirement_id):
        raise HTTPException(status_code=400, detail="A requirement cannot be its own parent.")
    current: Optional[str] = str(parent_id)
    seen: set = set()
    while current is not None and current not in seen:
        seen.add(current)
        parents = requirement_crud.get_parent_ids(db, [current])
        if current not in parents:
            if current == str(parent_id):
                raise HTTPException(status_code=400, detail="Parent requirement not found.")
            return
        if requirement_id is not None and parents[current] == str(requirement_id):
            raise HTTPException(
                status_code=400,
                detail=(
                    "The chosen parent is nested under this requirement, which would make a loop."
                ),
            )
        current = parents[current]


def _check_lookup(db: Session, field: str, lookup_id: uuid.UUID, organization_id: str) -> None:
    lookup = get_type_lookup(db, lookup_id, organization_id)
    expected = _LOOKUP_FIELDS[field]
    if lookup is None or lookup.type_name != expected:
        raise HTTPException(status_code=400, detail=f"{field} must name a {expected} value.")


def validate_requirement_links(
    db: Session,
    data: BaseModel,
    organization_id: str,
    requirement_id: Optional[uuid.UUID] = None,
) -> None:
    """Check parent, type and impact on a create or update body. Raises 400."""
    fields = data.model_dump(exclude_unset=True)
    if fields.get("parent_id") is not None:
        _check_parent(db, fields["parent_id"], requirement_id)
    for field in _LOOKUP_FIELDS:
        if fields.get(field) is not None:
            _check_lookup(db, field, fields[field], organization_id)


def attach_details(db: Session, requirements: List[models.Requirement]) -> List[models.Requirement]:
    """Set ``sources``, ``children_count`` and ``examples_count`` in three batched reads."""
    ids = [r.id for r in requirements]
    sources = requirement_crud.get_sources_by_requirement(db, ids)
    children = requirement_crud.get_children_counts(db, ids)
    examples = requirement_crud.get_example_counts(db, ids)
    for requirement in requirements:
        key = str(requirement.id)
        # Read as ``sources`` by the response schema; the relationship has no note.
        requirement.source_links = sources.get(key, [])
        requirement.children_count = children.get(key, 0)
        requirement.examples_count = examples.get(key, 0)
    return requirements


def _require_requirement(
    db: Session, requirement_id: uuid.UUID, organization_id: str, user_id: str
) -> models.Requirement:
    requirement = requirement_crud.get_requirement(db, requirement_id, organization_id, user_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return requirement


def link_source(
    db: Session,
    requirement_id: uuid.UUID,
    source_id: uuid.UUID,
    note: Optional[str],
    organization_id: str,
    user_id: str,
) -> bool:
    _require_requirement(db, requirement_id, organization_id, user_id)
    if get_source(db, source_id, organization_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    created = requirement_crud.link_source(
        db, requirement_id, source_id, note, organization_id, user_id
    )
    db.commit()
    return created


def unlink_source(
    db: Session,
    requirement_id: uuid.UUID,
    source_id: uuid.UUID,
    organization_id: str,
    user_id: str,
) -> None:
    _require_requirement(db, requirement_id, organization_id, user_id)
    if not requirement_crud.unlink_source(db, requirement_id, source_id):
        raise HTTPException(status_code=404, detail="Source was not linked to this requirement")
    db.commit()


def _tuning_cases(annotation: models.Annotation) -> list:
    attributes = annotation.attributes if isinstance(annotation.attributes, dict) else {}
    cases = attributes.get("tuning_cases")
    return [c for c in cases if isinstance(c, dict)] if isinstance(cases, list) else []


def list_examples(
    db: Session, requirement_id: uuid.UUID, organization_id: str, user_id: str
) -> List[schemas.RequirementExample]:
    """The requirement's annotations, newest first, each with the exchange it judged."""
    _require_requirement(db, requirement_id, organization_id, user_id)
    annotations = requirement_crud.get_example_annotations(db, requirement_id)
    exchanges = exchanges_for(db, annotations)
    details = attach_context(db, annotations)
    return [
        schemas.RequirementExample(
            annotation=detail,
            input=exchanges[annotation.id][0],
            output=exchanges[annotation.id][1],
            tuning_cases=_tuning_cases(annotation),
        )
        for annotation, detail in zip(annotations, details, strict=True)
    ]
