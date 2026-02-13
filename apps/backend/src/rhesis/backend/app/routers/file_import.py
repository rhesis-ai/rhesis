"""
File import API router.

Provides a multi-step flow for importing test sets from uploaded
files (JSON, JSONL, CSV, Excel).
"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import (
    get_tenant_context,
    get_tenant_db_session,
)
from rhesis.backend.app.models.user import User
from rhesis.backend.app.schemas.file_import import (
    AnalyzeResponse,
    ConfirmRequest,
    ParseRequest,
    ParseResponse,
    PreviewPage,
    RemapResponse,
)
from rhesis.backend.app.services.file_import import ImportService
from rhesis.backend.app.services.file_import.exceptions import FileImportError
from rhesis.backend.logging import logger

# Generic message for unexpected server errors (never expose internals)
IMPORT_ERROR_GENERIC = "Import failed. Please try again or contact support."

router = APIRouter(
    prefix="/import",
    tags=["import"],
    responses={404: {"description": "Not found"}},
)

# Maximum upload size: 10 MB
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Upload a file and analyze its structure.

    Detects format, extracts headers and sample rows, and suggests
    a column mapping.  Returns an ``import_id`` used for subsequent
    steps.
    """
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required",
        )

    file_bytes = await file.read()

    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File too large ({len(file_bytes)} bytes). "
                f"Maximum size is {MAX_UPLOAD_BYTES} bytes."
            ),
        )

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty",
        )

    try:
        result = ImportService.analyze(
            file_bytes=file_bytes,
            filename=file.filename,
            db=db,
            user=current_user,
            user_id=str(current_user.id),
            organization_id=str(current_user.organization_id or ""),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File encoding could not be read. Try saving as UTF-8.",
        )
    except ImportError as e:
        if "fastxlsx" in str(e):
            raise HTTPException(
                status_code=400,
                detail="Excel support is not available. Please use CSV or JSON.",
            )
        raise HTTPException(status_code=500, detail=IMPORT_ERROR_GENERIC)
    except FileImportError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error(f"File analyze failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=IMPORT_ERROR_GENERIC)


@router.post(
    "/{import_id}/parse",
    response_model=ParseResponse,
)
async def parse_file(
    import_id: str,
    request: ParseRequest,
    current_user: User = Depends(require_current_user_or_token),
):
    """Parse the uploaded file with the confirmed column mapping.

    Returns a validation summary and the first page of preview data.
    """
    try:
        result = ImportService.parse(
            import_id=import_id,
            mapping=request.mapping,
            test_type=request.test_type,
            user_id=str(current_user.id),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File encoding could not be read. Try saving as UTF-8.",
        )
    except FileImportError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error(
            f"File parse failed for {import_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=IMPORT_ERROR_GENERIC)


@router.get(
    "/{import_id}/preview",
    response_model=PreviewPage,
)
async def preview_data(
    import_id: str,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(50, ge=1, le=200, description="Rows per page"),
    current_user: User = Depends(require_current_user_or_token),
):
    """Get a page of parsed preview data with validation errors."""
    result = ImportService.preview(
        import_id=import_id,
        page=page,
        page_size=page_size,
        user_id=str(current_user.id),
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Import session not found: {import_id}",
        )
    return result


@router.post("/{import_id}/confirm")
async def confirm_import(
    import_id: str,
    request: ConfirmRequest,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
    current_user: User = Depends(require_current_user_or_token),
):
    """Create the test set from the parsed and validated data.

    Calls bulk_create_test_set internally.  Cleans up the import
    session on success.
    """
    organization_id, user_id = tenant_context

    try:
        test_set = ImportService.confirm(
            import_id=import_id,
            db=db,
            organization_id=str(organization_id),
            user_id=str(user_id),
            name=request.name or "",
            description=request.description or "",
            short_description=request.short_description or "",
        )
        return {
            "id": str(test_set.id),
            "name": test_set.name,
            "description": test_set.description,
            "short_description": test_set.short_description,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        errors = []
        for err in e.errors()[:5]:
            loc = " -> ".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", "Invalid value")
            errors.append(f"{loc}: {msg}")
        detail = {
            "message": "Some test data failed validation.",
            "errors": errors,
        }
        logger.warning(f"Import validation failed for {import_id}: {errors}")
        raise HTTPException(status_code=400, detail=detail)
    except FileImportError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error(
            f"Import confirm failed for {import_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=IMPORT_ERROR_GENERIC)


@router.delete("/{import_id}")
async def cancel_import(
    import_id: str,
    current_user: User = Depends(require_current_user_or_token),
):
    """Cancel and clean up an import session."""
    deleted = ImportService.cancel(import_id, user_id=str(current_user.id))
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Import session not found: {import_id}",
        )
    return {"status": "cancelled", "import_id": import_id}


@router.post(
    "/{import_id}/remap",
    response_model=RemapResponse,
)
async def remap_with_llm(
    import_id: str,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """Re-run column mapping using LLM assistance.

    If no LLM is available, returns the existing heuristic mapping
    with ``llm_available: false`` and a user-friendly message.
    """
    try:
        result = ImportService.remap_with_llm(
            import_id=import_id,
            db=db,
            user=current_user,
            user_id=str(current_user.id),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileImportError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error(
            f"LLM remap failed for {import_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=IMPORT_ERROR_GENERIC)
