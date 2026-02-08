"""
One-time script to send password reset emails to Auth0 users who were
migrated without a local password.

These users have auth0_id set and password_hash = NULL, meaning they
authenticated via Auth0 email/password but have no local bcrypt hash.

Usage:
    cd apps/backend
    uv run python scripts/send_migration_reset_emails.py --dry-run
    uv run python scripts/send_migration_reset_emails.py
"""

import argparse
import os
import sys

from dotenv import load_dotenv

# Load .env before any app imports so DB and SMTP config is available
load_dotenv()

from sqlalchemy import text  # noqa: E402

from rhesis.backend.app.auth.token_utils import (  # noqa: E402
    create_password_reset_token,
)
from rhesis.backend.app.database import SessionLocal  # noqa: E402
from rhesis.backend.app.utils.redact import redact_email  # noqa: E402
from rhesis.backend.notifications.email.service import (  # noqa: E402
    EmailService,
)


def get_frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:3000")


def find_migrated_users_without_password(session):
    """Return rows of (id, email, name) for Auth0-migrated users
    who have no local password."""
    result = session.execute(
        text(
            "SELECT id, email, name FROM users "
            "WHERE auth0_id IS NOT NULL "
            "AND password_hash IS NULL "
            "AND is_active = true"
        )
    )
    return result.fetchall()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Send password-reset emails to Auth0-migrated users who have no local password."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List affected users without sending emails.",
    )
    args = parser.parse_args()

    email_service = EmailService()
    frontend_url = get_frontend_url()

    if not args.dry_run and not email_service.is_configured:
        print(
            "ERROR: SMTP is not configured. "
            "Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, "
            "and FROM_EMAIL environment variables.",
            file=sys.stderr,
        )
        sys.exit(1)

    session = SessionLocal()
    try:
        users = find_migrated_users_without_password(session)

        if not users:
            print("No migrated users without a password found.")
            return

        print(f"Found {len(users)} migrated user(s) without a password:")
        for user_id, email, name in users:
            print(f"  - {redact_email(email)}  (id={user_id})")

        if args.dry_run:
            print("\n[DRY RUN] No emails sent.")
            return

        print()
        sent = 0
        failed = 0
        for user_id, email, name in users:
            try:
                token = create_password_reset_token(str(user_id), email)
                reset_url = f"{frontend_url}/auth/reset-password?token={token}"
                ok = email_service.send_password_reset_email(
                    recipient_email=email,
                    recipient_name=name,
                    reset_url=reset_url,
                )
                if ok:
                    print(f"  SENT  {redact_email(email)}")
                    sent += 1
                else:
                    print(f"  FAIL  {redact_email(email)} (EmailService returned False)")
                    failed += 1
            except Exception as exc:
                print(f"  ERROR {redact_email(email)}: {exc}")
                failed += 1

        print(f"\nDone. Sent: {sent}, Failed: {failed}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
