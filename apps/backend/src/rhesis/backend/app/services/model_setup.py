"""Keeps model defaults in line with what can be built: readiness for ``/features``,
onboarding defaults, and adopting a model once it becomes usable. Defaults live on
each user's settings, so "the org default" means every user in the org."""

import logging
from typing import Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from rhesis.backend.app.crud import model as model_crud
from rhesis.backend.app.crud import user as user_crud
from rhesis.backend.app.database import set_session_variables
from rhesis.backend.app.models.model import Model
from rhesis.backend.app.models.user import User
from rhesis.backend.app.utils.user_model_utils import (
    ModelReadiness,
    check_model_readiness,
    model_setup_problem,
)

logger = logging.getLogger(__name__)

#: Which default each model type fills. A language model serves both
#: generation and evaluation; execution keeps following the deployment default.
#: A decision model (Jev) can't generate text, so it only ever fills evaluation.
_PURPOSES_BY_MODEL_TYPE = {
    "language": ("generation", "evaluation"),
    "decision": ("evaluation",),
    "embedding": ("embedding",),
}


def readiness_for_request(db: Session, user: User) -> Optional[ModelReadiness]:
    """Readiness for the signed-in *user*, or ``None`` when they have no org yet.

    *db* is the plain session ``GET /features`` already has. It must stay plain,
    because a user mid-onboarding has no tenant context. So the RLS variables are
    set here for the user's own org, which the model rows need to be visible.
    """
    if not user.organization_id:
        return None
    try:
        set_session_variables(db, str(user.organization_id), str(user.id))
        return check_model_readiness(db, user)
    except Exception:
        # Fail open: a bug here must not put every user behind the model setup step.
        logger.exception("Could not compute model readiness for user_id=%s", user.id)
        return ModelReadiness()


def onboarding_default_model_ids(
    db: Session, user: User, default_model_ids: Optional[Dict[str, str]]
) -> Dict[str, str]:
    """The seeded model settings a new user should get, keeping only usable ones.

    Without a platform key the seeded "Rhesis" models cannot be built, and
    pointing a new org at them made everything look configured while nothing
    worked. So a default is only set when its model can be built right now.
    """
    if not default_model_ids:
        return {}
    candidates = {
        "generation": default_model_ids.get("language_model_id"),
        "evaluation": default_model_ids.get("language_model_id"),
        "embedding": default_model_ids.get("embedding_model_id"),
    }
    usable = {}
    for purpose, model_id in candidates.items():
        if not model_id:
            continue
        problem = model_setup_problem(db, user, purpose, model_id)
        if problem is None:
            usable[purpose] = model_id
        else:
            logger.info("Not setting a default %s model: %s", purpose, problem.log_message)
    return usable


def apply_default_model_ids(user: User, model_ids: Dict[str, str]) -> None:
    """Write ``{purpose: model_id}`` into *user*'s model settings."""
    if not model_ids:
        return
    user.settings.update(
        {"models": {purpose: {"model_id": mid} for purpose, mid in model_ids.items()}}
    )
    flag_modified(user, "user_settings")


def adopt_usable_defaults(db: Session, organization_id: str, candidates: list[Model]) -> None:
    """Point each org user at the first usable candidate, for every purpose
    whose current default cannot be built.

    A default that already works is never replaced. Best effort: this runs after
    the write that made a model usable, and failing here must not undo that write.
    """
    try:
        # A savepoint, so a failure here can't poison the transaction of that write.
        with db.begin_nested():
            for user in user_crud.get_organization_users(db, organization_id):
                _adopt_for_user(db, user, candidates)
    except Exception:
        logger.exception("Could not update default models for org_id=%s", organization_id)


def _adopt_for_user(db: Session, user: User, candidates: list[Model]) -> None:
    updates = {}
    for model in candidates:
        for purpose in _PURPOSES_BY_MODEL_TYPE.get(model.model_type or "language", ()):
            if purpose in updates or model_setup_problem(db, user, purpose) is None:
                continue
            if model_setup_problem(db, user, purpose, str(model.id)) is None:
                updates[purpose] = str(model.id)
    if updates:
        logger.info("Setting default models for user_id=%s: %s", user.id, updates)
        apply_default_model_ids(user, updates)


def adopt_platform_models(db: Session, user: User) -> None:
    """After a platform key is saved: offer the org's seeded Rhesis models.

    *db* is the platform router's plain session, so the RLS variables are set
    here for the user's own org and the result is committed here.
    """
    organization_id = str(user.organization_id)
    set_session_variables(db, organization_id, str(user.id))
    candidates = model_crud.get_rhesis_system_models(db, organization_id)
    adopt_usable_defaults(db, organization_id, candidates)
    db.commit()
