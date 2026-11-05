"""
Analytics Service
=================
Spending overview, department rollup and top-subscription queries.
All normalisation uses pure Python arithmetic – no AI APIs.

Handles multi-currency responsibly:
- Primary MRR / ARR and department rollups are strictly calculated in INR.
- Non-INR currencies (USD, EUR, etc.) are calculated and displayed in an isolated breakdown.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import Subscription, SubscriptionStatus
from app.schemas.subscription import (
    DepartmentSpend,
    CurrencySpend,
    SpendingSummary,
    SubscriptionOut,
)


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _to_monthly(amount: Decimal, cycle: str) -> Decimal:
    c = cycle.lower()
    if c == "quarterly":
        return amount / Decimal("3")
    if c == "yearly":
        return amount / Decimal("12")
    return amount


def _to_annual(amount: Decimal, cycle: str) -> Decimal:
    c = cycle.lower()
    if c == "monthly":
        return amount * Decimal("12")
    if c == "quarterly":
        return amount * Decimal("4")
    return amount


# ---------------------------------------------------------------------------
# Analytics queries
# ---------------------------------------------------------------------------

def get_spending_summary(db: Session, org_id: Optional[uuid.UUID] = None) -> SpendingSummary:
    query = db.query(Subscription).filter(Subscription.status == SubscriptionStatus.ACTIVE)
    if org_id:
        query = query.filter(Subscription.org_id == org_id)

    active_subs = query.all()

    total_active = len(active_subs)
    inr_monthly_total = Decimal("0")
    inr_annual_total = Decimal("0")
    inr_count = 0

    dept_map: dict[str, dict] = {}
    other_cur_map: dict[str, dict] = {}

    for sub in active_subs:
        amount = Decimal(str(sub.amount))
        cycle = sub.billing_cycle.value if sub.billing_cycle else "Monthly"
        cur = (sub.currency or "INR").upper()

        m = _to_monthly(amount, cycle)
        a = _to_annual(amount, cycle)

        if cur == "INR":
            inr_count += 1
            inr_monthly_total += m
            inr_annual_total += a

            dept = sub.department or "Unassigned"
            if dept not in dept_map:
                dept_map[dept] = {"monthly": Decimal("0"), "annual": Decimal("0")}
            dept_map[dept]["monthly"] += m
            dept_map[dept]["annual"] += a
        else:
            if cur not in other_cur_map:
                other_cur_map[cur] = {
                    "count": 0,
                    "monthly": Decimal("0"),
                    "annual": Decimal("0"),
                }
            other_cur_map[cur]["count"] += 1
            other_cur_map[cur]["monthly"] += m
            other_cur_map[cur]["annual"] += a

    # Upcoming renewals in next 30 days (all currencies)
    today = date.today()
    cutoff_30 = today + timedelta(days=30)
    upcoming_30 = sum(
        1 for s in active_subs
        if today <= s.renewal_date <= cutoff_30
    )

    # Department breakdown (INR only)
    dept_breakdown = [
        DepartmentSpend(department=dept, monthly=vals["monthly"], annual=vals["annual"])
        for dept, vals in sorted(dept_map.items(), key=lambda x: x[1]["annual"], reverse=True)
    ]

    # Other currencies breakdown
    other_currencies = [
        CurrencySpend(
            currency=cur,
            count=vals["count"],
            monthly_recurring=vals["monthly"],
            annual_recurring=vals["annual"],
        )
        for cur, vals in sorted(other_cur_map.items())
    ]

    # Top 5 subscriptions by monthly cost (INR subscriptions prioritized, then by normalized value)
    inr_subs = [s for s in active_subs if (s.currency or "INR").upper() == "INR"]
    top_pool = inr_subs if inr_subs else active_subs
    top_subs = sorted(
        top_pool,
        key=lambda s: _to_monthly(Decimal(str(s.amount)), s.billing_cycle.value),
        reverse=True,
    )[:5]

    return SpendingSummary(
        currency="INR",
        total_active=total_active,
        inr_active_count=inr_count,
        monthly_recurring=inr_monthly_total,
        annual_recurring=inr_annual_total,
        upcoming_renewals_30d=upcoming_30,
        department_breakdown=dept_breakdown,
        top_subscriptions=[SubscriptionOut.model_validate(s) for s in top_subs],
        other_currencies=other_currencies,
    )
