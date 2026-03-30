import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from rhesis.backend.app import crud, models, schemas
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.services.test import create_test_set_associations
from rhesis.backend.app.utils.crud_utils import (
    get_or_create_behavior,
    get_or_create_topic,
    get_or_create_type_lookup,
)
from rhesis.sdk.adaptive_testing.schemas import TestTreeNode, TopicNode

from .topics import create_topic_node
from .utils import (
    ADAPTIVE_TESTING_BEHAVIOR,
    _db_test_to_node,
    convert_to_sdk_tree,
)

logger = logging.getLogger(__name__)


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
    behavior = get_or_create_behavior(
        db=db,
        name=ADAPTIVE_TESTING_BEHAVIOR,
        organization_id=organization_id,
        user_id=user_id,
    )
    attributes = {
        "behaviors": [str(behavior.id)],
        "metadata": {"behaviors": [ADAPTIVE_TESTING_BEHAVIOR]},
    }
    test_set_type_lookup = get_or_create_type_lookup(
        db=db,
        type_name="TestType",
        type_value="Single-Turn",
        organization_id=organization_id,
        user_id=user_id,
    )
    test_set_data = schemas.TestSetCreate(
        name=name,
        description=description,
        attributes=attributes,
        test_set_type_id=test_set_type_lookup.id,
    )
    return crud.create_test_set(
        db=db,
        test_set=test_set_data,
        organization_id=organization_id,
        user_id=user_id,
    )


def _is_adaptive_test_set(test_set: models.TestSet) -> bool:
    """True if the test set has Adaptive Testing in metadata.behaviors."""
    attrs = test_set.attributes or {}
    metadata = attrs.get("metadata") or {}
    behaviors = metadata.get("behaviors") or []
    return ADAPTIVE_TESTING_BEHAVIOR in behaviors


def delete_adaptive_test_set(
    db: Session,
    test_set_identifier: str,
    organization_id: str,
    user_id: str,
) -> models.TestSet:
    """Delete a test set that is configured for adaptive testing.

    Resolves the test set by UUID, nano_id, or slug. Raises ValueError if the
    set is missing or does not include the Adaptive Testing behavior.
    """
    db_test_set = crud.resolve_test_set(test_set_identifier, db, organization_id)
    if db_test_set is None:
        raise ValueError("Test set not found with provided identifier")
    if not _is_adaptive_test_set(db_test_set):
        raise ValueError("Test set is not configured for adaptive testing")
    deleted = crud.delete_test_set(
        db,
        test_set_id=db_test_set.id,
        organization_id=organization_id,
        user_id=user_id,
    )
    if deleted is None:
        raise ValueError("Test set not found with provided identifier")
    return deleted


def _unique_adaptive_import_name(db: Session, organization_id: str, base_name: str) -> str:
    """Pick a test set name that does not collide within the organization."""
    candidate = base_name
    counter = 0
    while True:
        existing = (
            db.query(models.TestSet)
            .filter(
                models.TestSet.organization_id == organization_id,
                models.TestSet.name == candidate,
            )
            .first()
        )
        if existing is None:
            return candidate
        counter += 1
        candidate = f"{base_name} ({counter})"


def import_adaptive_test_set_from_source(
    db: Session,
    source_test_set_identifier: str,
    organization_id: str,
    user_id: str,
) -> dict:
    """Create a new adaptive test set by copying tests from a regular test set.

    Topic hierarchy is rebuilt via topic markers. Tests without prompt content
    (e.g. multi-turn-only) and topic-marker rows are skipped.

    Parameters
    ----------
    db : Session
        Database session
    source_test_set_identifier : str
        UUID, nano_id, or slug of the source test set
    organization_id : str
        Tenant organization id
    user_id : str
        Acting user id

    Returns
    -------
    dict
        ``test_set`` (``models.TestSet``), ``imported``, ``skipped``,
        ``skipped_test_ids``

    Raises
    ------
    ValueError
        If the source set is missing, or already configured for adaptive testing.
    """
    db_source = crud.resolve_test_set(source_test_set_identifier, db, organization_id)
    if db_source is None:
        raise ValueError("Test set not found with provided identifier")

    if _is_adaptive_test_set(db_source):
        raise ValueError("Source test set is already configured for adaptive testing")

    base_name = f"{db_source.name} (Adaptive)"
    new_name = _unique_adaptive_import_name(db, organization_id, base_name)

    new_set = create_adaptive_test_set(
        db=db,
        organization_id=organization_id,
        user_id=user_id,
        name=new_name,
        description=db_source.description,
    )
    db.flush()
    db.refresh(new_set)

    # Copy adaptive_settings from source (e.g. default endpoint) if present
    src_attrs = db_source.attributes or {}
    adaptive_src = src_attrs.get("adaptive_settings")
    if adaptive_src and isinstance(adaptive_src, dict):
        attrs = dict(new_set.attributes or {})
        attrs["adaptive_settings"] = dict(adaptive_src)
        new_set.attributes = attrs
        db.add(new_set)
        db.flush()

    imported = 0
    skipped = 0
    skipped_test_ids: List[str] = []
    # Must stay within crud.get_test_set_tests pagination max (100).
    batch_size = 100
    skip = 0

    while True:
        items, total = crud.get_test_set_tests(
            db=db,
            test_set_id=db_source.id,
            skip=skip,
            limit=batch_size,
            sort_by="created_at",
            sort_order="asc",
        )
        if not items:
            break

        for db_test in items:
            meta = db_test.test_metadata or {}
            if meta.get("label") == "topic_marker":
                skipped += 1
                skipped_test_ids.append(str(db_test.id))
                continue

            prompt = db_test.prompt
            content = (prompt.content or "").strip() if prompt else ""
            if not content:
                skipped += 1
                skipped_test_ids.append(str(db_test.id))
                continue

            topic_name = ""
            if db_test.topic is not None and getattr(db_test.topic, "name", None):
                topic_name = str(db_test.topic.name) or ""

            label_raw = meta.get("label", "") or ""
            label = label_raw if label_raw in ("", "pass", "fail") else ""

            output_val = meta.get("output", "") or ""
            labeler_val = meta.get("labeler", "imported") or "imported"
            try:
                model_score_val = float(meta.get("model_score", 0.0) or 0.0)
            except (TypeError, ValueError):
                model_score_val = 0.0

            create_test_node(
                db=db,
                test_set_id=new_set.id,
                organization_id=organization_id,
                user_id=user_id,
                topic=topic_name,
                input=content,
                output=str(output_val),
                labeler=str(labeler_val),
                label=label,
                model_score=model_score_val,
            )
            imported += 1

        skip += len(items)
        if skip >= total:
            break

    db.refresh(new_set)
    return {
        "test_set": new_set,
        "imported": imported,
        "skipped": skipped,
        "skipped_test_ids": skipped_test_ids,
    }


def create_test_node(
    db: Session,
    test_set_id: UUID,
    organization_id: str,
    user_id: str,
    input: str,
    topic: str = "",
    output: str = "",
    labeler: str = "user",
    label: str = "",
    model_score: float = 0.0,
) -> TestTreeNode:
    """Create a test node in the adaptive testing tree.

    Creates the underlying DB objects (Topic, Prompt, Test) and
    associates the test with the given test set.  If the topic does
    not yet have a topic_marker in the tree the function delegates to
    :func:`create_topic_node` so the hierarchy stays valid. Topic is
    optional; tests without a topic are allowed.

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
    label : str, optional
        Label: 'pass', 'fail', or '' (default ``""``)
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
            "label": label,
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
