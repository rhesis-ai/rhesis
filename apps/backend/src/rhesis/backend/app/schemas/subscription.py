from datetime import datetime
from typing import List, Optional

from pydantic import UUID4

from rhesis.backend.app.models import SubscriptionPlan
from rhesis.backend.app.schemas import Base, Tag


# Risk schemas
class SubscriptionBase(Base):
    name: str
    description: Optional[str] = None
    plan: Optional[SubscriptionPlan] = None
    start_date: datetime
    is_active: Optional[bool] = True
    end_date: Optional[datetime] = None
    user_id: UUID4
    organization_id: UUID4
    status_id: Optional[UUID4] = None
    tags: Optional[List[Tag]] = None


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionUpdate(SubscriptionBase):
    name: Optional[str] = None
    user_id: Optional[UUID4] = None
    organization_id: Optional[UUID4] = None
    start_date: Optional[datetime] = None
    is_active: Optional[bool] = None


class Subscription(SubscriptionBase):
    pass
