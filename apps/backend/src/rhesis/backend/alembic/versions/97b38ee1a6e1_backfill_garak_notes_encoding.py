"""backfill_garak_notes_encoding

Backfills garak_notes into test_metadata for tests imported from encoding probes
(InjectBase64, InjectAscii85, InjectBase16, …) before per-prompt trigger tracking
was introduced.

Encoding probes are probe-coupled: every prompt encodes a *different* payload, and
the DecodeMatch / DecodeApprox detectors need attempt.notes["triggers"] to contain
the plaintext payload that was encoded in that specific prompt.

Strategy
--------
For each test row whose garak_module is 'encoding' and whose test_metadata has no
garak_notes yet:
  1. Determine the probe class (e.g. InjectBase64) from test_metadata.
  2. Instantiate the probe with follow_prompt_cap=False so we get the *complete*,
     deterministic prompt→trigger mapping (all templates × all payloads × all encoders).
  3. Look up the test's prompt content in that mapping to find the correct trigger.
  4. Write {"triggers": [trigger]} into test_metadata["garak_notes"].

Tests that already have garak_notes, or whose prompt text is not found in the mapping
(e.g. tests from a very old garak version with different templates), are left untouched.

Revision ID: 97b38ee1a6e1
Revises: d592924f5b73
Create Date: 2026-04-21
"""

import json
import logging
from typing import Dict, Optional, Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

revision: str = "97b38ee1a6e1"
down_revision: Union[str, None] = "d592924f5b73"
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


def _build_prompt_trigger_map(probe_class_name: str) -> Optional[Dict[str, str]]:
    """
    Instantiate an encoding probe with the cap disabled and return a complete mapping of
    prompt_text → trigger_string.

    The mapping is deterministic: _generate_encoded_prompts produces a sorted list of
    unique (prompt, trigger) pairs.  Disabling the cap ensures all pairs are present,
    not just the random sample stored during the original import.
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

        if not hasattr(instance, "prompts") or not hasattr(instance, "triggers"):
            return None

        return {str(p): str(t) for p, t in zip(instance.prompts, instance.triggers)}

    except Exception as exc:
        logger.warning("Could not build trigger map for %s: %s", probe_class_name, exc)
        return None


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        print("\nBackfilling garak_notes in test_metadata for encoding probes...")

        result = session.execute(
            sa.text(
                """
                SELECT t.id, t.test_metadata, p.content AS prompt_content
                FROM test t
                JOIN prompt p ON p.id = t.prompt_id
                WHERE t.test_metadata->>'source' = 'garak'
                  AND t.test_metadata->>'garak_module' = 'encoding'
                  AND t.test_metadata->'garak_notes' IS NULL
                """
            )
        )
        rows = result.fetchall()
        print(f"  Found {len(rows)} encoding tests without garak_notes.")

        trigger_maps: Dict[str, Optional[Dict[str, str]]] = {}

        updated = 0
        skipped_no_map = 0
        skipped_no_match = 0

        for row in rows:
            test_id = row[0]
            metadata = row[1] or {}
            prompt_content = row[2] or ""
            probe_class_name = metadata.get("garak_probe_class", "")

            if probe_class_name not in ENCODING_PROBE_CLASSES:
                skipped_no_map += 1
                continue

            if probe_class_name not in trigger_maps:
                trigger_maps[probe_class_name] = _build_prompt_trigger_map(probe_class_name)

            trigger_map = trigger_maps[probe_class_name]
            if not trigger_map:
                skipped_no_map += 1
                continue

            trigger = trigger_map.get(prompt_content)
            if not trigger:
                skipped_no_match += 1
                continue

            patch = json.dumps({"garak_notes": {"triggers": [trigger]}})
            session.execute(
                sa.text(
                    """
                    UPDATE test
                    SET test_metadata = test_metadata || CAST(:patch AS jsonb)
                    WHERE id = :test_id
                    """
                ),
                {"test_id": test_id, "patch": patch},
            )
            updated += 1

        session.commit()
        print(
            f"  Updated {updated} tests. "
            f"Skipped {skipped_no_map} (no map) + {skipped_no_match} (prompt not found)."
        )

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def downgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        print("\nRemoving backfilled garak_notes from encoding test_metadata...")

        session.execute(
            sa.text(
                """
                UPDATE test
                SET test_metadata = test_metadata - 'garak_notes'
                WHERE test_metadata->>'source' = 'garak'
                  AND test_metadata->>'garak_module' = 'encoding'
                  AND test_metadata ? 'garak_notes'
                  AND test_metadata->'garak_notes' ? 'triggers'
                """
            )
        )

        session.commit()
        print("  Done.")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
