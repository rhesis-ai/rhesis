"""Celery task for computing a graph.

This task computes a embedding graph for entities in a background worker.
"""

import logging
from uuid import UUID

from rhesis.backend.celery.core import app
from rhesis.backend.tasks.base import SilentTask

logger = logging.getLogger(__name__)


@app.task(
    base=SilentTask,
    name="rhesis.backend.tasks.embedding.compute_graph",
    bind=True,
    display_name="Embedding Graph Computation",
)
def compute_graph_task(self, entity_ids: list[str], test_set_id: str, user_id: str):
    """
    Compute an embedding graph for the given entity IDs and persist it on the test set.

    The HTTP layer resolves which entities belong to the test set and passes their IDs here.
    """
    from rhesis.backend.app import crud
    from rhesis.backend.app.services.embedding.graph_builder import build_2d_graph

    with self.get_db_session() as db:
        user = crud.get_user_by_id(db, user_id)
        if user is None:
            logger.warning("Skipping graph computation: user not found", extra={"user_id": user_id})
            return

        test_set = crud.get_test_set(db, UUID(test_set_id), str(user.organization_id), str(user.id))
        if test_set is None:
            logger.warning(
                "Skipping graph computation: test set not found",
                extra={"test_set_id": test_set_id},
            )
            return

        ids = [UUID(eid) for eid in entity_ids]
        graph = build_2d_graph(db, ids, user)

        attrs = dict(test_set.attributes or {})
        attrs["graph"] = graph.model_dump(mode="json")
        test_set.attributes = attrs
        db.add(test_set)
        db.commit()
