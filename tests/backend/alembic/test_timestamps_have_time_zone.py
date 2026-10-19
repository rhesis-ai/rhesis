"""Every timestamp column is stored with a time zone.

A plain TIMESTAMP comes back naive, so the API sends it without an offset and
browsers read the UTC value as local time. The notification table shipped that way
(fixed in c4f9e2a7d1b6); this keeps a new table from repeating it.
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    os.environ.get("RHESIS_SKIP_MIGRATIONS", "").lower() in ("1", "true", "yes"),
    reason="Checks the migrated schema; skipped when RHESIS_SKIP_MIGRATIONS is set.",
)


def test_no_timestamp_without_time_zone(test_db: Session):
    naive = (
        test_db.execute(
            text(
                "SELECT table_name || '.' || column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND data_type = 'timestamp without time zone' "
                "ORDER BY 1"
            )
        )
        .scalars()
        .all()
    )

    assert naive == [], f"Use DateTime(timezone=True) / TIMESTAMPTZ for: {naive}"
