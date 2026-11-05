"""
Subscriptions Router – /api/v1/subscriptions
Protected with:
  - Strict tenant / organization isolation (scoped to demo organization)
  - Optional write-protection via ADMIN_API_KEY if configured in settings
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionWithRisk,
    SubscriptionListResponse,
    RenewalDecisionUpdate,
    RenewalLogOut,
)
from app.services import subscription_service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def get_demo_org() -> uuid.UUID:
    """Dependency: enforce all REST database queries stay strictly in demo org."""
    return uuid.UUID(settings.DEMO_ORG_ID)


def verify_write_access(
    authorization: Optional[str] = Header(default=None),
    x_admin_key: Optional[str] = Header(default=None),
) -> bool:
    """Dependency: protect write operations if ADMIN_API_KEY is configured."""
    expected = getattr(settings, "ADMIN_API_KEY", "").strip()
    if not expected:
        return True  # Open demo mode with strict org isolation
    token = (authorization or "").replace("Bearer ", "").strip() or (x_admin_key or "").strip()
    if token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid admin token required for write operations",
        )
    return True


@router.post(
    "",
    response_model=SubscriptionWithRisk,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_write_access)],
)
def create_subscription(
    payload: SubscriptionCreate,
    db: Session = Depends(get_db),
    org_id: uuid.UUID = Depends(get_demo_org),
):
    # Enforce organization bounding
    payload.org_id = org_id
    return subscription_service.create_subscription(db, payload)


@router.get("", response_model=SubscriptionListResponse)
def list_subscriptions(
    status: Optional[str] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    org_id: uuid.UUID = Depends(get_demo_org),
):
    items = subscription_service.list_subscriptions(
        db,
        org_id=org_id,
        status=status,
        department=department,
        search=search,
        skip=skip,
        limit=limit,
    )
    total = subscription_service.count_subscriptions(db, org_id=org_id, status=status)
    return SubscriptionListResponse(total=total, items=items)


@router.get("/{sub_id}", response_model=SubscriptionWithRisk)
def get_subscription(
    sub_id: uuid.UUID,
    db: Session = Depends(get_db),
    org_id: uuid.UUID = Depends(get_demo_org),
):
    result = subscription_service.get_subscription(db, sub_id, org_id=org_id)
    if not result:
        raise HTTPException(status_code=404, detail="Subscription not found or access denied")
    return result


@router.patch(
    "/{sub_id}",
    response_model=SubscriptionWithRisk,
    dependencies=[Depends(verify_write_access)],
)
def update_subscription(
    sub_id: uuid.UUID,
    payload: SubscriptionUpdate,
    db: Session = Depends(get_db),
    org_id: uuid.UUID = Depends(get_demo_org),
):
    result = subscription_service.update_subscription(db, sub_id, payload, org_id=org_id)
    if not result:
        raise HTTPException(status_code=404, detail="Subscription not found or access denied")
    return result


@router.delete(
    "/{sub_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_write_access)],
)
def delete_subscription(
    sub_id: uuid.UUID,
    db: Session = Depends(get_db),
    org_id: uuid.UUID = Depends(get_demo_org),
):
    deleted = subscription_service.delete_subscription(db, sub_id, org_id=org_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Subscription not found or access denied")


@router.patch(
    "/{sub_id}/decision",
    response_model=SubscriptionWithRisk,
    dependencies=[Depends(verify_write_access)],
)
def update_renewal_decision(
    sub_id: uuid.UUID,
    payload: RenewalDecisionUpdate,
    db: Session = Depends(get_db),
    org_id: uuid.UUID = Depends(get_demo_org),
):
    # Verify sub belongs to org before updating decision
    existing = subscription_service.get_subscription(db, sub_id, org_id=org_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Subscription not found or access denied")
    return subscription_service.update_renewal_decision(db, sub_id, payload)


@router.get("/{sub_id}/logs", response_model=List[RenewalLogOut])
def get_renewal_logs(
    sub_id: uuid.UUID,
    db: Session = Depends(get_db),
    org_id: uuid.UUID = Depends(get_demo_org),
):
    # Verify sub belongs to org before returning logs
    existing = subscription_service.get_subscription(db, sub_id, org_id=org_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Subscription not found or access denied")
    return subscription_service.get_renewal_logs(db, sub_id)
