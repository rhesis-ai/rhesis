"""
Celery tasks for Garak probe import and sync.

Both operations can create/modify thousands of Test/Prompt rows for a single
"Full" Garak probe (some produce 6000+ prompts). Running that synchronously
inside a FastAPI request blocks the worker's event loop for the whole
operation and can exceed gunicorn's worker timeout, killing the worker. These
tasks move that work into Celery, mirroring the existing
``generate_and_save_test_set`` pattern.
"""

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from rhesis.backend.celery.core import app
from rhesis.backend.notifications.email.template_service import EmailTemplate
from rhesis.backend.tasks.base import EmailEnabledTask, email_notification

logger = logging.getLogger(__name__)


@email_notification(
    template=EmailTemplate.TASK_COMPLETION,
    subject_template="Garak Import Complete: {task_name} - {status}",
)
@app.task(
    base=EmailEnabledTask,
    name="rhesis.backend.tasks.import_garak_probes",
    bind=True,
    display_name="Import Garak Probes",
)
def import_garak_probes_task(
    self,
    probes: List[Dict[str, Any]],
    name_prefix: Optional[str],
    description_template: Optional[str],
) -> Dict[str, Any]:
    """
    Import selected Garak probes as Rhesis test sets.

    The task extracts the selected probe classes itself (via the importer's
    per-probe extraction). We deliberately do not ship pre-fetched probe data
    through the Celery broker: a single "Full" probe carries thousands of
    prompts, so passing the payload would put megabytes on the broker per
    dispatch. Extraction here is bounded to the selected classes, runs in the
    worker (not the request thread), and is dwarfed by the test/prompt row
    writes the import performs anyway.

    Args:
        probes: List of probe selections (module_name, class_name, custom_name
            dicts, from GarakProbeSelection.model_dump())
        name_prefix: Prefix for auto-generated test set names
        description_template: Optional description template

    Returns:
        dict: Same shape as GarakImporter.import_probes() — test_sets,
        total_test_sets, total_tests, garak_version. test_set_id is coerced
        to str for a consistent, JSON-native result.
    """
    from rhesis.backend.app.services.garak.importer import GarakImporter, ProbeSelection

    org_id, user_id, _ = self.get_tenant_context()

    probe_selections = [ProbeSelection(**p) for p in probes]

    with self.get_db_session() as db:
        importer = GarakImporter(db)
        result = importer.import_probes(
            probes=probe_selections,
            name_prefix=name_prefix,
            description_template=description_template,
            organization_id=org_id,
            user_id=user_id,
        )
        for test_set in result["test_sets"]:
            test_set["test_set_id"] = str(test_set["test_set_id"])
        return result


@email_notification(
    template=EmailTemplate.TASK_COMPLETION,
    subject_template="Garak Sync Complete: {task_name} - {status}",
)
@app.task(
    base=EmailEnabledTask,
    name="rhesis.backend.tasks.sync_garak_test_set",
    bind=True,
    display_name="Sync Garak Test Set",
)
def sync_garak_test_set_task(
    self,
    test_set_id: str,
) -> Dict[str, Any]:
    """
    Sync a Garak-imported test set with the latest probe.

    The task extracts the test set's probe class(es) itself. As with
    ``import_garak_probes_task``, probe data is deliberately not shipped
    through the Celery broker (a "Full" probe's thousands of prompts would put
    megabytes on the broker); extraction runs in the worker and is bounded to
    the test set's own probe class(es).

    Args:
        test_set_id: ID of the test set to sync

    Returns:
        dict: Fields of GarakSyncService's SyncResult dataclass.
    """
    from rhesis.backend.app.services.garak.sync import GarakSyncService

    org_id, user_id, _ = self.get_tenant_context()

    with self.get_db_session() as db:
        sync_service = GarakSyncService(db)
        result = sync_service.sync_test_set(test_set_id, org_id, user_id)
        return asdict(result)
