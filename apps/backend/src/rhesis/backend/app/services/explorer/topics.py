import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.services.test import create_test_set_associations
from rhesis.backend.app.utils.crud_utils import get_or_create_topic
from rhesis.sdk.adaptive_testing.schemas import TopicNode

from .utils import convert_to_sdk_tree

logger = logging.getLogger(__name__)


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
        db_test.topic = new_db_topic
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
            if parent_topic:
                db_test.topic = parent_topic
            else:
                db_test.topic = None
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
