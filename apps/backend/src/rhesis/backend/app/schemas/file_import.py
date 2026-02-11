"""Pydantic schemas for the file import API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ── Analyze (Step 1) ─────────────────────────────────────────────


class FileInfo(BaseModel):
    """Metadata about the uploaded file."""

    filename: str
    format: str
    size_bytes: int


class AnalyzeResponse(BaseModel):
    """Response from POST /import/analyze."""

    import_id: str
    file_info: FileInfo
    headers: List[str]
    sample_rows: List[Dict[str, Any]]
    suggested_mapping: Dict[str, str]
    confidence: float = Field(ge=0.0, le=1.0)
    llm_available: bool = False


# ── Parse (Step 2) ───────────────────────────────────────────────


class ParseRequest(BaseModel):
    """Request body for POST /import/{import_id}/parse."""

    mapping: Dict[str, str] = Field(
        description=(
            "Column mapping from source header to target field. "
            "Example: {'Question': 'prompt_content', 'Cat': 'category'}"
        )
    )
    test_type: str = Field(
        default="Single-Turn",
        description=("The test type for the entire import. Must be 'Single-Turn' or 'Multi-Turn'."),
    )


class ValidationSummary(BaseModel):
    """Aggregate validation results."""

    total_rows: int
    valid_rows: int
    error_count: int
    warning_count: int
    error_types: Dict[str, int] = Field(default_factory=dict)


class PreviewRow(BaseModel):
    """A single row in the preview with its validation results."""

    index: int
    data: Dict[str, Any]
    errors: List[Dict[str, str]] = Field(default_factory=list)
    warnings: List[Dict[str, str]] = Field(default_factory=list)


class PreviewPage(BaseModel):
    """A page of preview rows."""

    rows: List[PreviewRow]
    page: int
    page_size: int
    total_rows: int
    total_pages: int


class ParseResponse(BaseModel):
    """Response from POST /import/{import_id}/parse."""

    total_rows: int
    validation_summary: ValidationSummary
    preview: PreviewPage


# ── Confirm (Step 3) ─────────────────────────────────────────────


class ConfirmRequest(BaseModel):
    """Request body for POST /import/{import_id}/confirm."""

    name: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None


# ── Re-map with LLM ─────────────────────────────────────────────


class RemapResponse(BaseModel):
    """Response from POST /import/{import_id}/remap."""

    mapping: Dict[str, str]
    confidence: float = Field(ge=0.0, le=1.0)
    llm_available: bool = True
    message: Optional[str] = None
