"""Version-of-the-system-under-test snapshot for a test run.

Written once when a TestRun is created, then optionally overridden once at completion by
a version the endpoint reported itself. Mirrors
``services.experiment.apply_parameter_snapshot_to_run_attributes``: the worker and the UI
read only the snapshot, never the live endpoint row, so editing an endpoint after a run
cannot rewrite what that run claims to have tested.

The value is free-form client JSON -- a prompt version, a model name, whatever identifies
their build. Rhesis stores and displays it without interpreting it.
"""

import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.schemas.validators import validate_version_info

logger = logging.getLogger(__name__)

VERSION_INFO_KEY = "version_info"
VERSION_INFO_SOURCE_KEY = "version_info_source"

SOURCE_ENDPOINT = "endpoint"
SOURCE_RESPONSE = "response"
SOURCE_RESCORE = "rescore"


def _clean(value: Any) -> Optional[Dict[str, Any]]:
    """Return a non-empty, valid version_info dict, or None."""
    if not isinstance(value, dict) or not value:
        return None
    try:
        validate_version_info(value)
    except ValueError as exc:
        logger.warning("Discarding invalid version_info: %s", exc)
        return None
    return value


def apply_version_snapshot_to_run_attributes(
    db: Session, *, test_config, attributes: Dict[str, Any]
) -> Dict[str, Any]:
    """Record the endpoint's configured version on a run being created.

    Mutates and returns ``attributes``. Writes nothing when there is no version to record,
    so consumers can test with ``"version_info" in attributes`` rather than against None.
    """
    from rhesis.backend.app.models.endpoint import Endpoint
    from rhesis.backend.app.models.test_run import TestRun

    cfg_attrs = test_config.attributes if isinstance(test_config.attributes, dict) else {}

    # A rescore replays stored outputs without calling the endpoint, so the endpoint's
    # *current* version never produced them. Carry the reference run's record forward.
    ref_run_id = cfg_attrs.get("reference_test_run_id")
    if cfg_attrs.get("is_rescore") and ref_run_id:
        try:
            ref = db.get(TestRun, uuid.UUID(str(ref_run_id)))
        except (ValueError, TypeError):
            ref = None
        ref_attrs = ref.attributes if ref is not None and isinstance(ref.attributes, dict) else {}
        carried = _clean(ref_attrs.get(VERSION_INFO_KEY))
        if carried is not None:
            attributes[VERSION_INFO_KEY] = carried
            attributes[VERSION_INFO_SOURCE_KEY] = SOURCE_RESCORE
        return attributes

    if test_config.endpoint_id is None:
        return attributes

    endpoint = db.get(Endpoint, test_config.endpoint_id)
    configured = _clean(endpoint.version_info) if endpoint is not None else None
    if configured is not None:
        attributes[VERSION_INFO_KEY] = configured
        attributes[VERSION_INFO_SOURCE_KEY] = SOURCE_ENDPOINT
    return attributes


def apply_reported_version_info(db: Session, *, test_run, attributes: Dict[str, Any]) -> None:
    """Override the creation-time snapshot with the version the endpoint reported.

    Only ever sets: when no result reported a version, the endpoint snapshot stands.
    """
    from rhesis.backend.app.crud.test_result import get_first_reported_version_info

    reported = _clean(
        get_first_reported_version_info(
            db,
            test_run_id=test_run.id,
            organization_id=str(test_run.organization_id) if test_run.organization_id else None,
        )
    )
    if reported is not None:
        attributes[VERSION_INFO_KEY] = reported
        attributes[VERSION_INFO_SOURCE_KEY] = SOURCE_RESPONSE


def version_info_from_run_attributes(
    attributes: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Read shape for API responses; mirrors ``experiment_summary_dict_from_run_attributes``."""
    if not attributes:
        return None
    value = attributes.get(VERSION_INFO_KEY)
    if not isinstance(value, dict) or not value:
        return None
    return {
        "value": value,
        "source": attributes.get(VERSION_INFO_SOURCE_KEY) or SOURCE_ENDPOINT,
    }
