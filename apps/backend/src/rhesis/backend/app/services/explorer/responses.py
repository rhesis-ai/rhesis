import asyncio
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud
from rhesis.backend.app.crud.explorer import set_explorer_test_outputs
from rhesis.backend.app.services.explorer.invocation import EndpointInvoker
from rhesis.backend.app.services.explorer.utils import (
    _build_eligible_tests,
    _get_test_set_tests_from_db,
)

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
    """Generate outputs for explorer test-set tests by invoking an endpoint.

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
    db_test_set = crud.resolve_test_set(test_set_identifier, db, organization_id=organization_id)
    if db_test_set is None:
        raise ValueError(f"Test set not found with identifier: {test_set_identifier}")

    tests = _get_test_set_tests_from_db(db, db_test_set.id, organization_id, user_id)

    # Skip tests that already have an output unless overwriting
    eligible = []
    skipped = 0
    for t in _build_eligible_tests(tests, test_ids, topic, include_subtopics):
        if not overwrite and (t.test_metadata or {}).get("output", "").strip():
            skipped += 1
            continue
        eligible.append(t)

    updated: List[Dict[str, str]] = []
    failed: List[Dict[str, str]] = []

    # --- Phase A: extract plain data from ORM objects ---
    work_items = [(str(t.id), (t.prompt.content or "").strip()) for t in eligible]

    # --- Phase B: concurrent invocations, each with its own DB session ---
    # Keep concurrency within connection pool limits (pool_size=10, max_overflow=20).
    invoker = EndpointInvoker(
        db=db,
        endpoint_id=endpoint_id,
        organization_id=organization_id,
        user_id=user_id,
        max_concurrency=20,
    )

    async def _invoke_one(test_id_str: str, prompt_content: str) -> tuple:
        output, error = await invoker.invoke(prompt_content)
        if error:
            logger.warning(f"Failed to generate output for test {test_id_str}: {error}")
            return (test_id_str, None, error)
        return (test_id_str, output, None)

    results = await asyncio.gather(*[_invoke_one(tid, pc) for tid, pc in work_items])

    # --- Phase C: writes on the main request session ---
    outputs = {tid: output for tid, output, error in results if not error}
    written = set(set_explorer_test_outputs(db, outputs))

    # Reported in invocation order; tests whose row no longer exists are silently dropped.
    for test_id_str, output, error in results:
        if error:
            failed.append({"test_id": test_id_str, "error": error})
        elif test_id_str in written:
            updated.append({"test_id": test_id_str, "output": output})

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
