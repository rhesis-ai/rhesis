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


def normalize_metric_name(name: str) -> str:
    """A metric name reduced to a comparable form: lowercase, non-alphanumerics to dashes."""
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", name.lower()))


def find_metric_key(metrics: dict, metric_name: str) -> Optional[str]:
    """The key this metric is stored under in a result's ``metrics`` blob.

    An annotation names a metric as a person sees it while the blob is keyed by
    whatever the run wrote, and the two differ by punctuation and case often
    enough that an exact match alone loses real annotations.
    """
    if metric_name in metrics:
        return metric_name
    normalized_target = normalize_metric_name(metric_name)
    for key in metrics:
        if isinstance(key, str) and normalize_metric_name(key) == normalized_target:
            return key
    return None
