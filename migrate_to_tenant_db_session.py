#!/usr/bin/env python3
"""
Migration script to update all routes from get_db_session to get_tenant_db_session.

This script performs a safe find/replace operation across all router files
to migrate from separate database session dependencies to the optimized
tenant-aware database session dependency.

Usage:
    python migrate_to_tenant_db_session.py
"""

import os
import re
from pathlib import Path


def find_router_files(base_path: str) -> list[Path]:
    """Find all router files in the project."""
    router_path = Path(base_path) / "apps" / "backend" / "src" / "rhesis" / "backend" / "app" / "routers"
    return list(router_path.glob("*.py"))


def update_imports(content: str) -> str:
    """Update import statements to include get_tenant_db_session."""
    # Pattern to match existing imports from dependencies
    import_pattern = r'from rhesis\.backend\.app\.dependencies import (.+)'
    
    def replace_import(match):
        imports = match.group(1)
        # If get_tenant_db_session is not already imported, add it
        if 'get_tenant_db_session' not in imports:
            if 'get_db_session' in imports:
                imports = imports.replace('get_db_session', 'get_db_session, get_tenant_db_session')
            else:
                imports += ', get_tenant_db_session'
        return f'from rhesis.backend.app.dependencies import {imports}'
    
    return re.sub(import_pattern, replace_import, content)


def update_dependency_usage(content: str) -> str:
    """Update function parameters to use get_tenant_db_session."""
    # Pattern to match: db: Session = Depends(get_db_session)
    pattern = r'db:\s*Session\s*=\s*Depends\(get_db_session\)'
    replacement = 'db: Session = Depends(get_tenant_db_session)'
    
    return re.sub(pattern, replacement, content)


def update_file(file_path: Path) -> bool:
    """Update a single file with the migration changes."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Skip if file doesn't contain relevant patterns
        if 'get_db_session' not in original_content:
            print(f"⏭️  Skipping {file_path.name} - no get_db_session found")
            return False
        
        # Apply transformations
        updated_content = original_content
        updated_content = update_imports(updated_content)
        updated_content = update_dependency_usage(updated_content)
        
        # Check if anything changed
        if updated_content == original_content:
            print(f"⏭️  No changes needed in {file_path.name}")
            return False
        
        # Write back the updated content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"✅ Updated {file_path.name}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating {file_path.name}: {e}")
        return False


def main():
    """Main migration function."""
    print("🚀 Starting migration to get_tenant_db_session...")
    
    # Find project root (assuming script is run from project root)
    project_root = os.getcwd()
    
    # Find all router files
    router_files = find_router_files(project_root)
    
    if not router_files:
        print("❌ No router files found. Make sure you're running from the project root.")
        return
    
    print(f"📁 Found {len(router_files)} router files")
    
    # Update each file
    updated_count = 0
    for router_file in router_files:
        if update_file(router_file):
            updated_count += 1
    
    print(f"\n🎉 Migration complete!")
    print(f"📊 Updated {updated_count} out of {len(router_files)} router files")
    
    if updated_count > 0:
        print("\n📝 Next steps:")
        print("1. Review the changes: git diff")
        print("2. Test the updated routes")
        print("3. Commit the changes: git add . && git commit -m 'refactor: migrate routes to get_tenant_db_session'")
    
    print(f"\n💡 Benefits after migration:")
    print("- ✅ Automatic PostgreSQL session variables for RLS policies")
    print("- ✅ Optimized database connection reuse")
    print("- ✅ Backward compatible with existing route logic")
    print("- ✅ Minimal code changes required")


if __name__ == "__main__":
    main()
