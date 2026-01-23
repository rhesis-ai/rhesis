"""
Pydantic schemas for Garak API endpoints.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GarakProbeModuleResponse(BaseModel):
    """Response schema for a single Garak probe module."""

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

    class Config:
        from_attributes = True


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


class GarakImportRequest(BaseModel):
    """Request schema for importing Garak probes."""

    modules: List[str] = Field(
        ...,
        description="List of Garak module names to import",
        min_length=1,
    )
    test_set_name: str = Field(
        ...,
        description="Name for the new test set",
        min_length=1,
        max_length=255,
    )
    description: Optional[str] = Field(
        None,
        description="Optional description for the test set",
        max_length=2000,
    )


class GarakImportPreviewResponse(BaseModel):
    """Response schema for import preview."""

    garak_version: str = Field(..., description="Garak version")
    total_probes: int = Field(..., description="Total number of probe classes")
    total_prompts: int = Field(..., description="Total number of prompts")
    total_tests: int = Field(..., description="Number of tests that will be created")
    detector_count: int = Field(..., description="Number of unique detectors")
    detectors: List[str] = Field(..., description="List of detector class names")
    modules: List[Dict[str, Any]] = Field(..., description="Module-level breakdown")


class GarakImportResponse(BaseModel):
    """Response schema for successful import."""

    test_set_id: str = Field(..., description="ID of the created test set")
    test_set_name: str = Field(..., description="Name of the created test set")
    test_count: int = Field(..., description="Number of tests created")
    metric_count: int = Field(..., description="Number of metrics associated")
    garak_version: str = Field(..., description="Garak version used for import")
    modules: List[str] = Field(..., description="Modules that were imported")


class GarakSyncPreviewResponse(BaseModel):
    """Response schema for sync preview."""

    can_sync: bool = Field(..., description="Whether the test set can be synced")
    old_version: str = Field(..., description="Current Garak version in test set")
    new_version: str = Field(..., description="Latest Garak version")
    to_add: int = Field(..., description="Number of new tests to add")
    to_remove: int = Field(..., description="Number of tests to remove")
    unchanged: int = Field(..., description="Number of unchanged tests")
    modules: List[str] = Field(..., description="Modules in the test set")
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
