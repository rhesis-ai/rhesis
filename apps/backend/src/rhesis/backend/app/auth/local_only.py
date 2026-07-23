"""Dependency that restricts an endpoint to local (non-production) deployments."""

from fastapi import HTTPException, status

from rhesis.backend.app.config.settings import get_application_settings


def require_local_deployment() -> None:
    """Refuse the request on production / Google Cloud deployments.

    Raises 404 (rather than 403) so the endpoint's existence is not advertised in
    production, mirroring the no-enumeration convention of ``require_feature``.
    """
    settings = get_application_settings()
    if (
        settings.is_production
        or settings.is_google_cloud
        or settings.gcp_project
        or settings.google_cloud_project
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
