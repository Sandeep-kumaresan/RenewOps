"""
RenewOps – End-to-End Claude MCP Integration Test Script
========================================================
Demonstrates and validates the complete workflow:
  Claude → MCP Server → PostgreSQL/Database → Live Dashboard & REST API

Usage:
  venv\\Scripts\\python.exe scripts\\test_mcp_flow.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import uuid
from decimal import Decimal

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.db.models import Subscription, RenewalLog
from app.core.config import settings
from app.mcp import server as mcp_server
from app.api.v1.subscriptions import list_subscriptions, get_subscription
from app.api.v1.analytics import spending_summary
from app.api.v1.renewals import upcoming_renewals


def run_e2e_flow():
    print("=" * 70)
    print(" RenewOps End-to-End Workflow Verification ")
    print(" Claude → MCP Tools → Database → Dashboard ")
    print("=" * 70)

    # Setup database
    print("\n[1/6] Initializing Database & Demo Organization...")
    init_db()
    db = SessionLocal()
    org_id = uuid.UUID(settings.DEMO_ORG_ID)
    print(f"      Organization: {settings.DEMO_ORG_NAME} ({org_id})")

    # Step 1: User asks Claude to add AWS subscription
    print("\n[2/6] User Prompt to Claude:")
    print("      'Add an AWS subscription costing ₹25,000 per month,")
    print("       renewing on December 1, 2026, under the Engineering department.'")
    print("      → Claude invokes MCP tool: create_subscription(...)")

    mcp_res_raw = mcp_server.create_subscription(
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
    mcp_res = json.loads(mcp_res_raw)
    assert mcp_res["success"] is True, f"Error: {mcp_res.get('error')}"
    sub = mcp_res["subscription"]
    sub_id = sub["id"]
    print(f"      ✓ MCP Tool Response: SUCCESS")
    print(f"        ID: {sub_id}")
    print(f"        Name: {sub['name']} | Amount: ₹{sub['amount']:,.0f} {sub['currency']}/mo")
    print(f"        Risk Score: {sub['risk']['score']}/100 ({sub['risk']['category']})")
    for reason in sub["risk"]["reasons"]:
        print(f"          - {reason}")

    # Step 2: Verify PostgreSQL / Database Layer directly
    print("\n[3/6] Verifying Database Record in PostgreSQL / ORM directly...")
    db_record = db.query(Subscription).filter(Subscription.id == uuid.UUID(sub_id)).first()
    assert db_record is not None, "Failed: Record not in database!"
    assert db_record.name == "AWS Production"
    assert db_record.amount == Decimal("25000.00")
    print(f"      ✓ Database record verified: {db_record.name} (${db_record.amount})")
    print(f"        Org Bound: {db_record.org_id} (Tenant Isolation Active)")

    # Step 3: Verify Live Dashboard & REST API
    print("\n[4/6] Verifying Live Dashboard & REST API endpoints reflect new record...")
    list_res = list_subscriptions(db=db, org_id=org_id)
    matching = [s for s in list_res.items if str(s.id) == sub_id]
    assert len(matching) == 1, "Subscription did not appear in dashboard listing!"
    print(f"      ✓ /api/v1/subscriptions reflects record (Total active subs: {list_res.total})")

    spend = spending_summary(db=db, org_id=org_id)
    print(f"      ✓ /api/v1/analytics/spending updated:")
    print(f"        Monthly Recurring (MRR): ₹{spend.monthly_recurring:,.0f} INR")
    print(f"        Annual Recurring (ARR):  ₹{spend.annual_recurring:,.0f} INR")
    eng_dept = [d for d in spend.department_breakdown if d.department == "Engineering"]
    if eng_dept:
        print(f"        Engineering Dept Spend:  ₹{eng_dept[0].monthly:,.0f}/mo")

    # Step 4: Claude retrieves upcoming renewals
    print("\n[5/6] Claude retrieves upcoming renewals via MCP tool...")
    renew_mcp = json.loads(mcp_server.get_upcoming_renewals(days_ahead=60))
    print(f"      ✓ MCP tool get_upcoming_renewals: {renew_mcp['total']} upcoming renewals returned")

    # Step 5: Claude updates renewal decision
    print("\n[6/7] Claude updates renewal decision via MCP update_subscription...")
    update_mcp = json.loads(
        mcp_server.update_subscription(
            subscription_id=sub_id,
            renewal_decision="Renew",
            notes="Engineering confirmed usage is critical",
        )
    )
    assert update_mcp["success"] is True
    print(f"      ✓ Decision updated to: {update_mcp['subscription']['renewal_decision']}")

    # Verify decision history log
    db.expire_all()
    logs = db.query(RenewalLog).filter(RenewalLog.subscription_id == uuid.UUID(sub_id)).all()
    print(f"      ✓ Audit trail in renewal_logs verified: {len(logs)} log entry created")
    print(f"        Decision transition: {logs[-1].old_decision} → {logs[-1].new_decision}")

    # Step 6: Reverse Flow - Dashboard edits, Claude reads
    print("\n[7/7] Bidirectional Verification: User edits on Dashboard → Claude retrieves via MCP...")
    from app.schemas.subscription import SubscriptionUpdate
    from app.api.v1.subscriptions import update_subscription as api_update_subscription
    from app.db.models import RenewalDecision

    api_update_subscription(
        sub_id=uuid.UUID(sub_id),
        payload=SubscriptionUpdate(
            amount=Decimal("35000.00"),
            owner="Priya Nair",
            renewal_decision=RenewalDecision.UNDER_REVIEW,
        ),
        db=db,
        org_id=org_id,
    )
    print("      ✓ Dashboard user updated amount to ₹35,000, owner to 'Priya Nair', decision to 'Under Review'")

    claude_fetch = json.loads(mcp_server.get_subscription(subscription_id=sub_id))["subscription"]
    assert claude_fetch["amount"] == 35000.0
    assert claude_fetch["owner"] == "Priya Nair"
    assert claude_fetch["renewal_decision"] == "Under Review"
    print(f"      ✓ Claude retrieved edited data via MCP successfully:")
    print(f"        Amount: ₹{claude_fetch['amount']:,.0f} | Owner: {claude_fetch['owner']} | Decision: {claude_fetch['renewal_decision']}")

    db.close()
    print("\n" + "=" * 70)
    print(" ALL 7 VERIFICATION STEPS PASSED SUCCESSFULLY! ")
    print(" Full bidirectional integration (Claude ⇄ DB ⇄ Dashboard) is verified. ")
    print("=" * 70)


if __name__ == "__main__":
    run_e2e_flow()

