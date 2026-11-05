"""
Renewals Router – /api/v1/renewals
Scoped to demo organization.
"""

from __future__ import annotations
import uuid
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.subscription import SubscriptionWithRisk
from app.services import renewal_service

router = APIRouter(prefix="/renewals", tags=["renewals"])


def get_demo_org() -> uuid.UUID:
    return uuid.UUID(settings.DEMO_ORG_ID)


@router.get("/upcoming", response_model=List[SubscriptionWithRisk])
def upcoming_renewals(
    days: int = 30,
    db: Session = Depends(get_db),
    org_id: uuid.UUID = Depends(get_demo_org),
):
    """Return subscriptions renewing within the next N days for the demo org."""
    return renewal_service.get_upcoming_renewals(db, days_ahead=days, org_id=org_id)


@router.get("/overdue", response_model=List[SubscriptionWithRisk])
def overdue_renewals(
    db: Session = Depends(get_db),
    org_id: uuid.UUID = Depends(get_demo_org),
):
    """Return active subscriptions whose renewal date has already passed for the demo org."""
    return renewal_service.get_overdue_renewals(db, org_id=org_id)
