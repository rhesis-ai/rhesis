"""backfill_garak_notes_encoding_by_index

Corrective backfill for encoding tests that were skipped by the original
97b38ee1a6e1 migration because their prompt text no longer matches the
current garak version's generated prompts.

Root cause
----------
The original migration built a prompt_text → trigger map and looked up each
test's stored prompt content as a key.  When the garak template changed
between the version used for import and the version running the migration,
the lookup returned nothing and the test was silently skipped.

Strategy (this migration)
-------------------------
garak_probe_id already encodes the probe index: "encoding.InjectAscii85.63"
→ index 63.  We use that index to look up instance.triggers[63] directly,
bypassing text matching entirely.  This is O(1) per test and fully
deterministic regardless of template changes.

Only tests that still have no garak_notes after the original migration are
touched.

Revision ID: f3fc3b9e444f9a32
Revises: c4d8e2f1a3b5
Create Date: 2026-04-24
"""

import json
import logging
from typing import Dict, List, Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

revision: str = "f3fc3b9e444f9a32"
down_revision: Union[str, None] = "c4d8e2f1a3b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENCODING_PROBE_CLASSES = {
    "InjectAscii85",
    "InjectAtbash",
    "InjectBase16",
    "InjectBase2048",
    "InjectBase32",
    "InjectBase64",
    "InjectBraille",
    "InjectEcoji",
    "InjectHex",
    "InjectLeet",
    "InjectMime",
    "InjectMorse",
    "InjectNato",
    "InjectQP",
    "InjectROT13",
    "InjectSneakyBits",
    "InjectUU",
    "InjectUnicodeTagChars",
    "InjectUnicodeVariantSelectors",
    "InjectZalgo",
}


def _build_trigger_list(probe_class_name: str) -> Optional[List[str]]:
    """
    Instantiate an encoding probe with the cap disabled and return the full
    triggers list so callers can index directly by probe position.

    Returns None if the probe cannot be imported or instantiated.
    """
    try:
        import importlib

        module = importlib.import_module("garak.probes.encoding")
        probe_cls = getattr(module, probe_class_name, None)
        if probe_cls is None:
            return None

        original_cap = getattr(probe_cls, "follow_prompt_cap", True)
        probe_cls.follow_prompt_cap = False
        try:
            instance = probe_cls()
        finally:
            probe_cls.follow_prompt_cap = original_cap

        if not hasattr(instance, "triggers") or not instance.triggers:
            return None

        return [str(t) for t in instance.triggers]

    except Exception as exc:
        logger.warning("Could not build trigger list for %s: %s", probe_class_name, exc)
        return None


def _parse_probe_index(garak_probe_id: str) -> Optional[int]:
    """
    Extract the numeric suffix from a garak_probe_id.

    "encoding.InjectAscii85.63"  →  63
    Returns None if the ID is missing or has no numeric suffix.
    """
    if not garak_probe_id:
        return None
    parts = garak_probe_id.rsplit(".", 1)
    if len(parts) != 2:
        return None
    suffix = parts[1]
    if not suffix.isdigit():
        return None
    return int(suffix)


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        print("\nCorrective backfill: garak_notes for encoding tests (index-based)...")

        result = session.execute(
            sa.text(
                """
                SELECT t.id, t.test_metadata
                FROM test t
                WHERE t.test_metadata->>'source' = 'garak'
                  AND t.test_metadata->>'garak_module' = 'encoding'
                  AND t.test_metadata->'garak_notes' IS NULL
                """
            )
        )
        rows = result.fetchall()
        print(f"  Found {len(rows)} encoding tests still without garak_notes.")

        if not rows:
            print("  Nothing to do.")
            return

        trigger_lists: Dict[str, Optional[List[str]]] = {}

        updated = 0
        skipped_no_list = 0
        skipped_bad_index = 0
        skipped_out_of_range = 0

        for row in rows:
            test_id = row[0]
            metadata = row[1] or {}
            probe_class_name = metadata.get("garak_probe_class", "")
            garak_probe_id = metadata.get("garak_probe_id", "")

            if probe_class_name not in ENCODING_PROBE_CLASSES:
                skipped_no_list += 1
                continue

            # Build (or reuse) the full trigger list for this probe class.
            if probe_class_name not in trigger_lists:
                trigger_lists[probe_class_name] = _build_trigger_list(probe_class_name)

            triggers = trigger_lists[probe_class_name]
            if not triggers:
                skipped_no_list += 1
                continue

            # Resolve the index from garak_probe_id (e.g. "encoding.InjectAscii85.63" → 63).
            probe_index = _parse_probe_index(garak_probe_id)
            if probe_index is None:
                logger.warning(
                    "test %s: cannot parse probe index from garak_probe_id=%r — skipping",
                    test_id,
                    garak_probe_id,
                )
                skipped_bad_index += 1
                continue

            if probe_index >= len(triggers):
                logger.warning(
                    "test %s: probe index %d out of range (triggers len=%d) — skipping",
                    test_id,
                    probe_index,
                    len(triggers),
                )
                skipped_out_of_range += 1
                continue

            trigger = triggers[probe_index]
            patch = json.dumps({"garak_notes": {"triggers": [trigger]}})
            session.execute(
                sa.text(
                    """
                    UPDATE test
                    SET test_metadata = COALESCE(test_metadata, '{}'::jsonb) || CAST(:patch AS jsonb)
                    WHERE id = :test_id
                    """
                ),
                {"test_id": test_id, "patch": patch},
            )
            updated += 1

        session.commit()
        print(
            f"  Updated {updated} tests. "
            f"Skipped {skipped_no_list} (no trigger list) + "
            f"{skipped_bad_index} (bad probe id) + "
            f"{skipped_out_of_range} (index out of range)."
        )

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def downgrade() -> None:
    # This migration only fills in rows that the previous migration missed.
    # Downgrading is a no-op: the previous migration's downgrade already
    # removes all backfilled garak_notes, so running it first covers these rows.
    # We intentionally do nothing here to avoid double-removing legitimately
    # set notes (e.g. from a re-import after the fix landed).
    pass
