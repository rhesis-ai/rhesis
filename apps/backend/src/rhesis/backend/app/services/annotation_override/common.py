"""Helpers shared by the TestResult and Trace override writers."""

import re
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.constants import OverallTestResult, categorize_test_result_status


def is_passed_status(status_name: str) -> bool:
    return categorize_test_result_status(status_name) == OverallTestResult.PASSED


def annotation_passed(db: Session, annotation: models.Annotation) -> bool:
    """Whether an annotation's verdict is a pass, loading its status if not eager-loaded."""
    status = annotation.status or db.get(models.Status, annotation.status_id)
    return is_passed_status(status.name if status else "")


def parse_turn_number(reference: str) -> Optional[int]:
    digits = re.sub(r"\D", "", reference)
    return int(digits) if digits else None
