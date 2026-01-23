"""
Pydantic schemas for Garak API endpoints.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GarakProbeClassResponse(BaseModel):
    """Response schema for a single Garak probe class."""

    class_name: str = Field(..., description="Probe class name (e.g., 'Dan_11_0')")
    full_name: str = Field(..., description="Full probe name (e.g., 'dan.Dan_11_0')")
    module_name: str = Field(..., description="Parent module name")
    description: str = Field(..., description="Probe description")
    prompt_count: int = Field(..., description="Number of prompts in this probe")
    tags: List[str] = Field(default_factory=list, description="Probe-specific tags")
    detector: Optional[str] = Field(None, description="Recommended detector for this probe")

    class Config:
        from_attributes = True


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
    probes: List[GarakProbeClassResponse] = Field(
        default_factory=list, description="Individual probe classes in this module"
    )

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
