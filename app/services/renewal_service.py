"""
Renewal Service
===============
Upcoming renewal queries and decision workflow helpers.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import Subscription, SubscriptionStatus
from app.schemas.subscription import SubscriptionWithRisk
from app.services.subscription_service import _enrich_with_risk


def get_upcoming_renewals(
    db: Session,
    days_ahead: int = 30,
    org_id: Optional[uuid.UUID] = None,
) -> List[SubscriptionWithRisk]:
    """Return active subscriptions renewing within the next `days_ahead` days."""
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    query = db.query(Subscription).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.renewal_date >= today,
        Subscription.renewal_date <= cutoff,
    )
    if org_id:
        query = query.filter(Subscription.org_id == org_id)

    subs = query.order_by(Subscription.renewal_date.asc()).all()
    return [_enrich_with_risk(s) for s in subs]


def get_overdue_renewals(
    db: Session,
    org_id: Optional[uuid.UUID] = None,
) -> List[SubscriptionWithRisk]:
    """Return active subscriptions whose renewal date has already passed."""
    today = date.today()
    query = db.query(Subscription).filter(
        Subscription.status == SubscriptionStatus.ACTIVE,
        Subscription.renewal_date < today,
    )
    if org_id:
        query = query.filter(Subscription.org_id == org_id)

    subs = query.order_by(Subscription.renewal_date.asc()).all()
    return [_enrich_with_risk(s) for s in subs]
