"""
Seed script – populates the demo org with sample subscriptions.
Run once after `init_db` to have realistic data for development.

Usage:
    venv/Scripts/python scripts/seed_demo_data.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import date, timedelta
from decimal import Decimal

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.schemas.subscription import SubscriptionCreate
from app.db.models import BillingCycle, SubscriptionStatus, RenewalDecision
from app.services.subscription_service import create_subscription

SAMPLE_SUBS = [
    SubscriptionCreate(
        name="AWS Production",
        vendor="Amazon Web Services",
        category="Cloud Infrastructure",
        amount=Decimal("25000"),
        currency="INR",
        billing_cycle=BillingCycle.MONTHLY,
        start_date=date(2025, 1, 1),
        renewal_date=date(2026, 12, 1),
        department="Engineering",
        owner="Rahul Sharma",
        status=SubscriptionStatus.ACTIVE,
        auto_renewal=True,
        renewal_decision=RenewalDecision.UNDECIDED,
        notes="Production workloads only",
    ),
    SubscriptionCreate(
        name="Microsoft 365 Business",
        vendor="Microsoft",
        category="Productivity",
        amount=Decimal("45000"),
        currency="INR",
        billing_cycle=BillingCycle.YEARLY,
        start_date=date(2025, 3, 1),
        renewal_date=date(2026, 11, 20),
        department="Operations",
        owner="Priya Nair",
        status=SubscriptionStatus.ACTIVE,
        auto_renewal=False,
        renewal_decision=RenewalDecision.RENEW,
        notes="50 user licenses",
    ),
    SubscriptionCreate(
        name="Google Workspace Business",
        vendor="Google",
        category="Productivity",
        amount=Decimal("36000"),
        currency="INR",
        billing_cycle=BillingCycle.YEARLY,
        start_date=date(2025, 6, 15),
        renewal_date=date(2026, 12, 15),
        department="Engineering",
        owner="",
        status=SubscriptionStatus.ACTIVE,
        auto_renewal=True,
        renewal_decision=RenewalDecision.UNDECIDED,
        notes="30 seats",
    ),
    SubscriptionCreate(
        name="Slack Business+",
        vendor="Slack",
        category="Communication",
        amount=Decimal("150"),
        currency="USD",
        billing_cycle=BillingCycle.MONTHLY,
        start_date=date(2025, 1, 1),
        renewal_date=date.today() + timedelta(days=12),
        department="All Departments",
        owner="Ankit Verma",
        status=SubscriptionStatus.ACTIVE,
        auto_renewal=False,
        renewal_decision=RenewalDecision.UNDER_REVIEW,
        notes="Evaluate vs Teams",
    ),
    SubscriptionCreate(
        name="GitHub Enterprise",
        vendor="GitHub",
        category="Developer Tools",
        amount=Decimal("84000"),
        currency="INR",
        billing_cycle=BillingCycle.YEARLY,
        start_date=date(2025, 4, 1),
        renewal_date=date.today() + timedelta(days=5),
        department="Engineering",
        owner="",
        status=SubscriptionStatus.ACTIVE,
        auto_renewal=True,
        renewal_decision=RenewalDecision.UNDECIDED,
        notes="Critical – do not cancel",
    ),
    SubscriptionCreate(
        name="Jira Software Cloud",
        vendor="Atlassian",
        category="Project Management",
        amount=Decimal("8000"),
        currency="INR",
        billing_cycle=BillingCycle.MONTHLY,
        start_date=date(2025, 2, 1),
        renewal_date=date(2026, 12, 31),
        department="Product",
        owner="Meera Iyer",
        status=SubscriptionStatus.ACTIVE,
        auto_renewal=True,
        renewal_decision=RenewalDecision.RENEW,
        notes=None,
    ),
    SubscriptionCreate(
        name="Figma Organisation",
        vendor="Figma",
        category="Design Tools",
        amount=Decimal("18000"),
        currency="INR",
        billing_cycle=BillingCycle.YEARLY,
        start_date=date(2025, 7, 1),
        renewal_date=date.today() + timedelta(days=45),
        department="Design",
        owner="Kavya Reddy",
        status=SubscriptionStatus.ACTIVE,
        auto_renewal=False,
        renewal_decision=RenewalDecision.UNDECIDED,
        notes="10 editor seats",
    ),
    SubscriptionCreate(
        name="Cloudflare Pro",
        vendor="Cloudflare",
        category="Security & CDN",
        amount=Decimal("1500"),
        currency="INR",
        billing_cycle=BillingCycle.MONTHLY,
        start_date=date(2025, 1, 1),
        renewal_date=date(2027, 1, 1),
        department="Engineering",
        owner="Rahul Sharma",
        status=SubscriptionStatus.ACTIVE,
        auto_renewal=True,
        renewal_decision=RenewalDecision.RENEW,
        notes=None,
    ),
    SubscriptionCreate(
        name="Zoom Business",
        vendor="Zoom",
        category="Communication",
        amount=Decimal("24000"),
        currency="INR",
        billing_cycle=BillingCycle.YEARLY,
        start_date=date(2025, 5, 1),
        renewal_date=date.today() - timedelta(days=5),  # overdue
        department="Operations",
        owner="Priya Nair",
        status=SubscriptionStatus.ACTIVE,
        auto_renewal=False,
        renewal_decision=RenewalDecision.UNDECIDED,
        notes="Review if usage justifies cost",
    ),
    SubscriptionCreate(
        name="Domain – renewops.in",
        vendor="GoDaddy",
        category="Domain",
        amount=Decimal("1200"),
        currency="INR",
        billing_cycle=BillingCycle.YEARLY,
        start_date=date(2025, 1, 1),
        renewal_date=date(2027, 1, 1),
        department="Engineering",
        owner="Rahul Sharma",
        status=SubscriptionStatus.ACTIVE,
        auto_renewal=True,
        renewal_decision=RenewalDecision.RENEW,
        notes=None,
    ),
]


def seed():
    print("[seed] Initialising database…")
    init_db()
    db = SessionLocal()
    try:
        for sub in SAMPLE_SUBS:
            result = create_subscription(db, sub)
            print(f"  + Created: {result.name} ({result.vendor})")
        print(f"[seed] Done – {len(SAMPLE_SUBS)} subscriptions created.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

