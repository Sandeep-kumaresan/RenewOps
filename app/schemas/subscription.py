"""Pydantic schemas for Subscription CRUD and responses."""

from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.db.models import BillingCycle, SubscriptionStatus, RenewalDecision


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

class SubscriptionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    vendor: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="INR", max_length=10)
    billing_cycle: BillingCycle
    start_date: date
    renewal_date: date
    department: Optional[str] = Field(default=None, max_length=100)
    owner: Optional[str] = Field(default=None, max_length=255)
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    auto_renewal: bool = False
    renewal_decision: RenewalDecision = RenewalDecision.UNDECIDED
    notes: Optional[str] = None


class SubscriptionCreate(SubscriptionBase):
    org_id: Optional[UUID] = None  # defaults to demo org in service layer


class SubscriptionUpdate(BaseModel):
    """All fields optional for PATCH-style updates."""
    name: Optional[str] = Field(default=None, max_length=255)
    vendor: Optional[str] = Field(default=None, max_length=255)
    category: Optional[str] = Field(default=None, max_length=100)
    amount: Optional[Decimal] = Field(default=None, gt=0)
    currency: Optional[str] = Field(default=None, max_length=10)
    billing_cycle: Optional[BillingCycle] = None
    start_date: Optional[date] = None
    renewal_date: Optional[date] = None
    department: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[SubscriptionStatus] = None
    auto_renewal: Optional[bool] = None
    renewal_decision: Optional[RenewalDecision] = None
    notes: Optional[str] = None


class SubscriptionOut(SubscriptionBase):
    id: UUID
    org_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Risk Score
# ---------------------------------------------------------------------------

class RiskDetail(BaseModel):
    score: int
    category: str               # Low / Medium / High
    reasons: List[str]


class SubscriptionWithRisk(SubscriptionOut):
    risk: RiskDetail


# ---------------------------------------------------------------------------
# Renewal Log
# ---------------------------------------------------------------------------

class RenewalLogOut(BaseModel):
    id: UUID
    subscription_id: UUID
    old_decision: Optional[str]
    new_decision: str
    changed_by: Optional[str]
    changed_at: datetime
    notes: Optional[str]

    model_config = {"from_attributes": True}


class RenewalDecisionUpdate(BaseModel):
    decision: RenewalDecision
    changed_by: Optional[str] = "API"
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Spending Analytics
# ---------------------------------------------------------------------------

class DepartmentSpend(BaseModel):
    department: str
    monthly: Decimal
    annual: Decimal


class CurrencySpend(BaseModel):
    currency: str
    count: int
    monthly_recurring: Decimal
    annual_recurring: Decimal


class SpendingSummary(BaseModel):
    currency: str = "INR"
    total_active: int
    inr_active_count: int = 0
    monthly_recurring: Decimal   # strictly INR recurring spend
    annual_recurring: Decimal    # strictly INR recurring spend
    upcoming_renewals_30d: int
    department_breakdown: List[DepartmentSpend]
    top_subscriptions: List[SubscriptionOut]
    other_currencies: List[CurrencySpend] = []


# ---------------------------------------------------------------------------
# Generic list wrapper
# ---------------------------------------------------------------------------

class SubscriptionListResponse(BaseModel):
    total: int
    items: List[SubscriptionOut]

