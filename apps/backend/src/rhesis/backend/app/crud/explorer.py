"""CRUD operations specific to Explorer test sets.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the bulk of the functions, and per-entity modules like this one take over as the code
around them is touched.

Every function here flushes and never commits -- the request session owns the commit
(see ``get_db_with_tenant_variables`` in ``database.py``).
"""

import logging
import uuid
from typing import Dict, List, Optional

from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, contains_eager, joinedload

from rhesis.backend.app import models
from rhesis.backend.app.constants import ADAPTIVE_TESTING_BEHAVIOR

# _TEST_SET_RELATED_FIELDS is imported rather than relocated: three other functions in
# the monolith use the same tuple, and moving it would mean deciding a new home for a
# TestSet-wide constant while this module only owns the Explorer slice.
# crud/__init__.py never imports this module, so the parent-package import is cycle-free.
from rhesis.backend.app.crud import _TEST_SET_RELATED_FIELDS
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
