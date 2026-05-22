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
from rhesis.backend.app.config.settings import get_model_settings
from rhesis.backend.app.utils.user_model_utils import (
    get_user_evaluation_model,
    get_user_execution_model,
)

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
        default_model = get_model_settings().evaluation_model
        user = crud.get_user_by_id(db, user_id)
        if user:
            return get_user_evaluation_model(db, user)
        else:
            logger.warning(
                f"[MODEL_SELECTION] User {user_id} not found, using default: "
                f"{default_model}"
            )
            return default_model
    except Exception as e:
        default_model = get_model_settings().evaluation_model
        logger.warning(
            f"[MODEL_SELECTION] Error fetching user model: {str(e)}, "
            f"using default: {default_model}"
        )
        return default_model


def get_execution_model(db: Session, user_id: str) -> Any:
    """
    Get the execution model for the user, with fallback to default.

    Used for multi-turn test execution (Penelope).

    Args:
        db: Database session
        user_id: User ID string

    Returns:
        Model instance (string or BaseLLM)
    """
    try:
        default_model = get_model_settings().execution_model
        user = crud.get_user_by_id(db, user_id)
        if user:
            return get_user_execution_model(db, user)
        else:
            logger.warning(
                f"[MODEL_SELECTION] User {user_id} not found, using default: "
                f"{default_model}"
            )
            return default_model
    except Exception as e:
        default_model = get_model_settings().execution_model
        logger.warning(
            f"[MODEL_SELECTION] Error fetching user execution model: {str(e)}, "
            f"using default: {default_model}"
        )
        return default_model
