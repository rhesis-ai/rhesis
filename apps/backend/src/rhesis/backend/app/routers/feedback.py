import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from rhesis.backend.notifications import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    feedback: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    rating: Optional[float] = None


class FeedbackResponse(BaseModel):
    success: bool
    message: str


@router.post("/", response_model=FeedbackResponse)
def submit_feedback(request_data: FeedbackRequest) -> FeedbackResponse:
    """
    Submit user feedback and send a notification email to the Rhesis team.

    This is a public endpoint — authentication is not required so that
    anonymous users can also submit feedback.
    """
    if not request_data.feedback.strip():
        return FeedbackResponse(success=False, message="Feedback content is required")

    success = email_service.send_feedback_email(
        user_name=request_data.user_name or "Anonymous User",
        user_email=request_data.user_email or "anonymous",
        feedback=request_data.feedback,
        rating=request_data.rating,
    )

    if success:
        logger.info(f"Feedback email sent from {request_data.user_email or 'anonymous'}")
        return FeedbackResponse(success=True, message="Feedback sent successfully")
    else:
        logger.warning("Failed to send feedback email (SMTP not configured or send error)")
        return FeedbackResponse(success=False, message="Failed to send feedback")
