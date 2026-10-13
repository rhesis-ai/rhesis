"""Celery job for audit streaming, on beat via ``ee/celery_jobs.py``."""

from rhesis.backend.celery.core import app
from rhesis.backend.ee.audit.streaming.service import deliver_all


@app.task(ignore_result=True)
def deliver_audit_streams() -> None:
    deliver_all()
