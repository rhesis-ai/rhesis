"""
Pydantic schemas for OWASP Top 10 test set generation API endpoints.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from rhesis.backend.app.constants import TestSetType


class OwaspFramework(str, Enum):
    """Which OWASP Top 10 report to generate attacks from."""

    LLM = "llm"
    AGENTIC = "agentic"


class OwaspCategory(BaseModel):
    """A single risk category (report section) within an OWASP Top 10 report."""

    id: str = Field(..., description="Normalised category id, e.g. 'llm01', 'asi06'")
    name: str = Field(..., description="Human-readable category name, e.g. 'Prompt Injection'")
    description: str = Field(
        default="",
        description="Short summary from the report's Description/Overview subsection",
    )


class OwaspCategoriesResponse(BaseModel):
    """Response schema for listing the risk categories of an OWASP report."""

    framework: OwaspFramework = Field(..., description="The OWASP report the categories belong to")
    report_url: str = Field(..., description="Source PDF URL for this report")
    categories: List[OwaspCategory] = Field(..., description="Risk categories found in the report")


class OwaspGenerateRequest(BaseModel):
    """
    Request schema for generating a test set from an OWASP Top 10 report.

    Downloads the selected OWASP report, and generates adversarial test cases
    tailored to the described system for each selected risk category via the
    user's configured LLM.
    """

    framework: OwaspFramework = Field(
        OwaspFramework.LLM,
        description="Which OWASP Top 10 report to generate attacks from",
    )
    purpose: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="What the system under test does, e.g. 'Customer service chatbot for a bank'",
    )
    categories: Optional[List[str]] = Field(
        None,
        description=(
            "Risk category ids to generate for, e.g. ['llm01', 'llm07']. "
            "Defaults to every category in the selected report."
        ),
    )
    num_tests: int = Field(
        20,
        ge=1,
        le=200,
        description="Total tests to generate, spread evenly across the selected categories",
    )
    name: Optional[str] = Field(
        None,
        max_length=100,
        description="Custom name for the generated test set",
    )
    batch_size: int = Field(
        10,
        ge=1,
        le=50,
        description="Max attacks generated per LLM call per category",
    )
    model_id: Optional[str] = Field(
        None,
        description="Optional model UUID to override the user's default generation model",
    )
    test_type: TestSetType = Field(
        TestSetType.SINGLE_TURN,
        description="'Single-Turn' (default) or 'Multi-Turn' conversational attacks.",
    )


class OwaspGenerateResponse(BaseModel):
    """Response schema for a successfully launched OWASP generation request."""

    task_id: str = Field(..., description="Celery task ID — use to poll for completion.")
    framework: OwaspFramework = Field(..., description="The OWASP report used for generation")
    num_tests: int = Field(..., description="Number of tests that will be generated")
    message: str = Field(..., description="Human-readable status message.")
