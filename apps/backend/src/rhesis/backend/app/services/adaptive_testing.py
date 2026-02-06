"""Service for building adaptive testing trees from test sets.

Converts backend Test models into SDK TestTreeData structures,
providing tree, tests-only, and topics-only views.
"""

from typing import List
from uuid import UUID

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.services.test import create_test_set_associations
from rhesis.backend.app.utils.crud_utils import get_or_create_topic
from rhesis.backend.logging import logger
from rhesis.sdk.adaptive_testing.schemas import (
    TestTreeData,
    TestTreeNode,
    TopicNode,
)

ADAPTIVE_TESTING_BEHAVIOR = "Adaptive Testing"


def _db_test_to_node(db_test: models.Test) -> TestTreeNode | None:
    """Convert a backend Test model to a TestTreeNode.

    Maps DB fields to the SDK node format:
    - test.topic.name -> node.topic
    - test.prompt.content -> node.input
    - test.test_metadata -> output, label, labeler, model_score

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

    return TestTreeNode(
        id=str(db_test.id),
        topic=topic_name,
        input=db_test.prompt.content if db_test.prompt else "",
        output=meta.get("output", "[no output]"),
        label=meta.get("label", ""),
        labeler=meta.get("labeler", "imported"),
        model_score=meta.get("model_score", 0.0),
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
            sort_order="asc",
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


def get_tree_nodes(
    db: Session,
    test_set_id: UUID,
    organization_id: str,
    user_id: str,
) -> List[TestTreeNode]:
    """Get all nodes in the tree (both tests and topic markers).

    Returns the complete tree as a flat list of TestTreeNode objects.
    """
    tree_data = convert_to_sdk_tree(db, test_set_id, organization_id, user_id)
    return list(tree_data)


def get_tree_tests(
    db: Session,
    test_set_id: UUID,
    organization_id: str,
    user_id: str,
    topic: str | None = None,
) -> List[TestTreeNode]:
    """Get only test nodes (excludes topic markers).

    Parameters
    ----------
    topic : str, optional
        If provided, only returns tests under this topic path.
    """
    tree_data = convert_to_sdk_tree(db, test_set_id, organization_id, user_id)

    if topic:
        return tree_data.topics.get_tests(TopicNode(path=topic), recursive=True)

    return tree_data.get_tests()


def get_tree_topics(
    db: Session,
    test_set_id: UUID,
    organization_id: str,
    user_id: str,
) -> List[TopicNode]:
    """Get all topics in the tree as TopicNode objects.

    Returns the hierarchical topic structure derived from topic markers.
    """
    tree_data = convert_to_sdk_tree(db, test_set_id, organization_id, user_id)
    return tree_data.topics.get_all()


def get_adaptive_test_sets(
    db: Session,
    organization_id: str,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> List[models.TestSet]:
    """Get all test sets that have the Adaptive Testing behavior.

    Queries test sets whose ``attributes -> 'metadata' -> 'behaviors'``
    JSONB array contains the ``"Adaptive Testing"`` string.

    Parameters
    ----------
    db : Session
        Database session
    organization_id : str
        Organization ID for tenant isolation
    skip : int
        Number of records to skip (pagination offset)
    limit : int
        Maximum number of records to return
    sort_by : str
        Field to sort by
    sort_order : str
        Sort direction ('asc' or 'desc')

    Returns
    -------
    List[models.TestSet]
        Test sets configured for adaptive testing
    """
    target = cast(
        [ADAPTIVE_TESTING_BEHAVIOR],
        JSONB,
    )
    query = (
        db.query(models.TestSet)
        .filter(models.TestSet.organization_id == organization_id)
        .filter(models.TestSet.attributes["metadata"]["behaviors"].contains(target))
    )

    # Apply sorting
    sort_column = getattr(models.TestSet, sort_by, models.TestSet.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    test_sets = query.offset(skip).limit(limit).all()

    logger.info(
        f"Found {len(test_sets)} adaptive testing test sets for organization={organization_id}"
    )

    return test_sets


def create_topic_node(
    db: Session,
    test_set_id: UUID,
    organization_id: str,
    user_id: str,
    topic: str,
) -> TopicNode:
    """Create a topic node (and any missing ancestor topics) in the test set.

    Ensures the full topic hierarchy is valid by creating topic markers
    for the requested topic and all its ancestor paths that don't yet
    exist in the test set.

    For each missing path level the function:
    1. Gets or creates a Topic row in the ``topic`` table.
    2. Creates a Test with ``test_metadata.label = "topic_marker"``.
    3. Associates that Test with the given test set.

    Parameters
    ----------
    db : Session
        Database session
    test_set_id : UUID
        ID of the test set to create the topic node in
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        User ID for tenant isolation
    topic : str
        Topic path to create (e.g. ``"Safety"`` or ``"Safety/Violence"``)

    Returns
    -------
    TopicNode
        The created (or already existing) topic node
    """
    # Build the current tree to check which markers already exist
    tree_data = convert_to_sdk_tree(db, test_set_id, organization_id, user_id)

    # Collect paths that still need a topic_marker
    topic_node = TopicNode(path=topic)
    all_paths = [topic_node] + topic_node.get_all_parents()
    paths_to_create = [t.path for t in all_paths if tree_data.topics.get(t.path) is None]

    if not paths_to_create:
        logger.info(f"Topic '{topic}' already exists in test_set={test_set_id}")
        return TopicNode(path=topic)

    # Create from root to leaf so parent topics exist first
    for path in reversed(paths_to_create):
        # 1. Get or create the topic row
        db_topic = get_or_create_topic(
            db=db,
            name=path,
            organization_id=organization_id,
            user_id=user_id,
        )

        # 2. Create a test record flagged as a topic marker
        db_test = models.Test(
            topic_id=db_topic.id,
            test_metadata={
                "label": "topic_marker",
                "labeler": "user",
                "output": "",
            },
            organization_id=organization_id,
            user_id=user_id,
        )
        db.add(db_test)
        db.flush()

        # 3. Associate the test with the test set
        create_test_set_associations(
            db=db,
            test_set_id=str(test_set_id),
            test_ids=[str(db_test.id)],
            organization_id=organization_id,
            user_id=user_id,
        )

    logger.info(
        f"Created topic node '{topic}' ({len(paths_to_create)} marker(s)) in test_set={test_set_id}"
    )

    return TopicNode(path=topic)
