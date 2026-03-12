"""
Pydantic schemas for Garak API endpoints.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class GarakProbeClassResponse(BaseModel):
    """Response schema for a single Garak probe class."""

    model_config = ConfigDict(from_attributes=True)

    class_name: str = Field(..., description="Probe class name (e.g., 'Dan_11_0')")
    full_name: str = Field(..., description="Full probe name (e.g., 'dan.Dan_11_0')")
    module_name: str = Field(..., description="Parent module name")
    description: str = Field(..., description="Probe description")
    prompt_count: int = Field(..., description="Number of prompts in this probe")
    tags: List[str] = Field(default_factory=list, description="Probe-specific tags")
    detector: Optional[str] = Field(None, description="Recommended detector for this probe")
    is_dynamic: bool = Field(
        False,
        description=(
            "True when the probe has no static prompts and must be generated dynamically "
            "via LLM synthesis. Use POST /garak/generate to create a test set for these probes."
        ),
    )


class GarakProbeModuleResponse(BaseModel):
    """Response schema for a single Garak probe module."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Module name (e.g., 'dan', 'encoding')")
    description: str = Field(..., description="Module description")
    probe_count: int = Field(..., description="Number of probe classes in the module")
    total_prompt_count: int = Field(..., description="Total number of prompts across all probes")
    tags: List[str] = Field(default_factory=list, description="Tags associated with the module")
    default_detector: Optional[str] = Field(
        None, description="Default Garak detector for this module"
    )
    rhesis_category: str = Field(..., description="Mapped Rhesis category")
    rhesis_topic: str = Field(..., description="Mapped Rhesis topic")
    rhesis_behavior: str = Field(..., description="Mapped Rhesis behavior")
    has_dynamic_probes: bool = Field(
        False,
        description=(
            "True when at least one probe in this module must be generated dynamically. "
            "Use POST /garak/generate to create test sets for those probes."
        ),
    )
    probes: List[GarakProbeClassResponse] = Field(
        default_factory=list, description="Individual probe classes in this module"
    )


class GarakProbesListResponse(BaseModel):
    """Response schema for listing all available Garak probe modules."""

    garak_version: str = Field(..., description="Installed Garak version")
    modules: List[GarakProbeModuleResponse] = Field(
        ..., description="List of available probe modules"
    )
    total_modules: int = Field(..., description="Total number of modules")


class GarakProbeDetailResponse(BaseModel):
    """Response schema for detailed probe module information."""

    name: str = Field(..., description="Module name")
    description: str = Field(..., description="Module description")
    probe_classes: List[str] = Field(..., description="List of probe class names")
    probe_count: int = Field(..., description="Number of probe classes")
    total_prompt_count: int = Field(..., description="Total prompts across all probes")
    tags: List[str] = Field(default_factory=list, description="Module tags")
    default_detector: Optional[str] = Field(None, description="Default detector")
    rhesis_mapping: Dict[str, str] = Field(
        ..., description="Rhesis taxonomy mapping (category, topic, behavior)"
    )
    probes: List[Dict[str, Any]] = Field(..., description="List of probes with their details")


class GarakProbeSelection(BaseModel):
    """Schema for selecting a specific probe to import."""

    module_name: str = Field(..., description="Module name (e.g., 'dan')")
    class_name: str = Field(..., description="Probe class name (e.g., 'Dan_11_0')")
    custom_name: Optional[str] = Field(None, description="Optional custom name for the test set")


class GarakImportRequest(BaseModel):
    """Request schema for importing Garak probes."""

    probes: List[GarakProbeSelection] = Field(
        ...,
        description="List of probes to import (each becomes a test set)",
        min_length=1,
    )
    name_prefix: Optional[str] = Field(
        "Garak",
        description="Prefix for auto-generated test set names",
        max_length=50,
    )
    description_template: Optional[str] = Field(
        None,
        description="Optional description template for test sets",
        max_length=2000,
    )


class GarakProbePreview(BaseModel):
    """Preview for a single probe to import."""

    module_name: str = Field(..., description="Module name")
    class_name: str = Field(..., description="Probe class name")
    full_name: str = Field(..., description="Full probe name")
    test_set_name: str = Field(..., description="Name for the test set")
    prompt_count: int = Field(..., description="Number of prompts/tests")
    detector: Optional[str] = Field(None, description="Associated detector")


