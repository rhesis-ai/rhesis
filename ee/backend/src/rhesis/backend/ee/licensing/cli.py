"""License issuance CLI.

Thin command-line wrapper around :mod:`~rhesis.backend.ee.licensing.mint`.
Contains **no signing logic** — all cryptographic work lives in ``mint.py``.

Entry point
-----------
Run via the module path (works inside the ``backend`` Docker image which
already has EE installed):

.. code-block:: bash

    python -m rhesis.backend.ee.licensing.cli <subcommand> [options]

Or locally with uv from ``apps/backend/``:

.. code-block:: bash

    uv run python -m rhesis.backend.ee.licensing.cli <subcommand> [options]

Subcommands
-----------
``keygen``
    Generate a throwaway Ed25519 keypair for local testing or key rotation.
    Private PEM is written to **stderr** (so it can be piped separately from
    the public key on stdout). Never commit the private key.

``mint``
    Mint a signed JWT for an org (or blanket ``*``) and print it to stdout.
    Requires ``RHESIS_LICENSE_PRIVATE_KEY`` in the environment.

``issue``
    Mint + write the token to ``organization.license`` for the target org.
    Requires ``RHESIS_LICENSE_PRIVATE_KEY`` in the environment and DB
    connectivity via the standard ``DB_*`` env vars (same as the migrate job).
    Use ``--dry-run`` to mint without writing (useful for auditing before
    committing).

Security notes
--------------
* ``issue`` never prints the token to stdout or logs — only an issuance
  summary (org, kid, exp, jti) is emitted. This avoids leaking the signed
  token into CI/CD logs or terminal history.
* The private key is read from the environment, not from CLI args, so it
  never appears in ``ps`` output or shell history.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from rhesis.backend.ee.licensing.entitlements import (
    ENV_LICENSE_KID,
    ENV_LICENSE_PRIVATE_KEY,
    LicenseEdition,
    LicenseStatus,
)
from rhesis.backend.ee.licensing.tiers import EDITION_ENTITLEMENTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sellable_editions() -> list[str]:
    return sorted(e.value for e in EDITION_ENTITLEMENTS)


def _default_kid() -> str:
    return os.environ.get(ENV_LICENSE_KID, "").strip() or "rhesis-prod-v1"


def _parse_edition(value: str) -> LicenseEdition:
    try:
        edition = LicenseEdition(value)
    except ValueError:
        edition = LicenseEdition.UNKNOWN
    if edition not in EDITION_ENTITLEMENTS:
        valid = ", ".join(_sellable_editions())
        raise argparse.ArgumentTypeError(
            f"Invalid edition '{value}'. Choose from: {valid}"
        )
    return edition


def _parse_status(value: str) -> LicenseStatus:
    try:
        return LicenseStatus(value)
    except ValueError:
        valid = ", ".join(s.value for s in LicenseStatus if s != LicenseStatus.UNKNOWN)
        raise argparse.ArgumentTypeError(
            f"Invalid status '{value}'. Choose from: {valid}"
        )


def _require_private_key() -> None:
    """Abort early with a clear message if the private key env var is missing."""
    if not os.environ.get(ENV_LICENSE_PRIVATE_KEY, "").strip():
        print(
            f"Error: {ENV_LICENSE_PRIVATE_KEY} is not set.\n"
            "Export the Ed25519 private key PEM before running this command.\n"
            "In the Cloud Run issuance job it is mounted via --set-secrets.",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# keygen
# ---------------------------------------------------------------------------


def cmd_keygen(args: argparse.Namespace) -> None:
    """Generate a throwaway Ed25519 keypair.

    Key rotation guidance
    ---------------------
    1. Generate a new keypair with a new ``--kid`` (e.g. ``rhesis-prod-v2``).
    2. Add the public PEM as ``ee/.../licensing/public_keys/<kid>.pem`` and
       register the kid in ``keys._BAKED_KIDS``.
    3. Update ``_BAKED_KIDS`` in ``keys.py`` to include the new kid.
    4. Deploy the updated ``ee`` package to production.  Both old and new keys
       now verify — existing tokens continue to work until they expire.
    5. Use the new kid for all future ``mint``/``issue`` invocations.
    6. After all old tokens have expired or been re-issued, remove the old
       kid from ``_BAKED_KIDS`` and delete its ``.pem`` file.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PublicFormat,
        PrivateFormat,
    )

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    ).decode()
    public_pem = public_key.public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    kid = args.kid
    print(
        f"# Generated Ed25519 keypair — kid: {kid}\n"
        f"# Public PEM (save to ee/.../licensing/public_keys/{kid}.pem):",
        file=sys.stderr,
    )
    print(
        "# ⚠️  PRIVATE KEY — store in Secret Manager, never commit:\n"
        f"# Set as: export {ENV_LICENSE_PRIVATE_KEY}='<key>'\n"
        "# Or store as a GCP secret and mount via Cloud Run --set-secrets",
        file=sys.stderr,
    )
    print(private_pem, file=sys.stderr)
    # Public PEM goes to stdout so it can be redirected to the .pem file
    # directly: python -m ... keygen --kid rhesis-prod-v2 > public.pem
    print(public_pem)


