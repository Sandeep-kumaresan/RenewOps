"""
Subscription Service
====================
Central business logic for subscription CRUD and risk enrichment.
Used by both the REST API layer and the MCP server.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Subscription, RenewalLog, RenewalDecision, SubscriptionStatus
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionOut,
    SubscriptionWithRisk,
    RiskDetail,
    RenewalDecisionUpdate,
    RenewalLogOut,
)
from app.services.risk_engine import calculate_risk


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _default_org_id() -> uuid.UUID:
    return uuid.UUID(settings.DEMO_ORG_ID)


def _enrich_with_risk(sub: Subscription) -> SubscriptionWithRisk:
    score, category, reasons = calculate_risk(
        renewal_date=sub.renewal_date,
        owner=sub.owner,
        renewal_decision=sub.renewal_decision.value if sub.renewal_decision else "Undecided",
        auto_renewal=sub.auto_renewal,
        amount=Decimal(str(sub.amount)),
        billing_cycle=sub.billing_cycle.value if sub.billing_cycle else "Monthly",
        currency=sub.currency or "INR",
    )
    base = SubscriptionOut.model_validate(sub)
    return SubscriptionWithRisk(**base.model_dump(), risk=RiskDetail(score=score, category=category, reasons=reasons))


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_subscription(db: Session, payload: SubscriptionCreate) -> SubscriptionWithRisk:
    org_id = payload.org_id or _default_org_id()
    sub = Subscription(
        org_id=org_id,
        name=payload.name,
        vendor=payload.vendor,
        category=payload.category,
        amount=payload.amount,
        currency=payload.currency,
        billing_cycle=payload.billing_cycle,
        start_date=payload.start_date,
        renewal_date=payload.renewal_date,
        department=payload.department,
        owner=payload.owner,
        status=payload.status,
        auto_renewal=payload.auto_renewal,
        renewal_decision=payload.renewal_decision,
        notes=payload.notes,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return _enrich_with_risk(sub)


def get_subscription(db: Session, sub_id: uuid.UUID, org_id: Optional[uuid.UUID] = None) -> Optional[SubscriptionWithRisk]:
    query = db.query(Subscription).filter(Subscription.id == sub_id)
    if org_id:
        query = query.filter(Subscription.org_id == org_id)
    sub = query.first()
    if not sub:
        return None
    return _enrich_with_risk(sub)


def list_subscriptions(
    db: Session,
    org_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[SubscriptionWithRisk]:
    query = db.query(Subscription)

    if org_id:
        query = query.filter(Subscription.org_id == org_id)
    if status:
        query = query.filter(Subscription.status == status)
    if department:
        query = query.filter(Subscription.department.ilike(f"%{department}%"))
    if search:
        query = query.filter(
            Subscription.name.ilike(f"%{search}%")
            | Subscription.vendor.ilike(f"%{search}%")
        )

    subs = query.order_by(Subscription.renewal_date.asc()).offset(skip).limit(limit).all()
    return [_enrich_with_risk(s) for s in subs]


def count_subscriptions(
    db: Session,
    org_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
) -> int:
    query = db.query(Subscription)
    if org_id:
        query = query.filter(Subscription.org_id == org_id)
    if status:
        query = query.filter(Subscription.status == status)
    return query.count()


def update_subscription(
    db: Session, sub_id: uuid.UUID, payload: SubscriptionUpdate, org_id: Optional[uuid.UUID] = None
) -> Optional[SubscriptionWithRisk]:
    query = db.query(Subscription).filter(Subscription.id == sub_id)
    if org_id:
        query = query.filter(Subscription.org_id == org_id)
    sub = query.first()
    if not sub:
        return None

    old_decision = sub.renewal_decision

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sub, field, value)

    # Log renewal decision change if it changed
    new_decision = update_data.get("renewal_decision")
    if new_decision and new_decision != old_decision:
        log = RenewalLog(
            subscription_id=sub.id,
            old_decision=old_decision.value if old_decision else None,
            new_decision=new_decision.value if hasattr(new_decision, "value") else str(new_decision),
            changed_by="API",
        )
        db.add(log)

    db.commit()
    db.refresh(sub)
    return _enrich_with_risk(sub)


def delete_subscription(db: Session, sub_id: uuid.UUID, org_id: Optional[uuid.UUID] = None) -> bool:
    query = db.query(Subscription).filter(Subscription.id == sub_id)
    if org_id:
        query = query.filter(Subscription.org_id == org_id)
    sub = query.first()
    if not sub:
        return False
    db.delete(sub)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Renewal decision
# ---------------------------------------------------------------------------

def update_renewal_decision(
    db: Session, sub_id: uuid.UUID, payload: RenewalDecisionUpdate
) -> Optional[SubscriptionWithRisk]:
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    if not sub:
        return None

    log = RenewalLog(
        subscription_id=sub.id,
        old_decision=sub.renewal_decision.value if sub.renewal_decision else None,
        new_decision=payload.decision.value,
        changed_by=payload.changed_by or "API",
        notes=payload.notes,
    )
    db.add(log)

    sub.renewal_decision = payload.decision
    db.commit()
    db.refresh(sub)
    return _enrich_with_risk(sub)


def get_renewal_logs(db: Session, sub_id: uuid.UUID) -> List[RenewalLogOut]:
    logs = (
        db.query(RenewalLog)
        .filter(RenewalLog.subscription_id == sub_id)
        .order_by(RenewalLog.changed_at.desc())
        .all()
    )
    return [RenewalLogOut.model_validate(l) for l in logs]