class GarakImportPreviewResponse(BaseModel):
    """Response schema for import preview."""

    garak_version: str = Field(..., description="Garak version")
    total_test_sets: int = Field(..., description="Number of test sets to create")
    total_tests: int = Field(..., description="Total number of tests to create")
    detector_count: int = Field(..., description="Number of unique detectors")
    detectors: List[str] = Field(..., description="List of detector class names")
    probes: List[GarakProbePreview] = Field(..., description="Probe-level breakdown")


class GarakImportedTestSet(BaseModel):
    """Response schema for a single imported test set."""

    test_set_id: str = Field(..., description="ID of the created test set")
    test_set_name: str = Field(..., description="Name of the created test set")
    probe_full_name: str = Field(..., description="Garak probe full name")
    test_count: int = Field(..., description="Number of tests created")


class GarakImportResponse(BaseModel):
    """Response schema for successful import."""

    test_sets: List[GarakImportedTestSet] = Field(..., description="List of created test sets")
    total_test_sets: int = Field(..., description="Number of test sets created")
    total_tests: int = Field(..., description="Total number of tests created")
    garak_version: str = Field(..., description="Garak version used for import")


class GarakSyncPreviewResponse(BaseModel):
    """Response schema for sync preview."""

    can_sync: bool = Field(..., description="Whether the test set can be synced")
    old_version: str = Field(..., description="Current Garak version in test set")
    new_version: str = Field(..., description="Latest Garak version")
    to_add: int = Field(..., description="Number of new tests to add")
    to_remove: int = Field(..., description="Number of tests to remove")
    unchanged: int = Field(..., description="Number of unchanged tests")
    probe_class: Optional[str] = Field(None, description="Probe class name")
    module_name: Optional[str] = Field(None, description="Module name")
    modules: Optional[List[str]] = Field(None, description="Modules (legacy format)")
    error: Optional[str] = Field(None, description="Error message if sync not possible")
    last_synced_at: Optional[str] = Field(None, description="Last sync timestamp")


class GarakSyncResponse(BaseModel):
    """Response schema for successful sync."""

    added: int = Field(..., description="Number of tests added")
    removed: int = Field(..., description="Number of tests removed")
    unchanged: int = Field(..., description="Number of unchanged tests")
    new_garak_version: str = Field(..., description="New Garak version")
    old_garak_version: str = Field(..., description="Previous Garak version")


class GarakErrorResponse(BaseModel):
    """Error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")


class GarakGenerateRequest(BaseModel):
    """
    Request schema for dynamically generating a test set from a dynamic garak probe.

    Dynamic probes have no static prompts — they generate them at runtime (e.g. via
    RL agents, NLTK, or external ML models). This endpoint synthesises semantically
    equivalent prompts using the user's configured LLM and saves the result as a
    Rhesis test set, preserving all garak metadata (goal, tags, OWASP references) so
    the test set is fully queryable by security standard.
    """

    module_name: str = Field(
        ...,
        description="Garak probe module name (e.g., 'fitd', 'atkgen', 'topic')",
    )
    class_name: str = Field(
        ...,
        description="Garak probe class name (e.g., 'FITD', 'Tox', 'WordNet')",
    )
    name: Optional[str] = Field(
        None,
        description=(
            "Custom name for the generated test set. Defaults to 'Garak Dynamic: <module>.<class>'."
        ),
    )
    num_tests: Optional[int] = Field(
        None,
        ge=1,
        le=500,
        description=(
            "Number of tests to generate. "
            "If omitted a random value between 100 and 200 is chosen automatically."
        ),
    )


class GarakGenerateResponse(BaseModel):
    """Response schema for a dynamic probe generation request."""

    task_id: str = Field(..., description="Celery task ID — use to poll for completion.")
    probe_full_name: str = Field(
        ..., description="Full probe identifier (e.g., 'fitd.FITD') for reference."
    )
    num_tests: int = Field(..., description="Number of tests that will be generated.")
    message: str = Field(
        ...,
        description="Human-readable status message.",
    )
