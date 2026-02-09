"""Service for building adaptive testing trees from test sets.

Converts backend Test models into SDK TestTreeData structures,
providing tree, tests-only, and topics-only views.
Also provides generation of test outputs by invoking an endpoint.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.models.test import test_test_set_association
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


def create_adaptive_test_set(
    db: Session,
    organization_id: str,
    user_id: str,
    name: str,
    description: Optional[str] = None,
) -> models.TestSet:
    """Create a new test set configured for adaptive testing.

    The created test set has attributes.metadata.behaviors containing
    "Adaptive Testing" so it appears in get_adaptive_test_sets.

    Parameters
    ----------
    db : Session
        Database session
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        User ID for ownership
    name : str
        Test set name
    description : str, optional
        Test set description

    Returns
    -------
    models.TestSet
        The created test set
    """
    attributes = {
        "metadata": {"behaviors": [ADAPTIVE_TESTING_BEHAVIOR]},
    }
    test_set_data = schemas.TestSetCreate(
        name=name,
        description=description,
        attributes=attributes,
    )
    return crud.create_test_set(
        db=db,
        test_set=test_set_data,
        organization_id=organization_id,
        user_id=user_id,
    )


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


def create_test_node(
    db: Session,
    test_set_id: UUID,
    organization_id: str,
    user_id: str,
    input: str,
    topic: str = "",
    output: str = "",
    labeler: str = "user",
    model_score: float = 0.0,
) -> TestTreeNode:
    """Create a test node in the adaptive testing tree.

    Creates the underlying DB objects (Topic, Prompt, Test) and
    associates the test with the given test set.  If the topic does
    not yet have a topic_marker in the tree the function delegates to
    :func:`create_topic_node` so the hierarchy stays valid. Topic is
    optional; tests without a topic are allowed.

    The label is intentionally not settable at creation time; new tests
    are always created without a label.

    Parameters
    ----------
    db : Session
        Database session
    test_set_id : UUID
        ID of the test set to add the test to
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        User ID for tenant isolation
    topic : str, optional
        Topic path (e.g. ``"Safety/Violence"``). Default ``""`` (no topic).
    input : str
        The test prompt / input text
    output : str
        Expected or actual output (default ``""``)
    labeler : str
        Who labelled this test (default ``"user"``)
    model_score : float
        Model score for the test (default ``0.0``)

    Returns
    -------
    TestTreeNode
        The created test node
    """
    # Ensure the topic and all ancestors exist as topic markers
    if topic:
        create_topic_node(
            db=db,
            test_set_id=test_set_id,
            organization_id=organization_id,
            user_id=user_id,
            topic=topic,
        )

    # Get or create the topic row for the FK
    db_topic = (
        get_or_create_topic(
            db=db,
            name=topic,
            organization_id=organization_id,
            user_id=user_id,
        )
        if topic
        else None
    )

    # Create the prompt (input text)
    db_prompt = models.Prompt(
        content=input,
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(db_prompt)
    db.flush()

    # Create the test record
    db_test = models.Test(
        topic_id=db_topic.id if db_topic else None,
        prompt_id=db_prompt.id,
        test_metadata={
            "output": output,
            "label": "",
            "labeler": labeler,
            "model_score": model_score,
        },
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(db_test)
    db.flush()

    # Associate the test with the test set
    create_test_set_associations(
        db=db,
        test_set_id=str(test_set_id),
        test_ids=[str(db_test.id)],
        organization_id=organization_id,
        user_id=user_id,
    )

    # Refresh to load relationships for _db_test_to_node
    db.refresh(db_test)

    node = _db_test_to_node(db_test)

    logger.info(f"Created test node in test_set={test_set_id} topic='{topic}'")

    return node


def update_test_node(
    db: Session,
    test_set_id: UUID,
    test_id: UUID,
    organization_id: str,
    user_id: str,
    input: Optional[str] = None,
    output: Optional[str] = None,
    label: Optional[str] = None,
    topic: Optional[str] = None,
    model_score: Optional[float] = None,
) -> Optional[TestTreeNode]:
    """Update a test node in the adaptive testing tree.

    Only the provided (non-None) fields are updated; the rest are
    left unchanged.

    Parameters
    ----------
    db : Session
        Database session
    test_set_id : UUID
        ID of the test set the test belongs to
    test_id : UUID
        ID of the test to update
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        User ID for tenant isolation
    input : str, optional
        New test prompt / input text
    output : str, optional
        New expected or actual output
    label : str, optional
        New label (``"pass"``, ``"fail"``, or ``""``)
    topic : str, optional
        New topic path (e.g. ``"Safety/Violence"``)
    model_score : float, optional
        New model score

    Returns
    -------
    TestTreeNode or None
        The updated test node, or None if test not found in the
        given test set.
    """
    # Look up the test and verify it belongs to the test set
    db_test = (
        db.query(models.Test)
        .join(
            test_test_set_association,
            models.Test.id == test_test_set_association.c.test_id,
        )
        .filter(
            models.Test.id == test_id,
            test_test_set_association.c.test_set_id == test_set_id,
            models.Test.organization_id == organization_id,
        )
        .first()
    )

    if db_test is None:
        return None

    # Update input -> Prompt.content
    if input is not None and db_test.prompt:
        db_test.prompt.content = input
        db.add(db_test.prompt)

    # Update metadata fields (output, label, model_score)
    meta = dict(db_test.test_metadata or {})
    if output is not None:
        meta["output"] = output
    if label is not None:
        meta["label"] = label
    if model_score is not None:
        meta["model_score"] = model_score
    if meta != (db_test.test_metadata or {}):
        db_test.test_metadata = meta

    # Update topic
    if topic is not None:
        # Ensure topic markers exist
        create_topic_node(
            db=db,
            test_set_id=test_set_id,
            organization_id=organization_id,
            user_id=user_id,
            topic=topic,
        )
        db_topic = get_or_create_topic(
            db=db,
            name=topic,
            organization_id=organization_id,
            user_id=user_id,
        )
        db_test.topic_id = db_topic.id

    db.add(db_test)
    db.flush()
    db.refresh(db_test)

    node = _db_test_to_node(db_test)

    logger.info(f"Updated test node {test_id} in test_set={test_set_id}")

    return node


def update_topic_node(
    db: Session,
    test_set_id: UUID,
    organization_id: str,
    user_id: str,
    topic_path: str,
    new_name: str,
) -> Optional[TopicNode]:
    """Rename a topic in the adaptive testing tree.

    Only the last segment (current level name) of the topic path is changed.
    For example, renaming ``"Europe/Germany"`` with ``new_name="Deutschland"``
    produces ``"Europe/Deutschland"``.

    The rename cascades to:
    1. The topic marker test itself.
    2. All descendant topic markers (e.g. ``Europe/Germany/Berlin`` becomes
       ``Europe/Deutschland/Berlin``).
    3. All regular tests whose topic starts with the old path.

    Parameters
    ----------
    db : Session
        Database session
    test_set_id : UUID
        ID of the test set containing the topic
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        User ID for tenant isolation
    topic_path : str
        Current full path of the topic to rename
        (e.g. ``"Europe/Germany"``)
    new_name : str
        New name for the current level only
        (e.g. ``"Deutschland"``; must not contain ``/``)

    Returns
    -------
    TopicNode or None
        The renamed topic node with its new path, or None if the topic
        was not found in the test set.

    Raises
    ------
    ValueError
        If ``new_name`` contains a ``/`` character.
    """
    if "/" in new_name:
        raise ValueError("new_name must not contain '/'")

    # Build the SDK tree to validate the topic exists
    tree_data = convert_to_sdk_tree(db, test_set_id, organization_id, user_id)
    existing_topic = tree_data.topics.get(topic_path)
    if existing_topic is None:
        return None

    # Compute the new path using the SDK helper
    old_topic = TopicNode(path=topic_path)
    new_topic = tree_data.topics.rename(old_topic, new_name)
    new_path = new_topic.path

    # If the name didn't change, return early
    if new_path == topic_path:
        return TopicNode(path=topic_path)

    # Find all tests in this test set and update their topic FKs.
    # We need tests whose topic.name == old_path or starts with
    # old_path + "/" (descendants).
    db_tests = (
        db.query(models.Test)
        .join(
            test_test_set_association,
            models.Test.id == test_test_set_association.c.test_id,
        )
        .join(models.Topic, models.Test.topic_id == models.Topic.id)
        .filter(
            test_test_set_association.c.test_set_id == test_set_id,
            models.Test.organization_id == organization_id,
        )
        .filter((models.Topic.name == topic_path) | (models.Topic.name.like(topic_path + "/%")))
        .all()
    )

    for db_test in db_tests:
        old_name = db_test.topic.name
        if old_name == topic_path:
            updated_name = new_path
        else:
            # Replace the prefix for descendants
            updated_name = new_path + old_name[len(topic_path) :]

        new_db_topic = get_or_create_topic(
            db=db,
            name=updated_name,
            organization_id=organization_id,
            user_id=user_id,
        )
        db_test.topic_id = new_db_topic.id
        db.add(db_test)

    db.flush()

    logger.info(
        f"Renamed topic '{topic_path}' to '{new_path}' "
        f"({len(db_tests)} test(s) updated) in test_set={test_set_id}"
    )

    return TopicNode(path=new_path)


def remove_topic_node(
    db: Session,
    test_set_id: UUID,
    organization_id: str,
    user_id: str,
    topic_path: str,
) -> bool:
    """Remove a topic from the adaptive testing tree.

    If the topic has subtopics, they are removed as well (their topic
    markers are deleted). All tests that belonged to the topic or any
    of its subtopics are moved to the parent of the removed topic.

    Parameters
    ----------
    db : Session
        Database session
    test_set_id : UUID
        ID of the test set containing the topic
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        User ID for tenant isolation
    topic_path : str
        Full path of the topic to remove (e.g. ``"Safety/Violence"``)

    Returns
    -------
    bool
        True if the topic existed and was removed, False if not found.
    """
    tree_data = convert_to_sdk_tree(db, test_set_id, organization_id, user_id)
    existing = tree_data.topics.get(topic_path)
    if existing is None:
        return False

    parent_path = existing.parent_path or ""

    # All tests in this test set under this topic or any subtopic
    db_tests = (
        db.query(models.Test)
        .join(
            test_test_set_association,
            models.Test.id == test_test_set_association.c.test_id,
        )
        .join(models.Topic, models.Test.topic_id == models.Topic.id)
        .filter(
            test_test_set_association.c.test_set_id == test_set_id,
            models.Test.organization_id == organization_id,
        )
        .filter((models.Topic.name == topic_path) | (models.Topic.name.like(topic_path + "/%")))
        .all()
    )

    parent_topic = None
    if parent_path:
        parent_topic = get_or_create_topic(
            db=db,
            name=parent_path,
            organization_id=organization_id,
            user_id=user_id,
        )

    topic_marker_ids = []
    for db_test in db_tests:
        is_marker = (db_test.test_metadata or {}).get("label") == "topic_marker"
        if is_marker:
            topic_marker_ids.append(db_test.id)
        else:
            db_test.topic_id = parent_topic.id if parent_topic else None
            db.add(db_test)

    for test_id in topic_marker_ids:
        db.execute(
            test_test_set_association.delete().where(
                test_test_set_association.c.test_id == test_id,
                test_test_set_association.c.test_set_id == test_set_id,
            )
        )
        crud.delete_test(
            db=db,
            test_id=test_id,
            organization_id=organization_id,
            user_id=user_id,
        )

    db.flush()

    logger.info(
        f"Removed topic '{topic_path}' from test_set={test_set_id}: "
        f"moved tests to parent '{parent_path}', deleted {len(topic_marker_ids)} "
        "topic marker(s)"
    )

    return True


def delete_test_node(
    db: Session,
    test_set_id: UUID,
    test_id: UUID,
    organization_id: str,
    user_id: str,
) -> bool:
    """Delete a test node from the adaptive testing tree.

    Removes the test-to-test-set association and soft-deletes the
    underlying Test (and its Prompt) so the node no longer appears
    in the tree.

    Parameters
    ----------
    db : Session
        Database session
    test_set_id : UUID
        ID of the test set the test belongs to
    test_id : UUID
        ID of the test to delete
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        User ID for tenant isolation

    Returns
    -------
    bool
        True if the test was found and deleted, False otherwise.
    """
    # Look up the test and verify it belongs to the test set
    db_test = (
        db.query(models.Test)
        .join(
            test_test_set_association,
            models.Test.id == test_test_set_association.c.test_id,
        )
        .filter(
            models.Test.id == test_id,
            test_test_set_association.c.test_set_id == test_set_id,
            models.Test.organization_id == organization_id,
        )
        .first()
    )

    if db_test is None:
        return False

    # Remove the test-test_set association
    db.execute(
        test_test_set_association.delete().where(
            test_test_set_association.c.test_id == test_id,
            test_test_set_association.c.test_set_id == test_set_id,
        )
    )

    # Soft-delete the test via the existing CRUD helper
    crud.delete_test(
        db=db,
        test_id=test_id,
        organization_id=organization_id,
        user_id=user_id,
    )

    db.flush()

    logger.info(f"Deleted test node {test_id} from test_set={test_set_id}")

    return True


async def generate_outputs_for_tests(
    db: Session,
    test_set_identifier: str,
    endpoint_id: str,
    organization_id: str,
    user_id: str,
    test_ids: Optional[List[UUID]] = None,
    topic: Optional[str] = None,
    include_subtopics: bool = True,
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

    Returns
    -------
    dict
        - generated: number of tests whose output was updated
        - failed: list of {"test_id": str, "error": str}
        - updated: list of {"test_id": str, "output": str}
    """
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
        eligible.append(t)

    updated: List[Dict[str, str]] = []
    failed: List[Dict[str, str]] = []

    for db_test in eligible:
        test_id_str = str(db_test.id)
        prompt_content = (db_test.prompt.content or "").strip()
        try:
            result = await svc.invoke_endpoint(
                db=db,
                endpoint_id=endpoint_id,
                input_data={"input": prompt_content},
                organization_id=organization_id,
                user_id=user_id,
            )
            processed = process_endpoint_result(result)
            output = (processed.get("output") or "").strip() or "[no output]"

            meta = dict(db_test.test_metadata or {})
            meta["output"] = output
            db_test.test_metadata = meta
            db.add(db_test)
            updated.append({"test_id": test_id_str, "output": output})
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to generate output for test {test_id_str}: {e}")
            failed.append({"test_id": test_id_str, "error": str(e)})

    db.flush()

    logger.info(
        f"Generate outputs: test_set={test_set_identifier}, endpoint={endpoint_id}, "
        f"topic={topic!r}, include_subtopics={include_subtopics}, "
        f"generated={len(updated)}, failed={len(failed)}"
    )

    return {
        "generated": len(updated),
        "failed": failed,
        "updated": updated,
    }
