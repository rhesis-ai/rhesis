"""Schemas for adaptive testing CRUD operations.

These schemas define the request/response models for the adaptive testing API,
which operates on test tree data within a TestSet.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# =============================================================================
# Test Node Schemas
# =============================================================================


class TestNodeBase(BaseModel):
    """Base schema for test node data."""

    topic: str = Field(default="", description="Hierarchical topic path (URL-encoded)")
    input: str = Field(default="", description="Test input/prompt")
    output: str = Field(default="", description="Expected or actual output")
    label: Literal["", "pass", "fail"] = Field(default="", description="Test label")
    labeler: str = Field(default="", description="Who labeled this test")
    to_eval: bool = Field(default=True, description="Whether to evaluate this test")
    model_score: float = Field(default=0.0, description="Score from model/metrics")


class TestNodeCreate(TestNodeBase):
    """Schema for creating a new test node."""

    pass


class TestNodeUpdate(BaseModel):
    """Schema for updating a test node. All fields are optional."""

    topic: Optional[str] = Field(None, description="New topic path")
    input: Optional[str] = Field(None, description="New input value")
    output: Optional[str] = Field(None, description="New output value")
    label: Optional[Literal["", "pass", "fail"]] = Field(None, description="New label")
    to_eval: Optional[bool] = Field(None, description="New to_eval value")
    model_score: Optional[float] = Field(None, description="New model score")


class TestNode(TestNodeBase):
    """Schema for test node response."""

    id: str = Field(..., description="Unique identifier for the test node")

    model_config = {"from_attributes": True}


# =============================================================================
# Topic Schemas
# =============================================================================


class TopicBase(BaseModel):
    """Base schema for topic data."""

    path: str = Field(..., description="Full hierarchical path (URL-encoded)")


class TopicCreate(BaseModel):
    """Schema for creating a new topic."""

    path: str = Field(..., description="Topic path to create")
    labeler: str = Field(default="user", description="Who created this topic")


class TopicUpdate(BaseModel):
    """Schema for updating a topic."""

    new_name: Optional[str] = Field(None, description="New name for the topic (rename)")
    new_path: Optional[str] = Field(None, description="New path for the topic (move)")


class TopicDelete(BaseModel):
    """Schema for topic deletion options."""

    move_tests_to_parent: bool = Field(
        default=True,
        description=(
            "If True, move tests to parent topic and lift subtopics. "
            "If False, delete everything under this topic."
        ),
    )


class Topic(BaseModel):
    """Schema for topic response."""

    path: str = Field(..., description="Full hierarchical path (URL-encoded)")
    name: str = Field(..., description="Leaf name of the topic")
    parent_path: Optional[str] = Field(None, description="Parent topic path")
    depth: int = Field(..., description="Depth in hierarchy (0 = root level)")
    display_name: str = Field(..., description="Human-readable name (decoded)")
    display_path: str = Field(..., description="Human-readable full path (decoded)")
    has_direct_tests: bool = Field(default=False, description="Whether topic has direct tests")
    has_subtopics: bool = Field(default=False, description="Whether topic has child topics")

    model_config = {"from_attributes": True}


# =============================================================================
# Bulk Operation Schemas
# =============================================================================


class TestNodeBulkCreate(BaseModel):
    """Schema for bulk creating test nodes."""

    tests: List[TestNodeCreate] = Field(..., description="List of tests to create")


class TestNodeBulkResponse(BaseModel):
    """Response for bulk test operations."""

    created: int = Field(..., description="Number of tests created")
    tests: List[TestNode] = Field(..., description="Created test nodes")


# =============================================================================
# Tree State Schemas
# =============================================================================


class TreeValidation(BaseModel):
    """Schema for tree validation results."""

    valid: bool = Field(..., description="Whether all topics have markers")
    missing_markers: List[str] = Field(
        default_factory=list, description="Topic paths missing markers"
    )
    topics_with_tests: List[str] = Field(
        default_factory=list, description="All topics that have tests"
    )
    topics_with_markers: List[str] = Field(
        default_factory=list, description="All topics that have markers"
    )


class TreeStats(BaseModel):
    """Schema for tree statistics."""

    total_tests: int = Field(..., description="Total number of tests")
    total_topics: int = Field(..., description="Total number of topics")
    tests_by_topic: dict = Field(default_factory=dict, description="Test count per topic")
