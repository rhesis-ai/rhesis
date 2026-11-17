import json
import logging

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sendgrid.helpers.eventwebhook import EventWebhookHeader

from rhesis.backend.app.dependencies import OffLoopSession, get_off_loop_db_session
from rhesis.backend.app.services.email_events import (
    record_bounces,
    signature_valid,
    webhook_public_key,
)

logger = logging.getLogger(__name__)

# Plain APIRouter: a signed public webhook is no resource a role can be granted.
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/sendgrid/events", include_in_schema=False)
async def sendgrid_events(request: Request, db: OffLoopSession = Depends(get_off_loop_db_session)):
    """Receive SendGrid's Event Webhook. Public, so every call must carry SendGrid's signature."""
    public_key = webhook_public_key()
    if public_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    payload = (await request.body()).decode("utf-8", errors="replace")
    signature = request.headers.get(EventWebhookHeader.SIGNATURE, "")
    timestamp = request.headers.get(EventWebhookHeader.TIMESTAMP, "")
    if (
        not signature
        or not timestamp
        or not signature_valid(public_key, payload, signature, timestamp)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        events = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    if not isinstance(events, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")

    await anyio.to_thread.run_sync(record_bounces, db, events)
    return {"success": True}
