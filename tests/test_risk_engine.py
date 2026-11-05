"""
Unit tests for the risk engine – no database required.
Run with: venv\Scripts\python -m pytest tests/ -v
"""

from datetime import date, timedelta
from decimal import Decimal
import pytest

from app.services.risk_engine import calculate_risk


TODAY = date.today()


def test_no_risk():
    score, cat, reasons = calculate_risk(
        renewal_date=TODAY + timedelta(days=90),
        owner="Alice",
        renewal_decision="Renew",
        auto_renewal=False,
        amount=Decimal("5000"),
        billing_cycle="Monthly",
    )
    assert score == 0
    assert cat == "Low"
    assert "No significant risk factors" in reasons[0]


def test_renewal_within_7_days():
    score, cat, reasons = calculate_risk(
        renewal_date=TODAY + timedelta(days=5),
        owner="Alice",
        renewal_decision="Renew",
        auto_renewal=False,
        amount=Decimal("5000"),
        billing_cycle="Monthly",
    )
    assert score >= 40
    assert cat in ("Medium", "High")
    assert any("critically urgent" in r for r in reasons)


def test_renewal_within_30_days():
    score, cat, reasons = calculate_risk(
        renewal_date=TODAY + timedelta(days=20),
        owner="Alice",
        renewal_decision="Renew",
        auto_renewal=False,
        amount=Decimal("5000"),
        billing_cycle="Monthly",
    )
    assert score >= 25
    assert any("30 days" in r for r in reasons)


def test_missing_owner():
    score, cat, reasons = calculate_risk(
        renewal_date=TODAY + timedelta(days=90),
        owner="",
        renewal_decision="Renew",
        auto_renewal=False,
        amount=Decimal("5000"),
        billing_cycle="Monthly",
    )
    assert score >= 20
    assert any("No subscription owner" in r for r in reasons)


def test_missing_decision():
    score, cat, reasons = calculate_risk(
        renewal_date=TODAY + timedelta(days=90),
        owner="Alice",
        renewal_decision="Undecided",
        auto_renewal=False,
        amount=Decimal("5000"),
        billing_cycle="Monthly",
    )
    assert score >= 15
    assert any("No renewal decision" in r for r in reasons)


def test_auto_renewal_no_decision():
    score, cat, reasons = calculate_risk(
        renewal_date=TODAY + timedelta(days=90),
        owner="Alice",
        renewal_decision="Undecided",
        auto_renewal=True,
        amount=Decimal("5000"),
        billing_cycle="Monthly",
    )
    # Should have both missing decision (+15) and auto-renewal risk (+10)
    assert score >= 25
    assert any("Auto-renewal is ON" in r for r in reasons)


def test_high_cost_tier1():
    score, cat, reasons = calculate_risk(
        renewal_date=TODAY + timedelta(days=90),
        owner="Alice",
        renewal_decision="Renew",
        auto_renewal=False,
        amount=Decimal("75000"),
        billing_cycle="Monthly",
    )
    assert score >= 15
    assert any("₹50,000" in r for r in reasons)


def test_high_cost_tier2():
    score, cat, reasons = calculate_risk(
        renewal_date=TODAY + timedelta(days=90),
        owner="Alice",
        renewal_decision="Renew",
        auto_renewal=False,
        amount=Decimal("150000"),
        billing_cycle="Monthly",
    )
    assert score >= 25
    assert any("₹100,000" in r for r in reasons)


def test_yearly_billing_normalised():
    """₹1,200,000/year = ₹100,000/month → triggers tier 2."""
    score, cat, reasons = calculate_risk(
        renewal_date=TODAY + timedelta(days=90),
        owner="Alice",
        renewal_decision="Renew",
        auto_renewal=False,
        amount=Decimal("1200000"),
        billing_cycle="Yearly",
    )
    assert score >= 25
    assert any("₹100,000" in r for r in reasons)


def test_score_capped_at_100():
    score, cat, reasons = calculate_risk(
        renewal_date=TODAY + timedelta(days=2),
        owner="",
        renewal_decision="Undecided",
        auto_renewal=True,
        amount=Decimal("500000"),
        billing_cycle="Monthly",
    )
    assert score == 100
    assert cat == "High"


def test_overdue_renewal():
    score, cat, reasons = calculate_risk(
        renewal_date=TODAY - timedelta(days=10),
        owner="Alice",
        renewal_decision="Renew",
        auto_renewal=False,
        amount=Decimal("5000"),
        billing_cycle="Monthly",
    )
    assert score >= 40
    assert any("already passed" in r for r in reasons)


def test_usd_currency_risk_threshold():
    # $800/mo exceeds USD tier 1 ($600)
    score, cat, reasons = calculate_risk(
        renewal_date=TODAY + timedelta(days=90),
        owner="Alice",
        renewal_decision="Renew",
        auto_renewal=False,
        amount=Decimal("800"),
        billing_cycle="Monthly",
        currency="USD",
    )
    assert score >= 15
    assert any("$600" in r for r in reasons)

    # $1500/mo exceeds USD tier 2 ($1200)
    score2, cat2, reasons2 = calculate_risk(
        renewal_date=TODAY + timedelta(days=90),
        owner="Alice",
        renewal_decision="Renew",
        auto_renewal=False,
        amount=Decimal("1500"),
        billing_cycle="Monthly",
        currency="USD",
    )
    assert score2 >= 25
    assert any("$1,200" in r for r in reasons2)
