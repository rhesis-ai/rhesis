#!/usr/bin/env python3
"""
Test Authentication Setup Script

This script sets up persistent authentication data for tests, ensuring that
the RHESIS_API_KEY environment variable corresponds to a valid token in the database.

Usage:
    python setup_test_auth.py
    
This will:
1. Create a test organization and user if they don't exist
2. Create or update the authentication token
3. Set up the RHESIS_API_KEY environment variable
4. Provide instructions for running tests
"""

import os
import sys
import uuid
from typing import Tuple, Optional

# Add the backend source to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'apps', 'backend', 'src'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from rhesis.backend.app.database import get_database_url
from rhesis.backend.app.models import User, Organization, Token
import hashlib
import secrets
from datetime import datetime, timezone


def generate_test_api_key() -> str:
    """Generate a test API key with a recognizable prefix."""
    return f"test_api_key_{secrets.token_urlsafe(32)}"


def setup_test_auth() -> Tuple[str, str, str, str]:
    """
    Set up test authentication data.
    
    Returns:
        Tuple of (api_key, user_id, org_id, token_id)
    """
    print("🔧 Setting up test authentication data...")
    
    # Create database connection
    engine = create_engine(get_database_url())
    SessionLocal = sessionmaker(bind=engine)
    
    with SessionLocal() as db:
        try:
            # Check if we already have a test API key from environment
            existing_api_key = os.getenv("RHESIS_API_KEY")
            if existing_api_key and existing_api_key.startswith("test_api_key_"):
                print(f"🔍 Checking existing API key: {existing_api_key[:20]}...")
                
                # Check if this token exists in the database
                existing_token = db.query(Token).filter(Token.token == existing_api_key).first()
                if existing_token:
                    user = db.query(User).filter(User.id == existing_token.user_id).first()
                    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
                    
                    if user and org:
                        print(f"✅ Existing test auth data is valid!")
                        print(f"   User: {user.email} ({user.id})")
                        print(f"   Org: {org.name} ({org.id})")
                        print(f"   Token: {existing_token.id}")
                        return existing_api_key, str(user.id), str(org.id), str(existing_token.id)
                
                print("⚠️ Existing API key is invalid, creating new one...")
            
            # Create or get test organization
            test_org = db.query(Organization).filter(Organization.name == "Test Organization").first()
            if not test_org:
                test_org = Organization(
                    id=uuid.uuid4(),
                    name="Test Organization",
                    description="Organization for running automated tests",
                    is_onboarding_complete=True,
                    is_active=True
                )
                db.add(test_org)
                db.flush()
                print(f"📁 Created test organization: {test_org.id}")
            else:
                print(f"📁 Using existing test organization: {test_org.id}")
            
            # Create or get test user
            test_user = db.query(User).filter(User.email == "test@rhesis.com").first()
            if not test_user:
                test_user = User(
                    id=uuid.uuid4(),
                    email="test@rhesis.com",
                    name="Test User",
                    organization_id=test_org.id,
                    is_active=True
                )
                db.add(test_user)
                db.flush()
                print(f"👤 Created test user: {test_user.id}")
            else:
                # Update organization_id if needed
                if test_user.organization_id != test_org.id:
                    test_user.organization_id = test_org.id
                    db.flush()
                print(f"👤 Using existing test user: {test_user.id}")
            
            # Generate new API key
            api_key = generate_test_api_key()
            
            # Create or update test token
            existing_token = db.query(Token).filter(Token.user_id == test_user.id).first()
            if existing_token:
                # Update existing token
                existing_token.token = api_key
                token = existing_token
                print(f"🔑 Updated existing token: {token.id}")
            else:
                # Create new token
                token = Token(
                    id=uuid.uuid4(),
                    token=api_key,
                    user_id=test_user.id,
                    organization_id=test_org.id,
                    name="Test API Token",
                    token_type="api_key"
                )
                db.add(token)
                print(f"🔑 Created test token: {token.id}")
            
            # Commit all changes
            db.commit()
            
            print(f"\n✅ Test authentication setup completed!")
            print(f"   API Key: {api_key}")
            print(f"   User ID: {test_user.id}")
            print(f"   Org ID: {test_org.id}")
            print(f"   Token ID: {token.id}")
            
            return api_key, str(test_user.id), str(test_org.id), str(token.id)
            
        except Exception as e:
            db.rollback()
            print(f"❌ Error setting up test auth: {e}")
            raise


def update_env_file(api_key: str) -> None:
    """Update the .env file with the test API key."""
    env_file_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    
    print(f"\n🔧 Updating environment configuration...")
    
    # Read existing .env file if it exists
    env_lines = []
    if os.path.exists(env_file_path):
        with open(env_file_path, 'r') as f:
            env_lines = f.readlines()
    
    # Update or add RHESIS_API_KEY
    updated = False
    for i, line in enumerate(env_lines):
        if line.startswith('RHESIS_API_KEY='):
            env_lines[i] = f'RHESIS_API_KEY={api_key}\n'
            updated = True
            break
    
    if not updated:
        env_lines.append(f'RHESIS_API_KEY={api_key}\n')
    
    # Write back to .env file
    with open(env_file_path, 'w') as f:
        f.writelines(env_lines)
    
    print(f"✅ Updated {env_file_path}")


def main():
    """Main setup function."""
    print("🚀 Setting up persistent test authentication data...\n")
    
    try:
        # Set up authentication data
        api_key, user_id, org_id, token_id = setup_test_auth()
        
        # Update .env file
        update_env_file(api_key)
        
        # Set environment variable for current session
        os.environ['RHESIS_API_KEY'] = api_key
        
        print(f"\n🎉 Setup completed successfully!")
        print(f"\n📋 Next steps:")
        print(f"   1. Export the API key in your shell:")
        print(f"      export RHESIS_API_KEY={api_key}")
        print(f"   2. Or source the .env file:")
        print(f"      source .env")
        print(f"   3. Run tests:")
        print(f"      python -m pytest tests/backend/")
        print(f"\n💡 The authentication data will persist across test runs,")
        print(f"   so you won't need to restore the database every time!")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