# ---------------------------------------------------------------------------
# mint
# ---------------------------------------------------------------------------


def cmd_mint(args: argparse.Namespace) -> None:
    """Mint a signed license JWT and print it to stdout."""
    _require_private_key()

    from rhesis.backend.ee.licensing.mint import mint_token

    custom_features: list[str] | None = None
    if args.features:
        custom_features = [f.strip() for f in args.features.split(",") if f.strip()]

    custom_limits: dict | None = None
    if args.limits:
        try:
            custom_limits = json.loads(args.limits)
        except json.JSONDecodeError as exc:
            print(f"Error: --limits must be valid JSON: {exc}", file=sys.stderr)
            sys.exit(1)

    token = mint_token(
        org_id=args.org,
        edition=args.edition,
        status=args.status,
        ttl_days=args.ttl_days,
        kid=args.kid,
        custom_features=custom_features,
        custom_limits=custom_limits,
    )
    print(token)


# ---------------------------------------------------------------------------
# issue
# ---------------------------------------------------------------------------


def cmd_issue(args: argparse.Namespace) -> None:
    """Mint + write to organization.license (or dry-run)."""
    _require_private_key()

    from rhesis.backend.ee.licensing.entitlements import BLANKET_SUBJECT

    if args.org == BLANKET_SUBJECT:
        print(
            "Error: blanket subject '*' cannot be issued to an org row.\n"
            "Use `mint` and deploy the token as the RHESIS_LICENSE env var instead.",
            file=sys.stderr,
        )
        sys.exit(1)

    from rhesis.backend.ee.licensing.mint import issue, mint_token

    custom_features: list[str] | None = None
    if args.features:
        custom_features = [f.strip() for f in args.features.split(",") if f.strip()]

    custom_limits: dict | None = None
    if args.limits:
        try:
            custom_limits = json.loads(args.limits)
        except json.JSONDecodeError as exc:
            print(f"Error: --limits must be valid JSON: {exc}", file=sys.stderr)
            sys.exit(1)

    if args.dry_run:
        token = mint_token(
            org_id=args.org,
            edition=args.edition,
            status=args.status,
            ttl_days=args.ttl_days,
            kid=args.kid,
            custom_features=custom_features,
            custom_limits=custom_limits,
        )
        _print_summary(args.org, args.kid, token, dry_run=True)
        return

    # Live issue — connect with admin credentials (ADMIN_DB_USER / ADMIN_DB_PASS)
    # so the UPDATE on organization.license succeeds regardless of RLS policy.
    # DatabaseSettings.admin_url falls back to APP_DB_* for single-role setups.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from rhesis.backend.app.config.settings import get_database_settings

    db_settings = get_database_settings()
    admin_engine = create_engine(db_settings.admin_url)
    AdminSession = sessionmaker(bind=admin_engine, autocommit=False, autoflush=False)
    db = AdminSession()
    try:
        token = issue(
            db,
            org_id=args.org,
            edition=args.edition,
            status=args.status,
            ttl_days=args.ttl_days,
            kid=args.kid,
            dry_run=False,
            custom_features=custom_features,
            custom_limits=custom_limits,
        )
    finally:
        db.close()
        admin_engine.dispose()

    _print_summary(args.org, args.kid, token, dry_run=False)


