"""Snapshot of the configuration a test run actually executed with.

The Configuration tab used to read ``test_run.test_configuration.attributes``, a live join.
A ``TestConfiguration`` row is mutable (``PUT /test_configurations/{id}``) and re-executable
(``POST /test_configurations/{id}/execute``, which rewrites ``attributes`` and commits), so
editing or re-running one silently changed what every past run claimed to have executed.

Copying the displayed keys onto the run at creation makes a finished run's record immutable,
the same way ``services.version_info`` and ``services.experiment`` already do for their own
snapshots. Runs created before this existed have no snapshot, so readers fall back to the
live join and keep working.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

RUN_CONFIG_KEY = "run_config"

#: The keys the test run Configuration tab renders. Deliberately an allowlist rather than a
#: copy of the whole bag: ``attributes`` also carries routing and bookkeeping (parameters_ref,
#: batch_*, reference_test_run_id) that is not part of what the user configured.
SNAPSHOT_KEYS = (
    "execution_mode",
    "is_rescore",
    "metrics",
    "metrics_source",
    "evaluation_model_id",
    "execution_model_id",
    "run_preflight_checks",
)


def snapshot_run_config(*, test_config, attributes: Dict[str, Any]) -> Dict[str, Any]:
    """Freeze the configured options onto a run being created.

    Mutates and returns ``attributes``. Writes nothing when the configuration is empty, so
    readers can tell "no snapshot, fall back" from "snapshot with nothing in it".
    """
    cfg_attrs = test_config.attributes if isinstance(test_config.attributes, dict) else {}
    snapshot = {key: cfg_attrs[key] for key in SNAPSHOT_KEYS if key in cfg_attrs}
    if snapshot:
        attributes[RUN_CONFIG_KEY] = snapshot
    return attributes


def record_resolved_evaluation_model(
    session: Session, *, test_run, model_name: Optional[str]
) -> None:
    """Record the evaluation model the run actually resolved, by name.

    Only an ``evaluation_model_id`` was ever stored, so the tab had nothing to show but a raw
    UUID, or "Default Model" when no override was set. The worker resolves a concrete model
    either way; this writes that name back so the tab can name it.

    Called once per run, right after resolution in each execution path, so there is no
    read-modify-write race. Best-effort: a run must still execute if this fails.
    """
    if not model_name:
        return

    from rhesis.backend.app import schemas
    from rhesis.backend.app.crud.test_run import update_test_run

    try:
        attributes = dict(test_run.attributes) if test_run.attributes else {}
        run_config = dict(attributes.get(RUN_CONFIG_KEY) or {})
        if run_config.get("evaluation_model_name") == model_name:
            return
        run_config["evaluation_model_name"] = model_name
        attributes[RUN_CONFIG_KEY] = run_config

        update_test_run(
            session,
            test_run.id,
            schemas.TestRunUpdate(attributes=attributes),
            organization_id=str(test_run.organization_id) if test_run.organization_id else None,
            user_id=str(test_run.user_id) if test_run.user_id else None,
        )
        # Commits the caller's shared session, so anything else pending goes with it. Both
        # call sites reach here right after update_test_run_start, which commits the same
        # session the same way, so there is no wider transaction to cut short. Safe inside
        # prefetch_execution_context only because the engine sets expire_on_commit=False
        # (app/database.py): with expiry on, the endpoint that function expunges afterwards
        # would come back detached.
        session.commit()
        test_run.attributes = attributes
    except Exception:
        logger.warning(
            "Failed to record resolved evaluation model for test run %s",
            getattr(test_run, "id", "?"),
            exc_info=True,
        )
