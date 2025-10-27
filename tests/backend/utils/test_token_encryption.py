import pytest
import os
from cryptography.fernet import Fernet
from sqlalchemy import text
from datetime import datetime, timedelta, timezone

from rhesis.backend.app.models.token import Token
from rhesis.backend.app.utils.encryption import is_encrypted, hash_token
from tests.backend.routes.fixtures.data_factories import BaseDataFactory
from faker import Faker

fake = Faker()


class TokenEncryptionDataFactory(BaseDataFactory):
    """Factory for generating token test data for encryption tests"""
    
    @classmethod
    def minimal_data(cls) -> dict:
        import uuid
        return {
            "name": f"{fake.word()} Token {uuid.uuid4().hex[:8]}",  # Ensure unique name
            "token": cls.generate_token(),
            "token_type": fake.random_element(["api_key", "access_token", "bearer"])
        }
    
    @classmethod
    def sample_data(cls) -> dict:
        data = cls.minimal_data()
        data.update({
            "token_obfuscated": cls.obfuscate_token(data["token"]),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
            "last_used_at": datetime.now(timezone.utc),
        })
        return data
    
    @classmethod
    def generate_token(cls) -> str:
        """Generate a realistic token"""
        import uuid
        return "rh_" + str(uuid.uuid4()).replace('-', '')[:48]
    
    @classmethod
    def obfuscate_token(cls, token: str) -> str:
        """Obfuscate token for display"""
        if len(token) > 8:
            return token[:4] + "..." + token[-4:]
        return "***"
    
    @classmethod
    def expired_token_data(cls) -> dict:
        """Generate expired token data"""
        data = cls.sample_data()
        data["expires_at"] = datetime.now(timezone.utc) - timedelta(days=1)
        return data


# Encryption key is now set globally in conftest.py