def _print_summary(org_id: str, kid: str, token: str, *, dry_run: bool) -> None:
    """Print an issuance summary without leaking the token value."""
    import jwt as _jwt  # PyJWT — already in the venv

    try:
        # Decode without verification just to extract readable claims for the
        # summary.  We already signed/verified the token in mint_token.
        header = _jwt.get_unverified_header(token)
        payload = _jwt.decode(token, options={"verify_signature": False})
        exp_ts = payload.get("exp")
        exp_str = (
            datetime.fromtimestamp(exp_ts, tz=timezone.utc).isoformat()
            if exp_ts
            else "n/a"
        )
        jti = payload.get("jti", "n/a")
        edition = (payload.get("lic") or {}).get("edition", "n/a")
    except Exception:
        exp_str = jti = edition = "n/a"

    label = "[DRY-RUN] " if dry_run else ""
    print(
        f"\n{label}Issuance summary",
        f"  org      : {org_id}",
        f"  edition  : {edition}",
        f"  kid      : {kid}",
        f"  exp      : {exp_str}",
        f"  jti      : {jti}",
        sep="\n",
    )
    if dry_run:
        print("  (token NOT written to database)")
    else:
        print("  organization.license updated")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rhesis.backend.ee.licensing.cli",
        description="Rhesis license issuance CLI (EE only).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- keygen ---
    kg = sub.add_parser("keygen", help="Generate a new Ed25519 keypair.")
    kg.add_argument(
        "--kid",
        default=_default_kid(),
        help=(
            "Key ID to embed in the suggested filename / header "
            f"(default: ${ENV_LICENSE_KID} or rhesis-prod-v1)."
        ),
    )
    kg.set_defaults(func=cmd_keygen)

    # --- shared mint/issue options ---
    def _add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--org",
            required=True,
            metavar="ORG_ID",
            help="Org UUID or '*' for a blanket all-orgs token (mint only).",
        )
        p.add_argument(
            "--edition",
            required=True,
            type=_parse_edition,
            metavar="EDITION",
            help=f"License tier. One of: {', '.join(_sellable_editions())}.",
        )
        p.add_argument(
            "--ttl-days",
            type=int,
            default=365,
            metavar="N",
            help="Validity period in days (default: 365).",
        )
        p.add_argument(
            "--status",
            type=_parse_status,
            default=LicenseStatus.ACTIVE,
            metavar="STATUS",
            help="Billing status (default: active).",
        )
        p.add_argument(
            "--kid",
            default=_default_kid(),
            help=(
                "Key ID to use for signing "
                f"(default: ${ENV_LICENSE_KID} or rhesis-prod-v1)."
            ),
        )
        p.add_argument(
            "--features",
            default=None,
            metavar="FEATURE1,FEATURE2",
            help="Comma-separated feature override list (replaces tier defaults).",
        )
        p.add_argument(
            "--limits",
            default=None,
            metavar="JSON",
            help='JSON limits override, e.g. \'{"seats": 200}\' (merged with tier defaults).',
        )

    # --- mint ---
    m = sub.add_parser("mint", help="Mint a signed JWT and print it to stdout.")
    _add_common(m)
    m.set_defaults(func=cmd_mint)

    # --- issue ---
    i = sub.add_parser(
        "issue",
        help="Mint and write the token to organization.license (or dry-run).",
    )
    _add_common(i)
    i.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Mint the token but do not write it to the database.",
    )
    i.set_defaults(func=cmd_issue)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
