#!/usr/bin/env python3
"""
Simple test to verify the project naming conflict fix.
This should be run in the same environment as the SDK integration tests.
"""

import time
import uuid
from rhesis.sdk.entities.project import Project

def _unique_name(prefix: str) -> str:
    """Generate a unique name for test entities to avoid naming conflicts."""
    return f"{prefix} {uuid.uuid4().hex[:8]} {int(time.time() * 1000)}"

def test_unique_project_creation():
    """Test that we can create projects with unique names without conflicts."""
    
    # Create first project
    name1 = _unique_name("Test Project")
    project1 = Project(name=name1, description="First test project")
    result1 = project1.push()
    print(f"Created project 1: {name1} with ID: {result1['id']}")
    
    # Create second project
    name2 = _unique_name("Test Project") 
    project2 = Project(name=name2, description="Second test project")
    result2 = project2.push()
    print(f"Created project 2: {name2} with ID: {result2['id']}")
    
    # Verify they have different names and IDs
    assert name1 != name2, "Project names should be unique"
    assert result1['id'] != result2['id'], "Project IDs should be unique"
    
    print("✅ Test passed: Projects created with unique names")
    
    # Clean up
    project1.delete()
    project2.delete()
    print("🧹 Cleaned up test projects")

if __name__ == "__main__":
    test_unique_project_creation()