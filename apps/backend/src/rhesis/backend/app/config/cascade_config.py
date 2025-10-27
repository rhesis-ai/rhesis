"""
Cascade Configuration for Soft Delete and Restore Operations

This configuration defines parent-child relationships that should cascade
when performing soft delete or restore operations.

Adding a new cascade relationship:
1. Import the parent and child models
2. Add an entry to CASCADE_RELATIONSHIPS dictionary
3. Define the CascadeRelationship with the child model and foreign key

Example:
    models.Parent: [
        CascadeRelationship(
            child_model=models.Child,
            foreign_key='parent_id',
            cascade_delete=True,
            cascade_restore=True,
            description="Children belong to parent"
        )
    ]

The system will automatically handle cascading for all configured relationships
without requiring any code changes in CRUD or service layers.
"""

from dataclasses import dataclass
from typing import Dict, List, Type

from rhesis.backend.app import models


@dataclass
class CascadeRelationship:
    """
    Defines a parent-child cascade relationship for soft delete/restore operations.

    Attributes:
        child_model: The SQLAlchemy model class for the child entity
        foreign_key: The column name in the child table that references the parent
        cascade_delete: Whether to cascade soft deletions (default: True)
        cascade_restore: Whether to cascade restorations (default: True)
        description: Optional human-readable description of the relationship
    """

    child_model: Type
    foreign_key: str
    cascade_delete: bool = True
    cascade_restore: bool = True
    description: str = ""


# Global cascade configuration registry
# Maps parent model classes to their cascade relationships
CASCADE_RELATIONSHIPS: Dict[Type, List[CascadeRelationship]] = {
    # TestRun cascades to TestResult
    # When a test run is deleted/restored, all its test results are also deleted/restored
    models.TestRun: [
        CascadeRelationship(
            child_model=models.TestResult,
            foreign_key="test_run_id",
            cascade_delete=True,
            cascade_restore=True,
            description="Test results belong to a test run and should cascade with it",
        )
    ],
    # Add more cascade relationships here as needed:
    # models.Project: [
    #     CascadeRelationship(
    #         child_model=models.TestSet,
    #         foreign_key='project_id',
    #         cascade_delete=True,
    #         cascade_restore=True
    #     )
    # ],
}


def get_cascade_relationships(parent_model: Type) -> List[CascadeRelationship]:
    """
    Get all cascade relationships for a given parent model.

    Args:
        parent_model: The parent model class

    Returns:
        List of CascadeRelationship objects, or empty list if none configured
    """
    return CASCADE_RELATIONSHIPS.get(parent_model, [])
