"""
🧹 Database Cleanup Fixtures Module

This module contains database cleanup logic for test isolation, including:
- Test database cleanup between tests
- Authentication data preservation
- Selective table cleanup with dependency ordering

Extracted from conftest.py for better modularity and maintainability.
"""

import pytest
from sqlalchemy import text
from .database import test_engine


@pytest.fixture(autouse=True)
def clean_test_database():
    """Clean test database between tests while generating fresh auth data for each test run."""
    # Clean up BEFORE each test to ensure isolation
    try:
        with test_engine.connect() as connection:
            # Get session-scoped authentication data to preserve it (outside transaction)
            auth_user_id = None
            auth_org_id = None
            auth_token_ids = []
            
            # We don't need to create fresh auth data in cleanup
            # The tests should be completely self-contained and not rely on external API keys
            print("🧹 Skipping auth data creation - tests should be self-contained")
            
            # Fallback: Preserve ALL production data if fresh generation fails
            if not auth_user_id:
                # Fallback: preserve all production tokens
                result = connection.execute(text("""
                    SELECT array_agg(DISTINCT u.id) as user_ids, 
                           array_agg(DISTINCT u.organization_id) as org_ids,
                           array_agg(DISTINCT t.id) as token_ids
                    FROM "user" u 
                    JOIN token t ON t.user_id = u.id
                """))
                
                row = result.fetchone()
                if row:
                    auth_user_ids = [str(uid) for uid in (row.user_ids or []) if uid]
                    auth_org_ids = [str(oid) for oid in (row.org_ids or []) if oid]  
                    auth_token_ids = [str(tid) for tid in (row.token_ids or []) if tid]
                    print(f"🔐 Preserving ALL production data: {len(auth_user_ids)} users, {len(auth_org_ids)} orgs, {len(auth_token_ids)} tokens")
            
            # List of tables to clean (in correct dependency order - most dependent first)
            # Clean ALL test data but preserve ONLY core authentication data (tokens, users, organization)
            tables_to_clean = [
                # Level 1: Association tables (no dependencies, just references)
                'test_test_set',  # test.id + test_set.id
                'prompt_test_set',  # prompt.id + test_set.id  
                'behavior_metric',  # behavior.id + metric.id
                'risk_use_case',  # risk.id + use_case.id
                'prompt_use_case',  # prompt.id + use_case.id
                'tagged_item',  # tag.id + entity polymorphic
                
                # Level 2: Highly dependent entities (reference many other tables)
                'comment',  # -> user, organization (polymorphic entity refs)
                'test_result',  # -> test_configuration, test_run, prompt, test, status, user, organization
                
                # Level 3: Execution/runtime entities
                'test_run',  # -> user, status, test_configuration, organization
                'test_configuration',  # -> endpoint, category, topic, prompt, use_case, test_set, user, status, organization
                
                # Level 4: Test entities
                'test_context',  # -> test, organization, user
                'test',  # -> prompt, type_lookup, user(3x), topic, behavior, category, status, organization
                
                # Level 5: Content entities  
                'prompt',  # -> demographic, category(2x), topic, behavior, prompt, prompt_template, source, user, status
                'test_set',  # -> status, type_lookup, user(3x), organization
                'prompt_template',  # -> user, organization
                'model',  # -> user(2x), organization
                'task',  # -> user(2x), status, type_lookup, organization
                'metric',  # -> user(2x), organization
                'endpoint',  # -> user, organization
                'project',  # -> user(2x), status, organization
                
                # Level 6: Reference/lookup entities (clean everything - no preservation)
                'response_pattern',  # -> organization
                'risk',  # -> organization, user
                'use_case',  # -> organization, user
                'source',  # -> organization
                'behavior',  # -> organization, user  
                'category',  # -> organization, user
                'topic',  # -> organization, user
                'demographic',  # -> dimension, organization, user
                'dimension',  # -> organization, user
                'tag',  # -> (referenced by tagged_item)
                'type_lookup',  # -> organization, user
                'status',  # -> organization, user
                
                # Level 7: User-related tables (clean everything except auth tokens)
                'subscription',  # -> user, organization (CLEAN ALL)
                
                # Level 8: Core authentication tables (preserve ONLY auth user/org/tokens)
                'token',  # -> user, organization (PRESERVE AUTH TOKENS ONLY)
                'organization',  # -> user(2x) [owner_id, user_id] (PRESERVE AUTH ORG ONLY)
                '"user"',  # -> organization [organization_id] (PRESERVE AUTH USER ONLY)
            ]
                
            # Always attempt cleanup, but preserve auth data if found
            # This prevents accidental complete data wipeout
            print(f"🧹 Starting selective cleanup...")
            if auth_user_id and auth_org_id and auth_token_ids:
                print(f"   🔐 Preserving auth data: user={auth_user_id}, org={auth_org_id}, tokens={len(auth_token_ids)}")
            else:
                print(f"   ⚠️ No auth data found to preserve - will clean everything")
                
            # Clean each table in its own transaction to prevent cascading failures
            for table_name in tables_to_clean:
                try:
                    with connection.begin():
                        if table_name == '"user"':
                            # Handle different preservation modes
                            if 'auth_user_ids' in locals() and auth_user_ids:
                                # Preserve ALL production users
                                placeholders = ','.join([f':user_{i}' for i in range(len(auth_user_ids))])
                                user_params = {f'user_{i}': user_id for i, user_id in enumerate(auth_user_ids)}
                                result = connection.execute(text(f'DELETE FROM {table_name} WHERE id NOT IN ({placeholders})'), 
                                             user_params)
                                if result.rowcount > 0:
                                    print(f"  🗑️ Cleaned {result.rowcount} users (preserved {len(auth_user_ids)} production users)")
                            elif auth_user_id:
                                # Preserve single auth user (fresh test user or specific production user)
                                result = connection.execute(text(f'DELETE FROM {table_name} WHERE id != :auth_user_id'), 
                                             {"auth_user_id": auth_user_id})
                                if result.rowcount > 0:
                                    print(f"  🗑️ Cleaned {result.rowcount} users (preserved 1 auth user)")
                        elif table_name == 'organization':
                            # Handle different preservation modes
                            if 'auth_org_ids' in locals() and auth_org_ids:
                                # Preserve ALL production organizations
                                placeholders = ','.join([f':org_{i}' for i in range(len(auth_org_ids))])
                                org_params = {f'org_{i}': org_id for i, org_id in enumerate(auth_org_ids)}
                                result = connection.execute(text(f'DELETE FROM {table_name} WHERE id NOT IN ({placeholders})'), 
                                             org_params)
                                if result.rowcount > 0:
                                    print(f"  🗑️ Cleaned {result.rowcount} organizations (preserved {len(auth_org_ids)} production orgs)")
                            elif auth_org_id:
                                # Preserve single auth organization (fresh test org or specific production org)
                                result = connection.execute(text(f'DELETE FROM {table_name} WHERE id != :auth_org_id'), 
                                             {"auth_org_id": auth_org_id})
                                if result.rowcount > 0:
                                    print(f"  🗑️ Cleaned {result.rowcount} organizations (preserved 1 auth org)")
                        elif table_name == 'token' and auth_token_ids:
                            # Preserve authentication tokens (works for both single and multiple modes)
                            placeholders = ','.join([f':token_{i}' for i in range(len(auth_token_ids))])
                            token_params = {f'token_{i}': token_id for i, token_id in enumerate(auth_token_ids)}
                            result = connection.execute(text(f'DELETE FROM {table_name} WHERE id NOT IN ({placeholders})'), 
                                         token_params)
                            if result.rowcount > 0:
                                print(f"  🗑️ Cleaned {result.rowcount} tokens (preserved {len(auth_token_ids)} auth tokens)")
                        elif table_name == 'subscription':
                            # Clean ALL subscriptions (no preservation)
                            result = connection.execute(text(f'DELETE FROM {table_name}'))
                            if result.rowcount > 0:
                                print(f"  🗑️ Cleaned {result.rowcount} subscriptions")
                        else:
                            # For all other tables (reference/lookup tables), clean everything
                            result = connection.execute(text(f'DELETE FROM {table_name}'))
                            if result.rowcount > 0:
                                print(f"  🗑️ Cleaned {result.rowcount} rows from {table_name}")
                                
                except Exception as e:
                    # If cleanup fails for a table, continue with others
                    # This is expected for tables that don't exist or have complex constraints
                    pass
                        
            print(f"✅ Selective cleanup completed")
                            
    except Exception as e:
        # If cleanup fails completely, continue - tests might still work
        print(f"Database cleanup failed: {e}")
        pass
    
    yield  # Test runs here
