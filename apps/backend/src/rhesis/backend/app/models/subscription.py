import enum

from sqlalchemy import ARRAY, Boolean, Column, Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationMixin, TagsMixin


class SubscriptionPlan(enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"


class Subscription(Base, TagsMixin, OrganizationMixin):
    __tablename__ = "subscription"

    name = Column(String, nullable=False)
    description = Column(Text)
    user_id = Column(ForeignKey("user.id"), nullable=False)  # Foreign key to users
    plan = Column(Enum(SubscriptionPlan), nullable=False, default=SubscriptionPlan.FREE)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # Null for ongoing subscriptions
    is_active = Column(Boolean, default=True)  # Tracks if subscription is currently active
    status_id = Column(GUID(), ForeignKey("status.id"))
    # Relationship back to the user
    user = relationship("User", back_populates="subscriptions")
    # Optional tag field (if using the TagsMixin)
    tags = Column(ARRAY(String), nullable=True)
    # Relationship to subscriptions
    status = relationship("Status", back_populates="subscriptions")
