"""
End-to-End Integration Test:
Claude → MCP Server → PostgreSQL/Database → Dashboard & REST API
"""

import json
import uuid
from decimal import Decimal
import pytest

from app.db.init_db import init_db
from app.db.session import SessionLocal, Base, engine
from app.db.models import Subscription, RenewalLog, RenewalDecision
from app.core.config import settings
from app.mcp import server as mcp_server
from app.api.v1.subscriptions import list_subscriptions, get_subscription
from app.api.v1.analytics import spending_summary
from app.api.v1.renewals import upcoming_renewals


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()
    yield


def test_claude_mcp_database_dashboard_flow():
    """
    Simulates the exact interaction:
    User asks Claude:
      'Add an AWS subscription costing ₹25,000 per month, renewing on December 1, 2026, under the Engineering department.'
    """
    # -----------------------------------------------------------------------
    # Step 1: Claude calls MCP tool: create_subscription
    # -----------------------------------------------------------------------
    create_res_json = mcp_server.create_subscription(
        name="AWS Production",
        vendor="Amazon Web Services",
        category="Cloud Infrastructure",
        amount=25000.0,
        billing_cycle="Monthly",
        start_date="2026-01-01",
        renewal_date="2026-12-01",
        currency="INR",
        department="Engineering",
        owner="Rahul Sharma",
        auto_renewal=True,
        renewal_decision="Undecided",
        notes="Created via Claude MCP tool",
    )

    create_data = json.loads(create_res_json)
    assert create_data["success"] is True, f"MCP tool failed: {create_data.get('error')}"
    created_sub = create_data["subscription"]
    sub_id = created_sub["id"]
    assert created_sub["name"] == "AWS Production"
    assert created_sub["amount"] == 25000.0
    assert created_sub["department"] == "Engineering"
    assert "risk" in created_sub
    assert created_sub["risk"]["score"] >= 0

    # -----------------------------------------------------------------------
    # Step 2: Verify PostgreSQL / Database record directly
    # -----------------------------------------------------------------------
    db = SessionLocal()
    try:
        db_sub = db.query(Subscription).filter(Subscription.id == uuid.UUID(sub_id)).first()
        assert db_sub is not None, "Subscription must be saved in database!"
        assert db_sub.name == "AWS Production"
        assert db_sub.vendor == "Amazon Web Services"
        assert db_sub.amount == Decimal("25000.00")
        assert db_sub.billing_cycle.value == "Monthly"
        assert db_sub.auto_renewal is True
        assert db_sub.renewal_decision.value == "Undecided"

        # -----------------------------------------------------------------------
        # Step 3: Verify Dashboard & REST API immediately reflect the record
        # -----------------------------------------------------------------------
        org_id = uuid.UUID(settings.DEMO_ORG_ID)

        # 3a. Subscriptions list
        list_res = list_subscriptions(db=db, org_id=org_id)
        matching = [s for s in list_res.items if str(s.id) == sub_id]
        assert len(matching) == 1, "New subscription must immediately appear in dashboard list!"
        assert matching[0].name == "AWS Production"
        assert matching[0].department == "Engineering"

        # 3b. Spending analytics
        analytics_res = spending_summary(db=db, org_id=org_id)
        assert analytics_res.monthly_recurring >= Decimal("25000.00")
        assert analytics_res.annual_recurring >= Decimal("300000.00")
        eng_dept = [d for d in analytics_res.department_breakdown if d.department == "Engineering"]
        assert len(eng_dept) == 1
        assert eng_dept[0].monthly >= Decimal("25000.00")

        # 3c. Upcoming renewals
        renew_res = upcoming_renewals(days=60, db=db, org_id=org_id)
        assert any(str(r.id) == sub_id for r in renew_res)

        # -----------------------------------------------------------------------
        # Step 4: Claude retrieves subscriptions via MCP
        # -----------------------------------------------------------------------
        list_mcp = json.loads(mcp_server.list_subscriptions(department="Engineering"))
        assert any(s["id"] == sub_id for s in list_mcp["subscriptions"])

        get_mcp = json.loads(mcp_server.get_subscription(subscription_id=sub_id))
        assert get_mcp["success"] is True
        assert get_mcp["subscription"]["name"] == "AWS Production"
        assert get_mcp["subscription"]["risk"]["category"] in ("Low", "Medium", "High")

        # -----------------------------------------------------------------------
        # Step 5: Claude updates renewal decision via MCP update_subscription
        # -----------------------------------------------------------------------
        update_mcp = json.loads(
            mcp_server.update_subscription(
                subscription_id=sub_id,
                renewal_decision="Renew",
                notes="Approved by engineering lead",
            )
        )
        assert update_mcp["success"] is True
        assert update_mcp["subscription"]["renewal_decision"] == "Renew"

        # -----------------------------------------------------------------------
        # Step 6: Verify decision history audit log in database
        # -----------------------------------------------------------------------
        logs = db.query(RenewalLog).filter(RenewalLog.subscription_id == uuid.UUID(sub_id)).all()
        assert len(logs) >= 1, "Renewal decision change must be logged in renewal_logs!"
        assert logs[-1].new_decision == "Renew"

        # -----------------------------------------------------------------------
        # Step 7: Verify updated status appears on the Dashboard API
        # -----------------------------------------------------------------------
        db.expire_all()
        sub_updated = get_subscription(sub_id=uuid.UUID(sub_id), db=db, org_id=org_id)
        assert sub_updated.renewal_decision.value == "Renew"

        # -----------------------------------------------------------------------
        # Step 8: Reverse Flow - User edits via Dashboard / REST API
        # -----------------------------------------------------------------------
        from app.schemas.subscription import SubscriptionUpdate
        from app.api.v1.subscriptions import update_subscription as api_update_subscription

        dashboard_patch = SubscriptionUpdate(
            amount=Decimal("35000.00"),
            owner="Priya Nair",
            renewal_decision=RenewalDecision.UNDER_REVIEW,
            notes="Amount updated during quarterly budget review on dashboard",
        )
        api_res = api_update_subscription(
            sub_id=uuid.UUID(sub_id),
            payload=dashboard_patch,
            db=db,
            org_id=org_id,
        )
        assert api_res.amount == Decimal("35000.00")
        assert api_res.owner == "Priya Nair"
        assert api_res.renewal_decision.value == "Under Review"

        # -----------------------------------------------------------------------
        # Step 9: Verify Claude can retrieve the newly edited data via MCP
        # -----------------------------------------------------------------------
        get_after_dashboard_edit = json.loads(mcp_server.get_subscription(subscription_id=sub_id))
        assert get_after_dashboard_edit["success"] is True
        edited_sub = get_after_dashboard_edit["subscription"]
        assert edited_sub["amount"] == 35000.0, "Claude must retrieve updated amount edited on dashboard!"
        assert edited_sub["owner"] == "Priya Nair", "Claude must retrieve updated owner edited on dashboard!"
        assert edited_sub["renewal_decision"] == "Under Review", "Claude must retrieve updated decision!"
    finally:
        db.close()
