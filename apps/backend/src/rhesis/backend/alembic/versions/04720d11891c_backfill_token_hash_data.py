"""backfill_token_hash_data

Revision ID: 04720d11891c
Revises: 024a24c97022
Create Date: 2025-10-08

"""

import hashlib
import os
from typing import Sequence, Union

from alembic import op
from cryptography.fernet import Fernet
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "04720d11891c"
down_revision: Union[str, None] = "024a24c97022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BATCH_SIZE = 100


def hash_token(token_value: str) -> str:
    """Create SHA-256 hash of token value."""
    return hashlib.sha256(token_value.encode()).hexdigest()


def decrypt_token(ciphertext: str, cipher: Fernet) -> str:
    """Decrypt an encrypted token."""
    try:
        decrypted_bytes = cipher.decrypt(ciphertext.encode())
        return decrypted_bytes.decode()
    except Exception as e:
        raise Exception(f"Failed to decrypt token: {str(e)}")


def upgrade() -> None:
    """Backfill token_hash for existing tokens and add constraints.

    This migration:
    1. Decrypts each existing token
    2. Computes its SHA-256 hash
    3. Stores the hash in token_hash column
    4. Adds unique constraint and index
    5. Sets column to NOT NULL
    """
    print("\n" + "=" * 60)
    print("🔐 TOKEN HASH BACKFILL MIGRATION")
    print("=" * 60)

    # Get encryption key
    encryption_key = os.getenv("DB_ENCRYPTION_KEY")
    if not encryption_key:
        raise Exception(
            "DB_ENCRYPTION_KEY environment variable is required for this migration. "
            "This key is needed to decrypt existing tokens and compute their hashes."
        )

    cipher = Fernet(encryption_key.encode())
    connection = op.get_bind()

    # Count total tokens
    result = connection.execute(text("SELECT COUNT(*) FROM token"))
    total_tokens = result.scalar()

    print(f"\nFound {total_tokens} tokens to process")

    if total_tokens == 0:
        print("✓ No tokens to process")
    else:
        offset = 0
        processed_count = 0
        skipped_count = 0

        while offset < total_tokens:
            # Fetch batch of tokens
            tokens = connection.execute(
                text(
                    """
                SELECT id, token, token_hash
                FROM token
                WHERE token_hash IS NULL
                ORDER BY id
                LIMIT :batch_size OFFSET :offset
                """
                ),
                {"batch_size": BATCH_SIZE, "offset": offset},
            ).fetchall()

            for token_record in tokens:
                token_id, encrypted_token, existing_hash = token_record

                # Skip if already has hash
                if existing_hash:
                    skipped_count += 1
                    continue

                try:
                    # Decrypt the token
                    decrypted_token = decrypt_token(encrypted_token, cipher)

                    # Compute hash
                    token_hash_value = hash_token(decrypted_token)

                    # Update the record
                    connection.execute(
                        text(
                            "UPDATE token SET token_hash = :token_hash, updated_at = NOW() WHERE id = :token_id"
                        ),
                        {"token_hash": token_hash_value, "token_id": str(token_id)},
                    )
                    processed_count += 1

                except Exception as e:
                    print(f"  ⚠ Warning: Could not process token {token_id}: {e}")
                    skipped_count += 1

            offset += BATCH_SIZE
            if processed_count + skipped_count > 0:
                print(f"  Progress: {min(offset, total_tokens)}/{total_tokens} tokens processed")

        print(f"\n✓ Backfill complete: {processed_count} hashed, {skipped_count} skipped")

    # Add unique constraint and index
    print("\nAdding constraints and index...")
    op.create_index("ix_token_token_hash", "token", ["token_hash"], unique=True)

    # Set column to NOT NULL
    print("Setting token_hash to NOT NULL...")
    op.alter_column("token", "token_hash", nullable=False)

    print("\n" + "=" * 60)
    print("✅ Migration complete")
    print("=" * 60)
    print()


def downgrade() -> None:
    """Remove token_hash constraints.

    Note: This does not remove the token_hash data, only the constraints.
    Use the previous migration's downgrade to remove the column entirely.
    """
    print("\n🔄 Removing token_hash constraints...")

    # Remove index
    op.drop_index("ix_token_token_hash", table_name="token")

    # Set column to nullable
    op.alter_column("token", "token_hash", nullable=True)

    print("✓ Constraints removed")
    print()
