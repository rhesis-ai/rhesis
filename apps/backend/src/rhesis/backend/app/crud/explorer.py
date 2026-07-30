"""CRUD operations specific to Explorer test sets.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the bulk of the functions, and per-entity modules like this one take over as the code
around them is touched.

Every function here flushes and never commits -- the request session owns the commit
(see ``get_db_with_tenant_variables`` in ``database.py``).
"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager, joinedload

from rhesis.backend.app import models, schemas
from rhesis.backend.app.constants import ADAPTIVE_TESTING_BEHAVIOR

# _TEST_SET_RELATED_FIELDS is imported rather than relocated: three other functions in
# the monolith use the same tuple, and moving it would mean deciding a new home for a
# TestSet-wide constant while this module only owns the Explorer slice.
# crud/__init__.py never imports this module, so the parent-package import is cycle-free.
from rhesis.backend.app.crud import (
    _TEST_SET_RELATED_FIELDS,
    create_embedding,
    get_embedding_by_hash,
)
from rhesis.backend.app.models.enums import ModelType
from rhesis.backend.app.models.test import test_test_set_association
from rhesis.backend.app.utils.query_utils import QueryBuilder, include

logger = logging.getLogger(__name__)


# --- Test sets ---------------------------------------------------------------------


def get_explorer_test_sets(
    db: Session,
    organization_id: str,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> List[models.TestSet]:
    """Get Explorer test sets -- the inverse of ``get_test_sets``' exclusion clause.

    Eager-loads what ``TestSetDetail`` serializes, since ``GET /explorer/`` returns
    that schema.

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
    list of models.TestSet
        Test sets carrying the Adaptive Testing behavior.
    """
    explorer_marker = cast([ADAPTIVE_TESTING_BEHAVIOR], JSONB)

    def only_explorer_test_sets(query):
        return query.filter(
            models.TestSet.attributes["metadata"]["behaviors"].contains(explorer_marker)
        )

    # Paginated outside the builder on purpose: with_pagination caps limit at 100
    # (validate_pagination) and this endpoint has never capped. with_sorting already
    # appends id ASC as a tiebreaker, so pagination stays stable.
    query = (
        QueryBuilder(db, models.TestSet)
        .with_related(*_TEST_SET_RELATED_FIELDS)
        .with_default_derived_field_loads()
        .with_organization_filter(organization_id)
        .with_custom_filter(only_explorer_test_sets)
        .with_sorting(sort_by, sort_order)
        .build()
    )
    return query.offset(skip).limit(limit).all()


def get_test_sets_by_ids(
    db: Session, test_set_ids: List[uuid.UUID], organization_id: str
) -> List[models.TestSet]:
    """Load the given test sets, scoped to the organization.

    Used by the bulk-delete path to inspect each candidate's behavior before deleting;
    ids that don't resolve simply come back missing from the result.

    Parameters
    ----------
    db : Session
        Database session
    test_set_ids : list of uuid.UUID
        Test set ids to load
    organization_id : str
        Organization ID for tenant isolation

    Returns
    -------
    list of models.TestSet
        The test sets that resolved, in no guaranteed order.
    """
    if not test_set_ids:
        return []

    return (
        QueryBuilder(db, models.TestSet)
        .with_organization_filter(organization_id)
        .with_custom_filter(lambda q: q.filter(models.TestSet.id.in_(test_set_ids)))
        .all()
    )


def get_test_ids_in_test_sets(
    db: Session, test_set_ids: List[uuid.UUID], organization_id: str
) -> List[uuid.UUID]:
    """Distinct ids of the tests associated with any of the given test sets.

    Parameters
    ----------
    db : Session
        Database session
    test_set_ids : list of uuid.UUID
        Test set ids to collect tests from
    organization_id : str
        Organization ID for tenant isolation

    Returns
    -------
    list of uuid.UUID
        Distinct test ids across all the given test sets.
    """
    if not test_set_ids:
        return []

    rows = db.execute(
        select(test_test_set_association.c.test_id)
        .where(
            test_test_set_association.c.test_set_id.in_(test_set_ids),
            test_test_set_association.c.organization_id == organization_id,
        )
        .distinct()
    ).fetchall()
    return [row.test_id for row in rows]


def replace_test_set_adaptive_settings(
    db: Session, test_set: models.TestSet, settings: Dict[str, Any]
) -> models.TestSet:
    """Overwrite a test set's ``attributes["adaptive_settings"]`` wholesale.

    Used by import, which copies the source set's settings across as a unit. Contrast
    :func:`set_test_set_default_endpoint`, which patches a single key.

    Parameters
    ----------
    db : Session
        Database session
    test_set : models.TestSet
        Test set to write to
    settings : dict
        The new ``adaptive_settings`` value

    Returns
    -------
    models.TestSet
        The same instance, flushed.
    """
    attrs = dict(test_set.attributes or {})
    attrs["adaptive_settings"] = dict(settings)
    test_set.attributes = attrs
    db.add(test_set)
    db.flush()
    return test_set


def set_test_set_default_endpoint(
    db: Session, test_set: models.TestSet, endpoint_id: uuid.UUID
) -> models.TestSet:
    """Patch ``adaptive_settings["default_endpoint_id"]``, leaving other settings alone.

    Refreshes before returning so the caller reads back what was written.

    Parameters
    ----------
    db : Session
        Database session
    test_set : models.TestSet
        Test set to write to
    endpoint_id : uuid.UUID
        Endpoint to make the default

    Returns
    -------
    models.TestSet
        The same instance, flushed and refreshed.
    """
    attrs = dict(test_set.attributes or {})
    explorer_settings = dict(attrs.get("adaptive_settings") or {})
    explorer_settings["default_endpoint_id"] = str(endpoint_id)
    attrs["adaptive_settings"] = explorer_settings
    test_set.attributes = attrs
    db.add(test_set)
    db.flush()
    db.refresh(test_set)
    return test_set


def refresh_test_set(db: Session, test_set: models.TestSet) -> models.TestSet:
    """Re-read a test set after a batch of writes to its tests.

    Import and export both add tests in a loop, and associating a test recalculates the
    set's derived attributes. This pulls those back onto the instance the caller is about
    to serialize.

    Parameters
    ----------
    db : Session
        Database session
    test_set : models.TestSet
        Test set to re-read

    Returns
    -------
    models.TestSet
        The same instance, current.
    """
    db.flush()
    db.refresh(test_set)
    return test_set


def find_unused_test_set_name(db: Session, organization_id: str, base_name: str) -> str:
    """Pick a test set name that does not collide within the organization.

    Returns ``base_name`` when it is free, otherwise the first free
    ``"{base_name} ({n})"`` counting up from 1. Collects the taken names in one query
    rather than probing per candidate, which is what the caller used to do.

    Parameters
    ----------
    db : Session
        Database session
    organization_id : str
        Organization ID for tenant isolation
    base_name : str
        Preferred name

    Returns
    -------
    str
        A name not currently used by any test set in the organization.
    """
    # LIKE wildcards in base_name would widen the match, so escape them.
    escaped = base_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    rows = (
        db.query(models.TestSet.name)
        .filter(
            models.TestSet.organization_id == organization_id,
            (models.TestSet.name == base_name)
            | (models.TestSet.name.like(f"{escaped} (%)", escape="\\")),
        )
        .all()
    )
    taken = {row.name for row in rows}

    if base_name not in taken:
        return base_name

    counter = 1
    while f"{base_name} ({counter})" in taken:
        counter += 1
    return f"{base_name} ({counter})"


# --- Tests within a test set -------------------------------------------------------


def get_test_in_test_set(
    db: Session, test_set_id: uuid.UUID, test_id: uuid.UUID, organization_id: str
) -> Optional[models.Test]:
    """Load a test, but only if it belongs to the given test set.

    The membership join is the point: it doubles as the authorization check for the
    per-test Explorer endpoints. The prompt is eager-loaded because callers either
    rewrite or serialize it.

    Parameters
    ----------
    db : Session
        Database session
    test_set_id : uuid.UUID
        Test set the test must belong to
    test_id : uuid.UUID
        Test to load
    organization_id : str
        Organization ID for tenant isolation

    Returns
    -------
    models.Test or None
        The test, or None when it does not exist in that test set.
    """
    return (
        db.query(models.Test)
        .options(joinedload(models.Test.prompt))
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


def get_tests_under_topic(
    db: Session, test_set_id: uuid.UUID, organization_id: str, topic_path: str
) -> List[models.Test]:
    """Load every test in a test set whose topic is ``topic_path`` or a descendant.

    Descendants are matched on the topic name prefix (``topic_path + "/"``), since
    Explorer stores the full path in ``Topic.name``. The topic is eager-loaded via
    ``contains_eager`` on the join the filter already needs, so callers can read
    ``test.topic.name`` without another round trip.

    Parameters
    ----------
    db : Session
        Database session
    test_set_id : uuid.UUID
        Test set to search within
    organization_id : str
        Organization ID for tenant isolation
    topic_path : str
        Full topic path, e.g. ``"Safety/Violence"``

    Returns
    -------
    list of models.Test
        Tests under the topic and all of its subtopics, topic markers included.
    """
    return (
        db.query(models.Test)
        .join(
            test_test_set_association,
            models.Test.id == test_test_set_association.c.test_id,
        )
        .join(models.Topic, models.Test.topic_id == models.Topic.id)
        .options(contains_eager(models.Test.topic))
        .filter(
            test_test_set_association.c.test_set_id == test_set_id,
            models.Test.organization_id == organization_id,
        )
        .filter((models.Topic.name == topic_path) | (models.Topic.name.like(topic_path + "/%")))
        .all()
    )


def create_explorer_test(
    db: Session,
    *,
    organization_id: str,
    user_id: str,
    topic_id: Optional[uuid.UUID] = None,
    content: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> models.Test:
    """Insert an Explorer test, plus the prompt holding its input when it has one.

    ``content=None`` skips the prompt entirely, which is how topic markers are stored --
    they are Test rows with no prompt and ``test_metadata["label"] == "topic_marker"``.
    Associating the test with its test set is the caller's job, since that goes through
    the shared ``create_test_set_associations`` service.

    Parameters
    ----------
    db : Session
        Database session
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        Owning user
    topic_id : uuid.UUID, optional
        Topic to file the test under
    content : str, optional
        Prompt text; when None no prompt row is created
    metadata : dict, optional
        Value for ``test_metadata``

    Returns
    -------
    models.Test
        The inserted test, flushed so its id is populated.
    """
    prompt_id = None
    if content is not None:
        db_prompt = models.Prompt(
            content=content,
            organization_id=organization_id,
            user_id=user_id,
        )
        db.add(db_prompt)
        db.flush()
        prompt_id = db_prompt.id

    db_test = models.Test(
        topic_id=topic_id,
        prompt_id=prompt_id,
        test_metadata=metadata,
        organization_id=organization_id,
        user_id=user_id,
    )
    db.add(db_test)
    db.flush()
    return db_test


def update_explorer_test(
    db: Session,
    db_test: models.Test,
    *,
    prompt_content: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    topic_id: Optional[uuid.UUID] = None,
) -> models.Test:
    """Apply the given changes to a test, then flush and refresh it.

    Only the arguments that are not None are applied; the caller decides what changed.
    The refresh matters: assigning ``topic_id`` does not update the already-loaded
    ``topic`` relationship, so a caller that serializes the test straight afterwards
    would otherwise read the old topic.

    Parameters
    ----------
    db : Session
        Database session
    db_test : models.Test
        Test to update
    prompt_content : str, optional
        New prompt text; ignored when the test has no prompt
    metadata : dict, optional
        Replacement ``test_metadata``, written only when it differs
    topic_id : uuid.UUID, optional
        New topic

    Returns
    -------
    models.Test
        The same instance, flushed and refreshed.
    """
    if prompt_content is not None and db_test.prompt:
        db_test.prompt.content = prompt_content
        db.add(db_test.prompt)

    if metadata is not None and metadata != (db_test.test_metadata or {}):
        db_test.test_metadata = metadata

    if topic_id is not None:
        db_test.topic_id = topic_id

    db.add(db_test)
    db.flush()
    db.refresh(db_test)
    return db_test


def reassign_tests_topic(
    db: Session, assignments: Sequence[Tuple[models.Test, Optional[models.Topic]]]
) -> None:
    """Re-point each given test at its paired topic, flushing once at the end.

    Takes pairs rather than one shared topic because the two callers differ: renaming a
    topic gives every test its own rewritten path, while removing one moves them all to
    the same parent. A ``None`` topic orphans the test, which is what removing a
    top-level topic does.

    Parameters
    ----------
    db : Session
        Database session
    assignments : sequence of (models.Test, models.Topic or None)
        Tests paired with the topic to move them to
    """
    if not assignments:
        return

    for db_test, topic in assignments:
        db_test.topic = topic
        db.add(db_test)

    db.flush()


def remove_tests_from_test_set(
    db: Session, test_set_id: uuid.UUID, test_ids: Sequence[uuid.UUID]
) -> None:
    """Drop the association rows linking the given tests to a test set.

    One statement for the whole batch. This only detaches -- soft-deleting the tests
    themselves is a separate ``crud.delete_test`` call, and note the order matters:
    ``delete_test`` reads the association table to decide which test sets to
    recalculate, so a test detached first is deliberately left out of that.

    Parameters
    ----------
    db : Session
        Database session
    test_set_id : uuid.UUID
        Test set to detach from
    test_ids : sequence of uuid.UUID
        Tests to detach
    """
    if not test_ids:
        return

    db.execute(
        test_test_set_association.delete().where(
            test_test_set_association.c.test_id.in_(list(test_ids)),
            test_test_set_association.c.test_set_id == test_set_id,
        )
    )


def set_explorer_test_metadata(
    db: Session, updates: Sequence[Tuple[models.Test, Dict[str, Any]]]
) -> None:
    """Write new ``test_metadata`` onto already-loaded tests, flushing once.

    Used by evaluation, which computes a verdict per test concurrently and then applies
    them all together -- keeping the ORM mutation off the concurrent path, since the
    tests share one request session.

    Parameters
    ----------
    db : Session
        Database session
    updates : sequence of (models.Test, dict)
        Tests paired with their replacement metadata
    """
    if not updates:
        return

    for db_test, metadata in updates:
        db_test.test_metadata = metadata

    db.flush()


def set_explorer_test_outputs(db: Session, outputs: Dict[str, str]) -> List[str]:
    """Store generated endpoint outputs on the given tests' ``test_metadata``.

    Loads all target tests in one query rather than one lookup per test, then writes
    ``test_metadata["output"]`` on each. Ids with no matching test are skipped silently.

    Parameters
    ----------
    db : Session
        Database session
    outputs : dict of str to str
        Test id (as a string) mapped to the output to store

    Returns
    -------
    list of str
        The test ids that were written, in the order the tests came back.
    """
    if not outputs:
        return []

    db_tests = db.query(models.Test).filter(models.Test.id.in_(list(outputs.keys()))).all()

    written: List[str] = []
    for db_test in db_tests:
        test_id_str = str(db_test.id)
        meta = dict(db_test.test_metadata or {})
        meta["output"] = outputs[test_id_str]
        db_test.test_metadata = meta
        written.append(test_id_str)

    db.flush()
    return written


# --- Metrics ------------------------------------------------------------------------


def get_test_set_metrics(db: Session, test_set_id: uuid.UUID) -> List[models.Metric]:
    """Metrics attached to a test set.

    Queried by id rather than via ``test_set.metrics`` because the callers
    (``routers/explorer.py`` by way of the settings service) don't guarantee that
    many-to-many relationship is eager-loaded on the test set they pass in.

    Parameters
    ----------
    db : Session
        Database session
    test_set_id : uuid.UUID
        Test set whose metrics to load

    Returns
    -------
    list of models.Metric
        The attached metrics.
    """
    return db.query(models.Metric).filter(models.Metric.test_sets.any(id=test_set_id)).all()


# --- Embeddings ---------------------------------------------------------------------


def get_test_for_embedding(
    db: Session, test_id: str, organization_id: str
) -> Optional[models.Test]:
    """Load a test with the relationships ``Test.to_searchable_text()`` reads.

    Parameters
    ----------
    db : Session
        Database session
    test_id : str
        Test to load
    organization_id : str
        Organization ID for tenant isolation

    Returns
    -------
    models.Test or None
        The test with prompt, topic, behavior, category and test type loaded.
    """
    return (
        QueryBuilder(db, models.Test)
        .with_custom_filter(
            lambda q: q.filter(
                models.Test.id == test_id, models.Test.organization_id == organization_id
            )
        )
        .with_related(
            include(models.Test.prompt),
            include(models.Test.topic),
            include(models.Test.behavior),
            include(models.Test.category),
            include(models.Test.test_type),
        )
        .first()
    )


def upsert_test_embedding(
    db: Session,
    *,
    embedding: schemas.EmbeddingCreate,
    organization_id: str,
    user_id: str,
) -> Optional[models.Embedding]:
    """Insert an embedding, tolerating a concurrent writer that got there first.

    The insert runs inside a savepoint so that a unique-constraint collision can be
    recovered from without poisoning the surrounding transaction -- the caller's request
    session may have unrelated pending work. On collision the winning row is returned
    instead.

    Parameters
    ----------
    db : Session
        Database session
    embedding : schemas.EmbeddingCreate
        Row to insert
    organization_id : str
        Organization ID for tenant isolation
    user_id : str
        Acting user

    Returns
    -------
    models.Embedding or None
        The inserted row, or the row a concurrent writer created.

    Raises
    ------
    sqlalchemy.exc.IntegrityError
        If the insert fails for a reason other than the row already existing.
    """
    try:
        with db.begin_nested():
            return create_embedding(
                db,
                embedding=embedding,
                organization_id=organization_id,
                user_id=user_id,
            )
    except IntegrityError:
        existing = get_embedding_by_hash(
            db,
            entity_id=embedding.entity_id,
            entity_type=embedding.entity_type,
            organization_id=organization_id,
            config_hash=embedding.config_hash,
            text_hash=embedding.text_hash,
            status_id=embedding.status_id,
        )
        if existing:
            return existing
        raise


def get_default_embedding_model(db: Session, organization_id: str) -> Optional[models.Model]:
    """Fallback row for ``embedding.model_id`` when user settings omit an embedding model.

    Tries the organization's model named "Rhesis Default Embedding" first, then any
    protected embedding model from the ``rhesis`` provider.

    Parameters
    ----------
    db : Session
        Database session
    organization_id : str
        Organization ID for tenant isolation

    Returns
    -------
    models.Model or None
        The default embedding model, or None when the organization has neither.
    """
    org_uuid = uuid.UUID(organization_id)

    by_name = (
        db.query(models.Model)
        .filter(
            models.Model.organization_id == org_uuid,
            models.Model.name == "Rhesis Default Embedding",
            models.Model.model_type == ModelType.EMBEDDING.value,
        )
        .first()
    )
    if by_name:
        return by_name

    return (
        db.query(models.Model)
        .join(models.TypeLookup, models.Model.provider_type_id == models.TypeLookup.id)
        .filter(
            models.Model.organization_id == org_uuid,
            models.TypeLookup.type_value == "rhesis",
            models.Model.is_protected.is_(True),
            models.Model.model_type == ModelType.EMBEDDING.value,
        )
        .first()
    )
