"""CRUD operations specific to Explorer test sets.

Part of the incremental split of the ``crud`` monolith: ``crud/__init__.py`` still holds
the bulk of the functions, and per-entity modules like this one take over as the code
around them is touched.
"""

import logging
from typing import Dict, List

from sqlalchemy.orm import Session

from rhesis.backend.app import models

logger = logging.getLogger(__name__)


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
