import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.constants import ADAPTIVE_TESTING_BEHAVIOR
from rhesis.sdk.adaptive_testing.schemas import TestTreeData, TestTreeNode

logger = logging.getLogger(__name__)


def _db_test_to_node(db_test: models.Test) -> TestTreeNode | None:
    """Convert a backend Test model to a TestTreeNode.

    Maps DB fields to the SDK node format:
    - test.topic.name -> node.topic
    - test.prompt.content -> node.input
    - test.test_metadata -> output, label, labeler, model_score, metrics

    Returns None for tests without prompts (unless they are topic markers).
    """
    meta = db_test.test_metadata or {}
    is_topic_marker = meta.get("label") == "topic_marker"

    # Skip tests without prompts (e.g., multi-turn tests)
    # But allow topic markers which have empty prompts
    if not is_topic_marker and (not db_test.prompt or not db_test.prompt.content):
        return None

    topic_name = ""
    if db_test.topic:
        topic_name = db_test.topic.name if hasattr(db_test.topic, "name") else ""

    raw_metrics = meta.get("metrics")
    metrics: Optional[Dict[str, Any]] = None
    if isinstance(raw_metrics, dict):
        metrics = raw_metrics

    return TestTreeNode(
        id=str(db_test.id),
        topic=topic_name,
        input=db_test.prompt.content if db_test.prompt else "",
        output=meta.get("output", "[no output]"),
        label=meta.get("label", ""),
        labeler=meta.get("labeler", "imported"),
        model_score=meta.get("model_score", 0.0),
        metrics=metrics,
    )


def _get_test_set_tests_from_db(
    db: Session,
    test_set_id: UUID,
    organization_id: str,
    user_id: str,
) -> list[models.Test]:
    """Load all tests for a test set from the database.

    Paginates through all pages since the tree needs the complete set
    and the API enforces a max limit of 100 per page.
    """
    page_size = 100
    skip = 0
    all_tests: list[models.Test] = []

    while True:
        items, _count = crud.get_test_set_tests(
            db=db,
            test_set_id=test_set_id,
            skip=skip,
            limit=page_size,
            sort_by="created_at",
            sort_order="desc",
        )
        all_tests.extend(items)

        if len(items) < page_size:
            break
        skip += page_size

    return all_tests


def convert_to_sdk_tree(
    db: Session,
    test_set_id: UUID,
    organization_id: str,
    user_id: str,
) -> TestTreeData:
    """Build a TestTreeData from a test set's tests.

    Loads all tests associated with the test set from the database
    and converts them into TestTreeNode objects.

    Parameters
    ----------
    db : Session
        Database session
    test_set_id : UUID
        ID of the test set to build the tree from
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        User ID for tenant isolation

    Returns
    -------
    TestTreeData
        The constructed tree data with all nodes
    """
    db_tests = _get_test_set_tests_from_db(db, test_set_id, organization_id, user_id)

    nodes = []
    for db_test in db_tests:
        node = _db_test_to_node(db_test)
        if node is not None:
            nodes.append(node)

    logger.info(
        f"Built adaptive testing tree for test_set={test_set_id} "
        f"with {len(nodes)} nodes from {len(db_tests)} tests"
    )

    return TestTreeData(nodes=nodes)


def _build_eligible_tests(
    tests: List[models.Test],
    test_ids: Optional[List[UUID]] = None,
    topic: Optional[str] = None,
    include_subtopics: bool = True,
) -> List[models.Test]:
    """Filter tests to those eligible for evaluation.

    Excludes topic markers, tests without prompts, and applies optional
    test_ids / topic filters (same logic as generate_outputs_for_tests).
    """
    eligible: List[models.Test] = []
    for t in tests:
        meta = t.test_metadata or {}
        if meta.get("label") == "topic_marker":
            continue
        if not t.prompt or not (t.prompt.content or "").strip():
            continue
        if test_ids is not None and t.id not in test_ids:
            continue
        if topic is not None and topic != "":
            t_topic = (t.topic.name if t.topic and hasattr(t.topic, "name") else "") or ""
            if include_subtopics:
                if t_topic != topic and not t_topic.startswith(topic + "/"):
                    continue
            else:
                if t_topic != topic:
                    continue
        eligible.append(t)
    return eligible
