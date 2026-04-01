"""
Shared utilities for test execution tasks.

Only ``get_evaluation_model`` is still used by services that need to resolve
a user's configured LLM for metric evaluation.  The per-test Celery task
that previously lived here was replaced by the batch execution engine
(``batch/`` sub-package).
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.constants import DEFAULT_EVALUATION_MODEL
from rhesis.backend.app.utils.user_model_utils import get_user_evaluation_model

logger = logging.getLogger(__name__)


def get_evaluation_model(db: Session, user_id: str) -> Any:
    """
    Get the evaluation model for the user, with fallback to default.

    Args:
        db: Database session
        user_id: User ID string

    Returns:
        Model instance (string or BaseLLM)
    """
    try:
        user = crud.get_user_by_id(db, user_id)
        if user:
            return get_user_evaluation_model(db, user)
        else:
            logger.warning(
                f"[MODEL_SELECTION] User {user_id} not found, using default: "
                f"{DEFAULT_EVALUATION_MODEL}"
            )
            return DEFAULT_EVALUATION_MODEL
    except Exception as e:
        logger.warning(
            f"[MODEL_SELECTION] Error fetching user model: {str(e)}, "
            f"using default: {DEFAULT_EVALUATION_MODEL}"
        )
        return DEFAULT_EVALUATION_MODEL
