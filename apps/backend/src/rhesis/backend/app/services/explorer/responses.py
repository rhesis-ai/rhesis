import asyncio
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models

from .utils import _get_test_set_tests_from_db

logger = logging.getLogger(__name__)


async def generate_outputs_for_tests(
    db: Session,
    test_set_identifier: str,
    endpoint_id: str,
    organization_id: str,
    user_id: str,
    test_ids: Optional[List[UUID]] = None,
    topic: Optional[str] = None,
    include_subtopics: bool = True,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Generate outputs for adaptive testing tests by invoking an endpoint.

    For each test in the test set (with a prompt), invokes the given endpoint
    with the test input, extracts the response output using the same logic as
    test execution, and updates the test's output in test_metadata.

    Parameters
    ----------
    db : Session
        Database session
    test_set_identifier : str
        Test set identifier (UUID, nano_id, or slug)
    endpoint_id : str
        Endpoint UUID to invoke for each test
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        User ID for tenant isolation
    test_ids : list of UUID, optional
        If provided, only generate outputs for these test IDs. Otherwise all
        tests in the set (that have a prompt) are processed.
    topic : str, optional
        If provided, only generate outputs for tests under this topic path.
        When combined with test_ids, both filters apply (topic + test_ids).
    include_subtopics : bool, default True
        When topic is set: if True, include tests in the topic and all
        subtopics; if False, include only tests directly under the topic.
    overwrite : bool, default False
        If False, tests that already have an output will be skipped.

    Returns
    -------
    dict
        - generated: number of tests whose output was updated
        - skipped: number of tests that already had an output (if overwrite=False)
        - failed: list of {"test_id": str, "error": str}
        - updated: list of {"test_id": str, "output": str}
    """
    from rhesis.backend.app.database import get_db_with_tenant_variables
    from rhesis.backend.app.dependencies import get_endpoint_service
    from rhesis.backend.tasks.execution.executors.results import (
        process_endpoint_result,
    )

    svc = get_endpoint_service()

    db_test_set = crud.resolve_test_set(test_set_identifier, db, organization_id=organization_id)
    if db_test_set is None:
        raise ValueError(f"Test set not found with identifier: {test_set_identifier}")

    tests = _get_test_set_tests_from_db(db, db_test_set.id, organization_id, user_id)

    # Exclude topic markers; only tests with prompt content
    eligible = []
    skipped = 0
    for t in tests:
        meta = t.test_metadata or {}
        if meta.get("label") == "topic_marker":
            continue
        if not t.prompt or not (t.prompt.content or "").strip():
            continue
        if test_ids is not None and t.id not in test_ids:
            continue
        # Filter by topic when provided
        if topic is not None and topic != "":
            t_topic = (t.topic.name if t.topic and hasattr(t.topic, "name") else "") or ""
            if include_subtopics:
                if t_topic != topic and not t_topic.startswith(topic + "/"):
                    continue
            else:
                if t_topic != topic:
                    continue

        # Filter out tests that already have an output if overwrite is False
        if not overwrite and meta.get("output", "").strip():
            skipped += 1
            continue

        eligible.append(t)

    updated: List[Dict[str, str]] = []
    failed: List[Dict[str, str]] = []

    # --- Phase A: extract plain data from ORM objects ---
    work_items = [(str(t.id), (t.prompt.content or "").strip()) for t in eligible]

    # --- Phase B: concurrent invocations, each with its own DB session ---
    # Keep semaphore within connection pool limits (pool_size=10, max_overflow=20).
    semaphore = asyncio.Semaphore(20)

    async def _invoke_one(test_id_str: str, prompt_content: str) -> tuple:
        async with semaphore:
            try:
                with get_db_with_tenant_variables(organization_id, user_id) as task_db:
                    result = await svc.invoke_endpoint(
                        db=task_db,
                        endpoint_id=endpoint_id,
                        input_data={"input": prompt_content},
                        organization_id=organization_id,
                        user_id=user_id,
                    )
                processed = process_endpoint_result(result)
                output = (processed.get("output") or "").strip() or "[no output]"
                return (test_id_str, output, None)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to generate output for test {test_id_str}: {e}")
                return (test_id_str, None, str(e))

    results = await asyncio.gather(*[_invoke_one(tid, pc) for tid, pc in work_items])

    # --- Phase C: sequential writes on the main request session ---
    for test_id_str, output, error in results:
        if error:
            failed.append({"test_id": test_id_str, "error": error})
        else:
            db_test = db.query(models.Test).filter(models.Test.id == test_id_str).first()
            if db_test:
                meta = dict(db_test.test_metadata or {})
                meta["output"] = output
                db_test.test_metadata = meta
                updated.append({"test_id": test_id_str, "output": output})

    db.flush()

    logger.info(
        f"Generate outputs: test_set={test_set_identifier}, endpoint={endpoint_id}, "
        f"topic={topic!r}, include_subtopics={include_subtopics}, overwrite={overwrite}, "
        f"generated={len(updated)}, skipped={skipped}, failed={len(failed)}"
    )

    return {
        "generated": len(updated),
        "skipped": skipped,
        "failed": failed,
        "updated": updated,
    }
