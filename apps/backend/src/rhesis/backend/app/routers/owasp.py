"""
OWASP Top 10 test set generation API router.

Provides endpoints for listing the risk categories of an OWASP Top 10 report
and launching an async LLM-driven generation task that produces a Rhesis test
set of adversarial prompts for a described system under test.
"""

import logging

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.dependencies import get_tenant_db_session
from rhesis.backend.app.models.user import User
from rhesis.backend.app.routers.base import RhesisRouter
from rhesis.backend.app.schemas.owasp import (
    OwaspCategoriesResponse,
    OwaspCategory,
    OwaspFramework,
    OwaspGenerateRequest,
    OwaspGenerateResponse,
)
from rhesis.backend.app.services.owasp import OWASP_FRAMEWORKS, list_category_summaries
from rhesis.backend.tasks import task_launcher
from rhesis.backend.tasks.test_set import generate_and_save_owasp_test_set

logger = logging.getLogger(__name__)

router = RhesisRouter(
    prefix="/owasp",
    tags=["owasp"],
    responses={404: {"description": "Not found"}},
    resource="owasp",
)


@router.get("/categories", response_model=OwaspCategoriesResponse)
async def get_categories(
    framework: OwaspFramework = OwaspFramework.LLM,
    db: Session = Depends(get_tenant_db_session),
    current_user: User = Depends(require_current_user_or_token),
):
    """
    List the risk categories (report sections) for an OWASP Top 10 report.

    Downloads and parses the official OWASP PDF on first request per
    framework, then serves from cache.
    """
    try:
        summaries = list_category_summaries(framework.value)

        return OwaspCategoriesResponse(
            framework=framework,
            report_url=OWASP_FRAMEWORKS[framework.value]["report_url"],
            categories=[
                OwaspCategory(
                    id=s["id"],
                    name=s["name"],
                    description=s.get("description", ""),
                )
                for s in summaries
            ],
        )
    except Exception as e:
        logger.error(f"Error listing OWASP categories for {framework.value}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to load OWASP report categories: {str(e)}",
        )


@router.post("/generate", response_model=OwaspGenerateResponse, status_code=202)
async def generate_test_set(
    request: OwaspGenerateRequest,
    current_user: User = Depends(require_current_user_or_token),
    db: Session = Depends(get_tenant_db_session),
):
    """
    Generate a test set of adversarial prompts from an OWASP Top 10 report.

    Launches an async task that downloads the selected report, generates
    attack prompts tailored to the described system for each selected risk
    category via the user's configured LLM, and saves the result as a Rhesis
    test set.

    Returns HTTP 202 Accepted with a `task_id` that can be polled via
    `GET /tasks/{task_id}`.
    """
    try:
        task_result = task_launcher(
            generate_and_save_owasp_test_set,
            current_user=current_user,
            db=db,
            framework=request.framework.value,
            purpose=request.purpose,
            categories=request.categories,
            num_tests=request.num_tests,
            batch_size=request.batch_size,
            name=request.name,
            model_id=request.model_id,
            test_type=request.test_type.value,
        )

        logger.info(
            "OWASP generation task launched",
            extra={
                "task_id": task_result.id,
                "framework": request.framework.value,
                "num_tests": request.num_tests,
                "user_id": current_user.id,
                "organization_id": current_user.organization_id,
            },
        )

        framework_label = OWASP_FRAMEWORKS[request.framework.value]["label"]
        return OwaspGenerateResponse(
            task_id=str(task_result.id),
            framework=request.framework,
            num_tests=request.num_tests,
            message=(
                f"Test set generation started from the {framework_label} report. "
                f"Generating {request.num_tests} tests using your configured LLM."
            ),
        )

    except Exception as e:
        logger.error(f"Error launching OWASP generation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to launch OWASP test set generation: {str(e)}",
        )
