"""
One-time script to send password-setup emails to users who were migrated
from Auth0 without a local password.

These users have provider_type='email' and password_hash=NULL, meaning
they authenticated via Auth0 email/password but have no local bcrypt
hash. Social login users (Google, GitHub, Microsoft) are excluded since
they can continue authenticating via their provider.

Usage:
    cd apps/backend
    uv run python scripts/send_migration_reset_emails.py \\
        --environment dev \\
        --config ../../infrastructure/config/service-secrets-config.sh \\
        --dry-run

    uv run python scripts/send_migration_reset_emails.py \\
        --environment prd \\
        --config ../../infrastructure/config/service-secrets-config.sh
"""

import argparse
import os
import re
import sys

# ---------------------------------------------------------------------------
# Environment prefix mapping
# ---------------------------------------------------------------------------
ENV_PREFIXES = {
    "dev": "DEV_",
    "stg": "STG_",
    "prd": "PRD_",
    "test": "TEST_",
}

# Variables the script actually needs (without prefix).
REQUIRED_VARS = [
    "SQLALCHEMY_DATABASE_URL",
    "JWT_SECRET_KEY",
    "FRONTEND_URL",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "FROM_EMAIL",
]


# ---------------------------------------------------------------------------
# Config file parser
# ---------------------------------------------------------------------------
def load_config(config_path: str, environment: str) -> dict[str, str]:
    """Parse a shell-style config file and return env vars for the
    requested environment with the prefix stripped.

    Handles lines like:
        export DEV_SQLALCHEMY_DATABASE_URL="postgresql://..."
        export DEV_SMTP_HOST="smtp.sendgrid.net"
    """
    prefix = ENV_PREFIXES[environment]
    pattern = re.compile(
        r"""^\s*export\s+""" + re.escape(prefix) + r"""(\w+)=["']?(.*?)["']?\s*$"""
    )

    result: dict[str, str] = {}
    with open(config_path) as fh:
        for line in fh:
            m = pattern.match(line)
            if m:
                var_name = m.group(1)
                var_value = m.group(2)
                result[var_name] = var_value

    return result


def apply_config(config: dict[str, str], environment: str) -> None:
    """Set the required environment variables from the parsed config.
    Raises SystemExit if any required variable is missing."""
    missing = []
    for var in REQUIRED_VARS:
        value = config.get(var)
        if value is None:
            missing.append(f"{ENV_PREFIXES[environment]}{var}")
        else:
            os.environ[var] = value

    if missing:
        print(
            "ERROR: The following variables are missing "
            "from the config file:\n  " + "\n  ".join(missing),
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description=(
            "Send password-setup emails to email/password users who have no local password."
        ),
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=list(ENV_PREFIXES.keys()),
        help="Target environment (dev, stg, prd, test).",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the service-secrets-config.sh file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List affected users without sending emails.",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 1. Parse config and set env vars BEFORE importing backend modules
    # ------------------------------------------------------------------
    if not os.path.isfile(args.config):
        print(
            f"ERROR: Config file not found: {args.config}",
            file=sys.stderr,
        )
        sys.exit(1)

    config = load_config(args.config, args.environment)
    apply_config(config, args.environment)

    print(f"Loaded config for environment: {args.environment}")
    print(f"  FRONTEND_URL = {os.environ.get('FRONTEND_URL')}")
    print(f"  SMTP_HOST    = {os.environ.get('SMTP_HOST')}")
    print()

    # ------------------------------------------------------------------
    # 2. Now import backend modules (they read env vars at import time)
    # ------------------------------------------------------------------
    from sqlalchemy import text  # noqa: E402

    from rhesis.backend.app.auth.token_utils import (  # noqa: E402
        create_password_reset_token,
    )
    from rhesis.backend.app.database import SessionLocal  # noqa: E402
    from rhesis.backend.app.utils.redact import (  # noqa: E402
        redact_email,
    )
    from rhesis.backend.notifications.email.service import (  # noqa: E402
        EmailService,
    )

    email_service = EmailService()
    frontend_url = os.environ["FRONTEND_URL"]

    if not args.dry_run and not email_service.is_configured:
        print(
            "ERROR: SMTP is not configured. Check SMTP_HOST, "
            "SMTP_PORT, SMTP_USER, SMTP_PASSWORD, and "
            "FROM_EMAIL in the config file.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # 3. Query and process users
    # ------------------------------------------------------------------
    session = SessionLocal()
    try:
        result = session.execute(
            text(
                'SELECT id, email, name FROM "user" '
                "WHERE provider_type = 'email' "
                "AND password_hash IS NULL "
                "AND is_active = true"
            )
        )
        users = result.fetchall()

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
                ok = email_service.send_migration_reset_email(
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
