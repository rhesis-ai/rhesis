from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.user_utils import require_current_user_or_token
from rhesis.backend.app.database import get_db
from rhesis.backend.app.services.kpi_service import KPIService

router = APIRouter(prefix="/kpi", tags=["kpi"])


@router.get("/platform-metrics")
async def get_platform_metrics(
    db: Session = Depends(get_db),
    current_user=Depends(require_current_user_or_token),
) -> Dict[str, Any]:
    """
    Get platform-wide KPIs for internal observability dashboard.

    REQUIRES SUPERUSER ACCESS - Platform-wide metrics are sensitive data.

    Returns key metrics across ALL organizations including:
    - Total active users (platform-wide)
    - Active users who signed in (last 30 days, platform-wide)
    - Total tests created (platform-wide)
    - Total test runs (platform-wide)
    - Test runs by status (platform-wide)
    - Test runs timeline (last 6 months, platform-wide)
    - Test results pass/fail rates (platform-wide)

    This endpoint is designed for internal platform monitoring
    and can be consumed by Google Looker Studio or other visualization tools.
    """
    # Check if user is superuser
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Platform KPIs require superuser privileges.",
        )

    try:
        kpi_service = KPIService(db)
        return kpi_service.get_platform_metrics()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database error occurred while fetching platform metrics",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while fetching platform metrics",
        )
