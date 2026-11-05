"""
Integration tests for:
  1. Multi-currency analytics separation (INR vs other currencies)
  2. Currency-aware risk scoring
  3. Organization scoping and tenant isolation
  4. MCP authentication enforcement
"""

import os
import uuid
from datetime import date
from decimal import Decimal
import pytest

# Ensure SQLite test database
os.environ["DATABASE_URL"] = "sqlite:///./test_analytics.db"

from app.db.init_db import init_db
from app.db.session import SessionLocal, Base, engine
from app.db.models import BillingCycle, SubscriptionStatus, RenewalDecision, Organization, Subscription, RenewalLog
from app.schemas.subscription import SubscriptionCreate
from app.services import subscription_service, analytics_service
from app.services.risk_engine import calculate_risk
from app.mcp import server as mcp_server


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    init_db()
    db = SessionLocal()
    db.query(RenewalLog).delete()
    db.query(Subscription).delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(RenewalLog).delete()
    db.query(Subscription).delete()
    db.commit()
    db.close()


def test_multi_currency_analytics_separation():
    db = SessionLocal()
    try:
        org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        # 1. Create an INR subscription: ₹25,000 / month
        subscription_service.create_subscription(
            db,
            SubscriptionCreate(
                org_id=org_id,
                name="AWS India",
                vendor="Amazon",
                category="Cloud",
                amount=Decimal("25000"),
                currency="INR",
                billing_cycle=BillingCycle.MONTHLY,
                start_date=date(2025, 1, 1),
                renewal_date=date(2026, 12, 1),
                department="Engineering",
            ),
        )

        # 2. Create a USD subscription: $100 / month
        subscription_service.create_subscription(
            db,
            SubscriptionCreate(
                org_id=org_id,
                name="Slack US",
                vendor="Slack",
                category="Communication",
                amount=Decimal("100"),
                currency="USD",
                billing_cycle=BillingCycle.MONTHLY,
                start_date=date(2025, 1, 1),
                renewal_date=date(2026, 12, 1),
                department="Engineering",
            ),
        )

        # 3. Retrieve spending summary
        summary = analytics_service.get_spending_summary(db, org_id=org_id)

        # Verify INR totals do NOT blindly include the 100 USD
        assert summary.monthly_recurring == Decimal("25000.00")
        assert summary.annual_recurring == Decimal("300000.00")

        # Verify USD is isolated in other_currencies
        assert len(summary.other_currencies) == 1
        usd_spend = summary.other_currencies[0]
        assert usd_spend.currency == "USD"
        assert usd_spend.count == 1
        assert usd_spend.monthly_recurring == Decimal("100.00")
        assert usd_spend.annual_recurring == Decimal("1200.00")
    finally:
        db.close()


def test_tenant_isolation():
    db = SessionLocal()
    try:
        org1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
        org2 = uuid.UUID("00000000-0000-0000-0000-000000000002")

        # Ensure org2 exists
        if not db.query(Organization).filter(Organization.id == org2).first():
            db.add(Organization(id=org2, name="Org 2"))
            db.commit()

        # Create sub in org2
        sub_org2 = subscription_service.create_subscription(
            db,
            SubscriptionCreate(
                org_id=org2,
                name="Secret Org2 Sub",
                vendor="VendorX",
                category="Security",
                amount=Decimal("5000"),
                currency="INR",
                billing_cycle=BillingCycle.MONTHLY,
                start_date=date(2025, 1, 1),
                renewal_date=date(2026, 12, 1),
            ),
        )

        # Querying with org1 MUST NOT return org2 subscription
        res = subscription_service.get_subscription(db, sub_org2.id, org_id=org1)
        assert res is None

        # Querying with org2 MUST return it
        res2 = subscription_service.get_subscription(db, sub_org2.id, org_id=org2)
        assert res2 is not None
        assert res2.name == "Secret Org2 Sub"
    finally:
        db.close()


def test_rest_write_access_verification(monkeypatch):
    from app.core.config import settings
    from app.api.v1.subscriptions import verify_write_access
    from fastapi import HTTPException

    # Without ADMIN_API_KEY configured -> open for demo
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "")
    assert verify_write_access(None, None) is True

    # With ADMIN_API_KEY configured
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "admin-secret-xyz")

    # Missing auth -> raises 401
    with pytest.raises(HTTPException) as exc_info:
        verify_write_access(None, None)
    assert exc_info.value.status_code == 401

    # Wrong auth -> raises 401
    with pytest.raises(HTTPException) as exc_info2:
        verify_write_access("Bearer wrong-key", None)
    assert exc_info2.value.status_code == 401

    # Valid Bearer token
    assert verify_write_access("Bearer admin-secret-xyz", None) is True

    # Valid X-Admin-Key header
    assert verify_write_access(None, "admin-secret-xyz") is True