class TestTokenEncryption:
    """Test encryption of Token field"""
    
    def test_token_encrypted_in_db(self, test_db, authenticated_user_id, test_org_id):
        """Test that token is encrypted when stored in database"""
        token_data = TokenEncryptionDataFactory.sample_data()
        token_data["user_id"] = authenticated_user_id
        token_data["organization_id"] = test_org_id
        token_data["token_hash"] = hash_token(token_data["token"])  # Add the missing token_hash
        token = Token(**token_data)
        test_db.add(token)
        test_db.commit()
        
        # Read directly from DB (bypassing ORM)
        result = test_db.execute(
            text("SELECT token FROM token WHERE id = :id"),
            {"id": str(token.id)}
        ).fetchone()
        
        # Verify encrypted in DB
        assert result[0] is not None
        assert result[0] != token_data["token"]
        assert is_encrypted(result[0])
        
        # Verify ORM returns decrypted value
        test_db.refresh(token)
        assert token.token == token_data["token"]
    
    def test_token_obfuscated_not_encrypted(self, test_db, authenticated_user_id, test_org_id):
        """Test that token_obfuscated is NOT encrypted (it's for display)"""
        token_data = TokenEncryptionDataFactory.sample_data()
        token_data["user_id"] = authenticated_user_id
        token_data["organization_id"] = test_org_id
        token_data["token_hash"] = hash_token(token_data["token"])
        token = Token(**token_data)
        test_db.add(token)
        test_db.commit()
        
        result = test_db.execute(
            text("SELECT token_obfuscated FROM token WHERE id = :id"),
            {"id": str(token.id)}
        ).fetchone()
        
        # token_obfuscated should remain plaintext
        assert result[0] == token_data["token_obfuscated"]
        assert not is_encrypted(result[0])
    
    def test_update_token(self, test_db, authenticated_user_id, test_org_id):
        """Test updating token (token refresh/rotation scenario)"""
        token_data = TokenEncryptionDataFactory.sample_data()
        token_data["user_id"] = authenticated_user_id
        token_data["organization_id"] = test_org_id
        token_data["token_hash"] = hash_token(token_data["token"])
        token = Token(**token_data)
        test_db.add(token)
        test_db.commit()
        
        # Rotate token
        new_token = TokenEncryptionDataFactory.generate_token()
        token.token = new_token
        token.token_hash = hash_token(new_token)
        token.last_refreshed_at = datetime.now(timezone.utc)
        test_db.commit()
        
        # Verify new token is encrypted
        result = test_db.execute(
            text("SELECT token FROM token WHERE id = :id"),
            {"id": str(token.id)}
        ).fetchone()
        
        assert is_encrypted(result[0])
        test_db.refresh(token)
        assert token.token == new_token
        assert token.token != token_data["token"]
    
    def test_different_token_types(self, test_db, authenticated_user_id, test_org_id):
        """Test encryption works for different token types"""
        token_types = ["api_key", "access_token", "bearer", "refresh_token"]
        
        for token_type in token_types:
            token_data = TokenEncryptionDataFactory.minimal_data()
            token_data["token_type"] = token_type
            token_data["user_id"] = authenticated_user_id
            token_data["organization_id"] = test_org_id
            token_data["token_hash"] = hash_token(token_data["token"])
            token = Token(**token_data)
            test_db.add(token)
            test_db.commit()
            
            # Check encryption
            result = test_db.execute(
                text("SELECT token FROM token WHERE id = :id"),
                {"id": str(token.id)}
            ).fetchone()
            
            assert is_encrypted(result[0])
            test_db.refresh(token)
            assert token.token == token_data["token"]
    
    def test_multiple_tokens_for_same_user(self, test_db, authenticated_user_id, test_org_id):
        """Test multiple tokens with different values"""
        tokens_data = [
            TokenEncryptionDataFactory.sample_data(),
            TokenEncryptionDataFactory.sample_data(),
            TokenEncryptionDataFactory.sample_data(),
        ]
        
        created_tokens = []
        for token_data in tokens_data:
            token_data["user_id"] = authenticated_user_id
            token_data["organization_id"] = test_org_id
            token_data["token_hash"] = hash_token(token_data["token"])
            token = Token(**token_data)
            test_db.add(token)
            test_db.commit()
            created_tokens.append((token.id, token_data["token"]))
        
        # Verify each token is encrypted and decrypts correctly
        for token_id, original_token in created_tokens:
            result = test_db.execute(
                text("SELECT token FROM token WHERE id = :id"),
                {"id": str(token_id)}
            ).fetchone()
            
            assert is_encrypted(result[0])
            
            token = test_db.query(Token).filter(Token.id == token_id).first()
            assert token.token == original_token
    
    def test_token_query(self, test_db, authenticated_user_id, test_org_id):
        """Test that we can query tokens and access values transparently"""
        token_data = TokenEncryptionDataFactory.sample_data()
        token_data["user_id"] = authenticated_user_id
        token_data["organization_id"] = test_org_id
        token_data["token_hash"] = hash_token(token_data["token"])
        token = Token(**token_data)
        test_db.add(token)
        test_db.commit()
        
        # Query via ORM
        queried_token = test_db.query(Token).filter(Token.name == token_data["name"]).first()
        assert queried_token is not None
        assert queried_token.token == token_data["token"]  # Transparently decrypted
    
    def test_expired_token_still_encrypted(self, test_db, authenticated_user_id, test_org_id):
        """Test that expired tokens are still encrypted"""
        token_data = TokenEncryptionDataFactory.expired_token_data()
        token_data["user_id"] = authenticated_user_id
        token_data["organization_id"] = test_org_id
        token_data["token_hash"] = hash_token(token_data["token"])
        token = Token(**token_data)
        test_db.add(token)
        test_db.commit()
        
        # Even expired tokens should be encrypted
        result = test_db.execute(
            text("SELECT token FROM token WHERE id = :id"),
            {"id": str(token.id)}
        ).fetchone()
        
        assert is_encrypted(result[0])
        
        # Verify expired property works with encrypted token
        test_db.refresh(token)
        assert token.is_expired is True
        assert token.token == token_data["token"]
    
    def test_token_last_used_tracking(self, test_db, authenticated_user_id, test_org_id):
        """Test that token usage tracking works with encryption"""
        token_data = TokenEncryptionDataFactory.sample_data()
        token_data["user_id"] = authenticated_user_id
        token_data["organization_id"] = test_org_id
        token_data["token_hash"] = hash_token(token_data["token"])
        token = Token(**token_data)
        test_db.add(token)
        test_db.commit()
        
        # Simulate token usage
        token.last_used_at = datetime.now(timezone.utc)
        test_db.commit()
        
        # Token should still be encrypted and accessible
        result = test_db.execute(
            text("SELECT token FROM token WHERE id = :id"),
            {"id": str(token.id)}
        ).fetchone()
        
        assert is_encrypted(result[0])
        test_db.refresh(token)
        assert token.token == token_data["token"]
        assert token.last_used_at is not None
    
    def test_token_required_validation(self, test_db, authenticated_user_id, test_org_id):
        """Test that token field is required (cannot be None)"""
        token_data = TokenEncryptionDataFactory.minimal_data()
        token_data["token"] = None
        token_data["user_id"] = authenticated_user_id
        token_data["organization_id"] = test_org_id
        
        token = Token(**token_data)
        test_db.add(token)
        
        # Should raise IntegrityError due to nullable=False
        with pytest.raises(Exception):
            test_db.commit()
        
        test_db.rollback()

