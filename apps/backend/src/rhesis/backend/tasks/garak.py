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
    probes_by_module: Optional[Dict[str, List[Dict]]],
) -> Dict[str, Any]:
    """
    Import selected Garak probes as Rhesis test sets.

    Args:
        probes: List of probe selections (module_name, class_name, custom_name
            dicts, from GarakProbeSelection.model_dump())
        name_prefix: Prefix for auto-generated test set names
        description_template: Optional description template
        probes_by_module: Pre-fetched probe data (from the Garak probe cache),
            filtered to only the exact probes referenced by ``probes`` —
            avoids re-instantiating Garak probe classes inside the task. May
            be None when the router found the cache cold; the importer then
            falls back to targeted per-probe extraction (its pre-cache
            behavior), which is safe here since it runs in the worker rather
            than on the request thread.

    Returns:
        dict: Same shape as GarakImporter.import_probes() — test_sets,
        total_test_sets, total_tests, garak_version. test_set_id is coerced
        to str for a consistent, JSON-native result across both the preloaded
        and live-extraction paths.
    """
    from rhesis.backend.app.services.garak.cache import deserialize_probes_by_module
    from rhesis.backend.app.services.garak.importer import GarakImporter, ProbeSelection

    org_id, user_id, _ = self.get_tenant_context()

    probe_selections = [ProbeSelection(**p) for p in probes]

    with self.get_db_session() as db:
        importer = GarakImporter(db)
        if probes_by_module is not None:
            importer.preload_probes(deserialize_probes_by_module(probes_by_module))
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
    probes_by_module: Optional[Dict[str, List[Dict]]],
) -> Dict[str, Any]:
    """
    Sync a Garak-imported test set with the latest probe.

    Args:
        test_set_id: ID of the test set to sync
        probes_by_module: Pre-fetched probe data (from the Garak probe cache),
            filtered to the probe class(es) referenced by the test set —
            avoids re-instantiating Garak probe classes inside the task. May
            be None when the router found the cache cold; the sync service
            then falls back to live extraction (its pre-cache behavior),
            which is safe here since it runs in the worker rather than on the
            request thread.

    Returns:
        dict: Fields of GarakSyncService's SyncResult dataclass.
    """
    from rhesis.backend.app.services.garak.cache import deserialize_probes_by_module
    from rhesis.backend.app.services.garak.sync import GarakSyncService

    org_id, user_id, _ = self.get_tenant_context()

    with self.get_db_session() as db:
        sync_service = GarakSyncService(db)
        if probes_by_module is not None:
            sync_service.preload_probes(deserialize_probes_by_module(probes_by_module))
        result = sync_service.sync_test_set(test_set_id, org_id, user_id)
        return asdict(result)
