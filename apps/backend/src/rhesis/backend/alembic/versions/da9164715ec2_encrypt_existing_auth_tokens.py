"""Encrypt existing authentication tokens and API keys

Revision ID: da9164715ec2
Revises: 1b668a6bed23
Create Date: 2025-10-07

This migration encrypts existing plaintext values in endpoint, model, and token tables.
It processes records in batches to handle large datasets efficiently and is idempotent.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from typing import Union, Sequence
import os
from cryptography.fernet import Fernet


# revision identifiers, used by Alembic.
revision: str = 'da9164715ec2'
down_revision: Union[str, None] = '1b668a6bed23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Batch size for processing records
BATCH_SIZE = 100


def get_cipher():
    """Get Fernet cipher for encryption"""
    key = os.getenv('DB_ENCRYPTION_KEY')
    if not key:
        raise ValueError(
            "DB_ENCRYPTION_KEY environment variable is required for migration. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    return Fernet(key.encode())


def is_encrypted(value: str) -> bool:
    """Check if value is already encrypted (Fernet format)"""
    if not value or len(value) < 10:
        return False
    try:
        return value.startswith('gAAAAA')
    except:
        return False


def encrypt_value(cipher, value: str) -> str:
    """Encrypt a plaintext value"""
    if not value:
        return value
    if is_encrypted(value):
        return value  # Already encrypted, skip
    encrypted = cipher.encrypt(value.encode())
    return encrypted.decode()


def upgrade() -> None:
    """Encrypt existing plaintext authentication tokens and API keys"""
    
    print("\n" + "="*60)
    print("🔐 Starting encryption migration...")
    print("="*60)
    
    try:
        cipher = get_cipher()
    except ValueError as e:
        print(f"\n❌ ERROR: {e}")
        print("\nTo generate an encryption key, run:")
        print("  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        print("\nThen set it in your environment:")
        print("  export DB_ENCRYPTION_KEY='your-generated-key'")
        raise
    
    connection = op.get_bind()
    
    # ==========================================
    # PART 1: Encrypt Endpoint Authentication Fields
    # ==========================================
    print("\n📍 STEP 1/3: Encrypting endpoint authentication fields...")
    print("-" * 60)
    
    result = connection.execute(text("SELECT COUNT(*) FROM endpoint"))
    total_endpoints = result.scalar()
    print(f"Found {total_endpoints} endpoint records to process")
    
    if total_endpoints == 0:
        print("  ✓ No endpoints to process")
    else:
        offset = 0
        encrypted_count = 0
        skipped_count = 0
        
        while offset < total_endpoints:
            endpoints = connection.execute(text(
                """
                SELECT id, auth_token, client_secret, last_token
                FROM endpoint
                ORDER BY id
                LIMIT :batch_size OFFSET :offset
                """
            ), {"batch_size": BATCH_SIZE, "offset": offset}).fetchall()
            
            for endpoint in endpoints:
                endpoint_id, auth_token, client_secret, last_token = endpoint
                needs_update = False
                update_fields = {}
                
                if auth_token and not is_encrypted(auth_token):
                    update_fields['auth_token'] = encrypt_value(cipher, auth_token)
                    needs_update = True
                
                if client_secret and not is_encrypted(client_secret):
                    update_fields['client_secret'] = encrypt_value(cipher, client_secret)
                    needs_update = True
                
                if last_token and not is_encrypted(last_token):
                    update_fields['last_token'] = encrypt_value(cipher, last_token)
                    needs_update = True
                
                if needs_update:
                    set_clause = ', '.join([f"{field} = :{field}" for field in update_fields.keys()])
                    update_fields['endpoint_id'] = str(endpoint_id)
                    
                    connection.execute(
                        text(f"UPDATE endpoint SET {set_clause}, updated_at = NOW() WHERE id = :endpoint_id"),
                        update_fields
                    )
                    encrypted_count += 1
                else:
                    skipped_count += 1
            
            offset += BATCH_SIZE
            print(f"  Progress: {min(offset, total_endpoints)}/{total_endpoints} endpoints processed")
        
        print(f"  ✓ Complete: {encrypted_count} encrypted, {skipped_count} skipped (already encrypted)")
    
    # ==========================================
    # PART 2: Encrypt Model API Keys
    # ==========================================
    print("\n🤖 STEP 2/3: Encrypting model API keys...")
    print("-" * 60)
    
    result = connection.execute(text("SELECT COUNT(*) FROM model"))
    total_models = result.scalar()
    print(f"Found {total_models} model records to process")
    
    if total_models == 0:
        print("  ✓ No models to process")
    else:
        offset = 0
        encrypted_count = 0
        skipped_count = 0
        
        while offset < total_models:
            models = connection.execute(text(
                """
                SELECT id, key
                FROM model
                ORDER BY id
                LIMIT :batch_size OFFSET :offset
                """
            ), {"batch_size": BATCH_SIZE, "offset": offset}).fetchall()
            
            for model in models:
                model_id, api_key = model
                
                if api_key and not is_encrypted(api_key):
                    encrypted_key = encrypt_value(cipher, api_key)
                    connection.execute(
                        text("UPDATE model SET key = :encrypted_key, updated_at = NOW() WHERE id = :model_id"),
                        {"encrypted_key": encrypted_key, "model_id": str(model_id)}
                    )
                    encrypted_count += 1
                else:
                    skipped_count += 1
            
            offset += BATCH_SIZE
            print(f"  Progress: {min(offset, total_models)}/{total_models} models processed")
        
        print(f"  ✓ Complete: {encrypted_count} encrypted, {skipped_count} skipped (already encrypted)")
    
    # ==========================================
    # PART 3: Encrypt User Tokens
    # ==========================================
    print("\n🔑 STEP 3/3: Encrypting user-generated tokens...")
    print("-" * 60)
    
    result = connection.execute(text("SELECT COUNT(*) FROM token"))
    total_tokens = result.scalar()
    print(f"Found {total_tokens} token records to process")
    
    if total_tokens == 0:
        print("  ✓ No tokens to process")
    else:
        offset = 0
        encrypted_count = 0
        skipped_count = 0
        
        while offset < total_tokens:
            tokens = connection.execute(text(
                """
                SELECT id, token
                FROM token
                ORDER BY id
                LIMIT :batch_size OFFSET :offset
                """
            ), {"batch_size": BATCH_SIZE, "offset": offset}).fetchall()
            
            for token_record in tokens:
                token_id, token_value = token_record
                
                if token_value and not is_encrypted(token_value):
                    encrypted_token = encrypt_value(cipher, token_value)
                    connection.execute(
                        text("UPDATE token SET token = :encrypted_token, updated_at = NOW() WHERE id = :token_id"),
                        {"encrypted_token": encrypted_token, "token_id": str(token_id)}
                    )
                    encrypted_count += 1
                else:
                    skipped_count += 1
            
            offset += BATCH_SIZE
            print(f"  Progress: {min(offset, total_tokens)}/{total_tokens} tokens processed")
        
        print(f"  ✓ Complete: {encrypted_count} encrypted, {skipped_count} skipped (already encrypted)")
    
    # ==========================================
    # Verification
    # ==========================================
    print("\n🔍 Verifying encryption...")
    print("-" * 60)
    
    # Check for any remaining plaintext values
    plaintext_endpoints = connection.execute(text("""
        SELECT COUNT(*) FROM endpoint
        WHERE (auth_token IS NOT NULL AND NOT auth_token LIKE 'gAAAAA%')
           OR (client_secret IS NOT NULL AND NOT client_secret LIKE 'gAAAAA%')
           OR (last_token IS NOT NULL AND NOT last_token LIKE 'gAAAAA%')
    """)).scalar()
    
    plaintext_models = connection.execute(text("""
        SELECT COUNT(*) FROM model
        WHERE key IS NOT NULL AND NOT key LIKE 'gAAAAA%'
    """)).scalar()
    
    plaintext_tokens = connection.execute(text("""
        SELECT COUNT(*) FROM token
        WHERE token IS NOT NULL AND NOT token LIKE 'gAAAAA%'
    """)).scalar()
    
    if plaintext_endpoints == 0 and plaintext_models == 0 and plaintext_tokens == 0:
        print("  ✓ All sensitive data is now encrypted!")
    else:
        print(f"  ⚠ Warning: Found {plaintext_endpoints} plaintext endpoint fields")
        print(f"  ⚠ Warning: Found {plaintext_models} plaintext model keys")
        print(f"  ⚠ Warning: Found {plaintext_tokens} plaintext tokens")
    
    print("\n" + "="*60)
    print("✅ Encryption migration complete!")
    print("="*60)
    print()


def downgrade() -> None:
    """Rollback: Decrypt encrypted values back to plaintext
    
    WARNING: This will decrypt all encrypted data back to plaintext.
    Only use this for rollback scenarios.
    """
    print("\n" + "="*60)
    print("⚠️  WARNING: Decrypting data back to plaintext")
    print("="*60)
    
    try:
        cipher = get_cipher()
    except ValueError as e:
        print(f"\n❌ ERROR: {e}")
        raise
    
    connection = op.get_bind()
    
    # Decrypt endpoint fields
    print("\n📍 Decrypting endpoint fields...")
    endpoints = connection.execute(text(
        "SELECT id, auth_token, client_secret, last_token FROM endpoint"
    )).fetchall()
    
    decrypted_count = 0
    for endpoint in endpoints:
        endpoint_id, auth_token, client_secret, last_token = endpoint
        update_fields = {}
        
        if auth_token and is_encrypted(auth_token):
            try:
                decrypted = cipher.decrypt(auth_token.encode()).decode()
                update_fields['auth_token'] = decrypted
            except Exception as e:
                print(f"  ⚠ Warning: Could not decrypt auth_token for endpoint {endpoint_id}: {e}")
        
        if client_secret and is_encrypted(client_secret):
            try:
                decrypted = cipher.decrypt(client_secret.encode()).decode()
                update_fields['client_secret'] = decrypted
            except Exception as e:
                print(f"  ⚠ Warning: Could not decrypt client_secret for endpoint {endpoint_id}: {e}")
        
        if last_token and is_encrypted(last_token):
            try:
                decrypted = cipher.decrypt(last_token.encode()).decode()
                update_fields['last_token'] = decrypted
            except Exception as e:
                print(f"  ⚠ Warning: Could not decrypt last_token for endpoint {endpoint_id}: {e}")
        
        if update_fields:
            set_clause = ', '.join([f"{field} = :{field}" for field in update_fields.keys()])
            update_fields['endpoint_id'] = str(endpoint_id)
            connection.execute(
                text(f"UPDATE endpoint SET {set_clause} WHERE id = :endpoint_id"),
                update_fields
            )
            decrypted_count += 1
    
    print(f"  ✓ Decrypted {decrypted_count} endpoints")
    
    # Decrypt model keys
    print("\n🤖 Decrypting model keys...")
    models = connection.execute(text("SELECT id, key FROM model")).fetchall()
    
    decrypted_count = 0
    for model in models:
        model_id, api_key = model
        if api_key and is_encrypted(api_key):
            try:
                decrypted = cipher.decrypt(api_key.encode()).decode()
                connection.execute(
                    text("UPDATE model SET key = :decrypted_key WHERE id = :model_id"),
                    {"decrypted_key": decrypted, "model_id": str(model_id)}
                )
                decrypted_count += 1
            except Exception as e:
                print(f"  ⚠ Warning: Could not decrypt key for model {model_id}: {e}")
    
    print(f"  ✓ Decrypted {decrypted_count} models")
    
    # Decrypt tokens
    print("\n🔑 Decrypting tokens...")
    tokens = connection.execute(text("SELECT id, token FROM token")).fetchall()
    
    decrypted_count = 0
    for token_record in tokens:
        token_id, token_value = token_record
        if token_value and is_encrypted(token_value):
            try:
                decrypted = cipher.decrypt(token_value.encode()).decode()
                connection.execute(
                    text("UPDATE token SET token = :decrypted_token WHERE id = :token_id"),
                    {"decrypted_token": decrypted, "token_id": str(token_id)}
                )
                decrypted_count += 1
            except Exception as e:
                print(f"  ⚠ Warning: Could not decrypt token {token_id}: {e}")
    
    print(f"  ✓ Decrypted {decrypted_count} tokens")
    
    print("\n" + "="*60)
    print("✅ Rollback complete - data decrypted")
    print("="*60)
    print()
