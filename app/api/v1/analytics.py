"""
Analytics Router – /api/v1/analytics
Scoped to demo organization.
"""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.subscription import SpendingSummary
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_demo_org() -> uuid.UUID:
    return uuid.UUID(settings.DEMO_ORG_ID)


@router.get("/spending", response_model=SpendingSummary)
def spending_summary(
    db: Session = Depends(get_db),
    org_id: uuid.UUID = Depends(get_demo_org),
):
    """Full spending overview scoped strictly to the authorized demo organization."""
    return analytics_service.get_spending_summary(db, org_id=org_id)
