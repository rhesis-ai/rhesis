"""Audit log streaming destinations.

- ``GET    /audit-destinations``             -- list, with each one's health
- ``POST   /audit-destinations``             -- add; a webhook's signing secret is returned once
- ``GET    /audit-destinations/{id}``        -- one
- ``PATCH  /audit-destinations/{id}``        -- pause or resume
- ``DELETE /audit-destinations/{id}``        -- remove
- ``POST   /audit-destinations/{id}/test``   -- send one sample event now

Gated on ``FeatureName.AUDIT_LOG`` (404 when unavailable) and ``audit_log:manage``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from rhesis.backend.app.auth.capabilities import Permission, capability
from rhesis.backend.app.auth.feature_gates import require_feature
from rhesis.backend.app.dependencies import get_tenant_context, get_tenant_db_session
from rhesis.backend.app.features import FeatureName
from rhesis.backend.ee.audit.streaming import crud, service
from rhesis.backend.ee.audit.streaming.models import AuditDestination
from rhesis.backend.ee.audit.streaming.schemas import (
    DestinationCreate,
    DestinationCreated,
    DestinationRead,
    DestinationUpdate,
    TestEventResult,
)

MANAGE = Permission.AuditLog.MANAGE

router = APIRouter(
    prefix="/audit-destinations",
    tags=["audit-log"],
    dependencies=[Depends(require_feature(FeatureName.AUDIT_LOG))],
    responses={404: {"description": "Not found"}},
)


def _get_or_404(db: Session, destination_id: UUID) -> AuditDestination:
    destination = crud.get_destination(db, destination_id)
    if destination is None:
        raise HTTPException(status_code=404, detail="Audit destination not found")
    return destination


@router.get("/", response_model=list[DestinationRead], **capability(MANAGE))
def list_destinations(db: Session = Depends(get_tenant_db_session)):
    return [service.to_read(d) for d in crud.list_destinations(db)]


@router.post(
    "/",
    response_model=DestinationCreated,
    status_code=status.HTTP_201_CREATED,
    **capability(MANAGE),
)
def create_destination(
    payload: DestinationCreate,
    db: Session = Depends(get_tenant_db_session),
    tenant_context=Depends(get_tenant_context),
):
    organization_id, _ = tenant_context
    try:
        return service.create_destination(db, organization_id, payload)
    except service.InvalidDestination as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{destination_id}", response_model=DestinationRead, **capability(MANAGE))
def read_destination(destination_id: UUID, db: Session = Depends(get_tenant_db_session)):
    return service.to_read(_get_or_404(db, destination_id))


@router.patch("/{destination_id}", response_model=DestinationRead, **capability(MANAGE))
def update_destination(
    destination_id: UUID,
    payload: DestinationUpdate,
    db: Session = Depends(get_tenant_db_session),
):
    destination = _get_or_404(db, destination_id)
    service.set_paused(destination, payload.paused)
    db.flush()
    return service.to_read(destination)


@router.delete("/{destination_id}", status_code=status.HTTP_204_NO_CONTENT, **capability(MANAGE))
def delete_destination(destination_id: UUID, db: Session = Depends(get_tenant_db_session)):
    crud.delete_destination(db, _get_or_404(db, destination_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{destination_id}/test", response_model=TestEventResult, **capability(MANAGE))
def send_test_event(destination_id: UUID, db: Session = Depends(get_tenant_db_session)):
    error = service.send_test_event(_get_or_404(db, destination_id))
    return TestEventResult(delivered=error is None, error=error)
