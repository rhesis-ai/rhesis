"""Backfill script: migrate existing File bytea rows to object storage.

Hard-cut deployment runbook (Phase 8b):
  1. Apply schema-only Alembic revision (additive columns, nothing dropped).
  2. Brief maintenance window — pause uploads/executions.
  3. Run this script to completion.
  4. Verify: row counts + hash spot-check.
  5. Deploy new code release (storage_path required, bytea reads gone).
  6. Soak ~48 h.
  7. Apply DROP COLUMN content revision.

Usage:
    cd apps/backend
    uv run python scripts/migrate_files_to_storage.py [--sync-extract] [--batch-size N] [--dry-run]

Options:
    --sync-extract   Run text extraction synchronously during backfill (slower, no soak gap).
    --batch-size N   Number of rows per batch (default: 100).
    --dry-run        Report what would be migrated without writing anything.
"""

import argparse
import hashlib
import logging
import sys
import uuid
from pathlib import Path

# Ensure the backend src is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("backfill")


def parse_args():
    parser = argparse.ArgumentParser(description="Migrate File bytea rows to object storage")
    parser.add_argument("--sync-extract", action="store_true", help="Run extraction synchronously")
    parser.add_argument("--batch-size", type=int, default=100, help="Rows per batch (default 100)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without writing anything",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    from sqlalchemy import func
    from sqlalchemy.orm import undefer

    from rhesis.backend.app.database import get_db
    from rhesis.backend.app.models.file import File
    from rhesis.backend.app.services.storage_service import StorageService

    storage = StorageService()

    # -----------------------------------------------------------------------
    # Step 1: Count rows to migrate
    # -----------------------------------------------------------------------
    with get_db() as db:
        total_pending = (
            db.query(func.count(File.id))
            .filter(File.storage_path.is_(None), File.content.isnot(None))
            .scalar()
        )

    logger.info(
        f"Found {total_pending} File row(s) with bytea content but no storage_path."
    )

    if total_pending == 0:
        logger.info("Nothing to migrate — exiting.")
        return

    if args.dry_run:
        logger.info("[DRY RUN] Would migrate %d row(s). Exiting.", total_pending)
        return

    # -----------------------------------------------------------------------
    # Step 2: Batch migration
    # -----------------------------------------------------------------------
    migrated = 0
    failed = 0
    offset = 0
    batch_size = args.batch_size

    import asyncio

    while True:
        with get_db() as db:
            rows = (
                db.query(File)
                .options(undefer(File.content))
                .filter(File.storage_path.is_(None), File.content.isnot(None))
                .order_by(File.created_at)
                .limit(batch_size)
                .all()
            )

        if not rows:
            break

        for row in rows:
            if not row.content:
                logger.warning(f"Row {row.id}: content is empty despite filter — skipping.")
                continue

            org_id = str(row.organization_id) if row.organization_id else "unknown"
            dest_path = storage.get_attachment_original_path(
                organization_id=org_id,
                entity_type=row.entity_type,
                entity_id=str(row.entity_id),
                file_id=str(row.id),
                filename=row.filename,
            )

            content_bytes = row.content
            content_hash = hashlib.sha256(content_bytes).hexdigest()

            try:
                async def _upload():
                    async def _source():
                        yield content_bytes

                    return await storage.put_object_streaming(_source(), dest_path, row.content_type)

                _, _ = asyncio.run(_upload())

                with get_db() as db2:
                    db_row = db2.query(File).filter(File.id == row.id).first()
                    if db_row:
                        db_row.storage_path = dest_path
                        db_row.content_hash = content_hash
                        db_row.extraction_status = "pending"
                        db2.commit()

                migrated += 1
                logger.debug(f"Migrated File id={row.id} -> {dest_path}")

                # Optionally run extraction synchronously
                if args.sync_extract:
                    try:
                        from rhesis.sdk.services.extractor import extract_with_vision_fallback

                        extracted = extract_with_vision_fallback(
                            content_bytes, row.filename, row.content_type
                        )
                        with get_db() as db3:
                            db_row = db3.query(File).filter(File.id == row.id).first()
                            if db_row:
                                db_row.extracted_text = extracted
                                db_row.extraction_status = "done"
                                db3.commit()
                    except Exception as exc:
                        logger.warning(f"Sync extraction failed for File id={row.id}: {exc}")
                else:
                    # Enqueue async extraction
                    try:
                        from rhesis.backend.tasks.file.extract_text import extract_file_text

                        extract_file_text.delay(
                            file_id=str(row.id),
                            storage_path=dest_path,
                            filename=row.filename,
                            content_type=row.content_type,
                            content_hash=content_hash,
                            organization_id=org_id,
                        )
                    except Exception as exc:
                        logger.warning(
                            f"Failed to enqueue extraction for File id={row.id}: {exc}"
                        )

            except Exception as exc:
                logger.error(f"Failed to migrate File id={row.id}: {exc}", exc_info=True)
                failed += 1

        offset += batch_size
        logger.info(
            f"Progress: {migrated} migrated, {failed} failed "
            f"(batch offset={offset})"
        )

    # -----------------------------------------------------------------------
    # Step 3: Verification
    # -----------------------------------------------------------------------
    logger.info("=== Verification ===")
    with get_db() as db:
        migrated_count = (
            db.query(func.count(File.id)).filter(File.storage_path.isnot(None)).scalar()
        )
        still_pending = (
            db.query(func.count(File.id))
            .filter(File.storage_path.is_(None), File.content.isnot(None))
            .scalar()
        )

    logger.info(f"Rows with storage_path: {migrated_count}")
    logger.info(f"Rows still pending:     {still_pending}")

    # Spot-check: download 10 random migrated rows and verify hash
    import random

    with get_db() as db:
        sample = (
            db.query(File)
            .filter(File.storage_path.isnot(None), File.content_hash.isnot(None))
            .order_by(func.random())
            .limit(10)
            .all()
        )

    spot_ok = spot_fail = 0
    for row in sample:
        try:
            full_path = storage._full_path(row.storage_path)
            with storage.fs.open(full_path, "rb") as f:
                stored_bytes = f.read()
            computed = hashlib.sha256(stored_bytes).hexdigest()
            if computed == row.content_hash:
                spot_ok += 1
            else:
                logger.error(
                    f"Hash mismatch for File id={row.id}: "
                    f"expected={row.content_hash}, got={computed}"
                )
                spot_fail += 1
        except Exception as exc:
            logger.error(f"Spot-check failed for File id={row.id}: {exc}")
            spot_fail += 1

    logger.info(f"Spot-check ({len(sample)} rows): {spot_ok} OK, {spot_fail} FAILED")
    logger.info(f"=== Backfill complete: {migrated} migrated, {failed} failed ===")

    if failed > 0 or spot_fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
