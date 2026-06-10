#!/usr/bin/env python
"""Break-glass operator CLI — reassign an organization's owner.

Sanctioned replacement for the superuser escape hatch removed in SP3.
This script re-points ``organization.owner_id`` to a given user UUID.
Use it when the current owner account is inaccessible (deleted, locked out,
lost credentials) and no other principal can perform administrative tasks.

SCOPE & SAFETY
--------------
- The user **must** belong to the target organization.
- The script runs in a real transaction; failure rolls back automatically.
- The script does NOT require ``is_superuser``.
- Audit emission is intentionally deferred (locked decision, SP12).

USAGE
-----
    cd apps/backend
    uv run python scripts/recover_org_owner.py \\
        --org-id  <organization-uuid> \\
        --user-id <new-owner-user-uuid>

Dry-run (prints what WOULD happen, rolls back automatically):
    uv run python scripts/recover_org_owner.py \\
        --org-id  <organization-uuid> \\
        --user-id <new-owner-user-uuid> \\
        --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Reassign an organization's owner_id (break-glass recovery)."
    )
    p.add_argument(
        "--org-id",
        required=True,
        help="UUID of the organization whose owner_id is being reassigned.",
    )
    p.add_argument(
        "--user-id",
        required=True,
        help="UUID of the user to become the new org owner.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Log the change but roll back the transaction (no DB mutation).",
    )
    return p.parse_args()


if __name__ == "__main__":
    # Ensure src/ is importable when run directly (mirrors how uv run resolves it).
    from pathlib import Path

    src = Path(__file__).parent.parent / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from rhesis.backend.app.management.recover_org_owner import run

    args = _parse_args()
    run(args.org_id, args.user_id, dry_run=args.dry_run)
