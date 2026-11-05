"""
Renewal Risk Score Engine
=========================
Pure Python rule-based calculation – no ML, no AI APIs.

Business Note on Thresholds:
  The cost thresholds below (e.g. ₹50,000 / ₹100,000 for INR, $600 / $1,200 for USD)
  are configurable organizational budget guardrails and governance policy rules,
  not market-derived statistical benchmarks. In an enterprise deployment, these
  thresholds can be customized per department or organization tiers.

Score range: 0–100
Category:
  0–30   → Low
  31–60  → Medium
  61–100 → High
"""

from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import List, Tuple, Optional

# Cost thresholds per currency: (Tier 1 +15 pts, Tier 2 +25 pts, symbol)
CURRENCY_THRESHOLDS: dict[str, tuple[Decimal, Decimal, str]] = {
    "INR": (Decimal("50000"), Decimal("100000"), "₹"),
    "USD": (Decimal("600"), Decimal("1200"), "$"),
    "EUR": (Decimal("550"), Decimal("1100"), "€"),
    "GBP": (Decimal("480"), Decimal("960"), "£"),
}

DEFAULT_THRESHOLD = (Decimal("600"), Decimal("1200"), "")


def _days_until_renewal(renewal_date: date) -> int:
    today = date.today()
    return (renewal_date - today).days


def _monthly_equivalent(amount: Decimal, billing_cycle: str) -> Decimal:
    """Normalise any billing cycle to a monthly figure."""
    cycle = billing_cycle.lower()
    if cycle == "quarterly":
        return amount / Decimal("3")
    if cycle == "yearly":
        return amount / Decimal("12")
    return amount   # monthly


def calculate_risk(
    renewal_date: date,
    owner: Optional[str],
    renewal_decision: str,
    auto_renewal: bool,
    amount: Decimal,
    billing_cycle: str,
    currency: str = "INR",
) -> Tuple[int, str, List[str]]:
    """
    Calculate the renewal risk score for a subscription.

    Returns:
        (score: int, category: str, reasons: list[str])
    """
    score = 0
    reasons: List[str] = []

    # 1. Renewal timeline risk
    days = _days_until_renewal(renewal_date)
    if days < 0:
        score += 40
        reasons.append(f"Renewal date has already passed ({abs(days)} days ago)")
    elif days <= 7:
        score += 40
        reasons.append(f"Renewal is in {days} day(s) – critically urgent")
    elif days <= 30:
        score += 25
        reasons.append(f"Renewal is in {days} days – approaching within 30 days")
    elif days <= 60:
        score += 10
        reasons.append(f"Renewal is in {days} days – approaching within 60 days")

    # 2. Missing owner
    if not owner or owner.strip() == "":
        score += 20
        reasons.append("No subscription owner assigned")

    # 3. Missing or undecided renewal decision
    if renewal_decision in ("Undecided", "", None):
        score += 15
        reasons.append("No renewal decision has been set")

    # 4. Auto-renewal risk (enabled without a clear decision)
    if auto_renewal and renewal_decision in ("Undecided", "", None):
        score += 10
        reasons.append("Auto-renewal is ON but renewal decision is undecided")

    # 5. Currency-aware high cost evaluation
    cur_upper = (currency or "INR").upper()
    t1, t2, sym = CURRENCY_THRESHOLDS.get(cur_upper, DEFAULT_THRESHOLD)
    monthly = _monthly_equivalent(amount, billing_cycle)

    if monthly >= t2:
        score += 25
        reasons.append(
            f"Very high monthly cost ({sym}{monthly:,.0f} {cur_upper}) – above {sym}{t2:,.0f} threshold"
        )
    elif monthly >= t1:
        score += 15
        reasons.append(
            f"High monthly cost ({sym}{monthly:,.0f} {cur_upper}) – above {sym}{t1:,.0f} threshold"
        )

    # Clamp to 100
    score = min(score, 100)

    # Category
    if score <= 30:
        category = "Low"
    elif score <= 60:
        category = "Medium"
    else:
        category = "High"

    if not reasons:
        reasons.append("No significant risk factors detected")

    return score, category, reasons
