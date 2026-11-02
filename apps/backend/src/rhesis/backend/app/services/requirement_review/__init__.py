"""AI quality review of a requirement's wording.

Asks the user's generation model, the way ``metric_tuning.improve`` does, for a few
plain-language hints on the name and description, and stores the answer on
``requirement.review`` so the page can show it without asking again. The stored
``description_hash`` tells the client whether the text changed since.
"""

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

from jinja2 import Template
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from rhesis.backend.app import models, schemas
from rhesis.backend.app.crud.requirement import set_requirement_review
from rhesis.backend.app.crud.type_lookup import get_type_values
from rhesis.backend.app.services.requirement import REQUIREMENT_TYPE
from rhesis.backend.app.utils.user_model_utils import resolve_model

logger = logging.getLogger(__name__)

MAX_HINTS = 5


class ReviewUnavailable(Exception):
    """The generation model could not produce a review."""


class _ModelHints(BaseModel):
    """What the model is asked to return."""

    hints: List[schemas.RequirementReviewHint] = Field(default_factory=list)


def _load_template() -> Template:
    path = os.path.join(os.path.dirname(__file__), "review.jinja")
    with open(path, "r") as handle:
        return Template(handle.read())


def description_hash(name: Optional[str], description: Optional[str]) -> str:
    text = f"{name or ''}\n{description or ''}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean(
    hints: List[schemas.RequirementReviewHint], description: str, types: List[str]
) -> List[schemas.RequirementReviewHint]:
    """Drop what the client could not use: a quote not in the text, an unknown type."""
    cleaned = []
    for hint in hints[:MAX_HINTS]:
        if hint.quote and hint.quote not in description:
            hint.quote = None
        if hint.kind == "suggest_type" and hint.suggestion not in types:
            continue
        cleaned.append(hint)
    return cleaned


def _ask_model(db: Session, user: models.User, prompt: str) -> _ModelHints:
    try:
        model = resolve_model(db, user, "generation")
        answer = model.generate(prompt, schema=_ModelHints)
    except Exception as e:
        raise ReviewUnavailable(str(e)) from e
    # A provider can swallow its own failure and hand back something else.
    if not isinstance(answer, dict) or "hints" not in answer:
        raise ReviewUnavailable(f"The generation model answered with {answer!r}")
    try:
        return _ModelHints.model_validate(answer)
    except Exception as e:
        raise ReviewUnavailable(str(e)) from e


def review_requirement(
    db: Session, requirement: models.Requirement, user: models.User, organization_id: str
) -> schemas.RequirementReview:
    """Review the requirement, store the result on it, and return it."""
    types = get_type_values(db, REQUIREMENT_TYPE, organization_id)
    current_type = requirement.requirement_type.type_value if requirement.requirement_type else None
    prompt = _load_template().render(
        name=requirement.name,
        description=requirement.description,
        current_type=current_type,
        types=types,
    )
    answer = _ask_model(db, user, prompt)
    review = schemas.RequirementReview(
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        description_hash=description_hash(requirement.name, requirement.description),
        hints=_clean(answer.hints, requirement.description or "", types),
    )
    set_requirement_review(db, requirement, review.model_dump(mode="json"))
    db.commit()
    return review
