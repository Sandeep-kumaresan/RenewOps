"""
RenewOps Remote MCP Server
==========================
Implements 6 MCP tools using the official Python MCP SDK with Streamable HTTP transport.

Tools:
  1. create_subscription
  2. list_subscriptions
  3. get_subscription
  4. update_subscription
  5. get_upcoming_renewals
  6. get_spending_summary
  7. delete_subscription (with server-side confirmation safeguards)

Transport: Streamable HTTP (compatible with Claude's remote custom connector).
Security Architecture:
  - Authentication is enforced at the HTTP middleware level (Authorization: Bearer <MCP_API_KEY>).
  - Tools expose clean business parameters without leaking auth tokens into tool schemas.
  - Organization isolation: all database operations are strictly scoped to the configured organization.
"""

import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate
from app.db.models import BillingCycle, SubscriptionStatus, RenewalDecision
from app.services import subscription_service, renewal_service, analytics_service

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="RenewOps",
    instructions=(
        "RenewOps subscription and contract management tools. "
        "Use these tools to create, read, and update subscription records "
        "stored in the RenewOps PostgreSQL database. "
        "All database operations are strictly scoped to the authorized organization. "
        "All monetary amounts are in the currency specified per subscription (default INR). "
        "Dates must be in YYYY-MM-DD format. "
        "For optional string fields, pass an empty string '' to leave them unset."
    ),
)

# ---------------------------------------------------------------------------
# Helpers & Scoping
# ---------------------------------------------------------------------------

def _db():
    return SessionLocal()


def _org_id() -> uuid.UUID:
    """Return the scoped organization UUID."""
    return uuid.UUID(settings.DEMO_ORG_ID)


def _serialise(obj: Any) -> Any:
    """Make objects JSON-safe for MCP responses."""
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialise(i) for i in obj]
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    return obj


def _sub_to_dict(sub) -> dict:
    return _serialise(sub.model_dump())


# ---------------------------------------------------------------------------
# Tool 1: create_subscription
# ---------------------------------------------------------------------------

@mcp.tool()
def create_subscription(
    name: str,
    vendor: str,
    category: str,
    amount: float,
    billing_cycle: str,
    start_date: str,
    renewal_date: str,
    currency: str = "INR",
    department: str = "",
    owner: str = "",
    auto_renewal: bool = False,
    renewal_decision: str = "Undecided",
    notes: str = "",
) -> str:
    """
    Create a new subscription in RenewOps.

    Args:
        name: Subscription name (e.g. 'AWS Production')
        vendor: Vendor name (e.g. 'Amazon Web Services')
        category: Category (e.g. 'Cloud Infrastructure', 'SaaS', 'Domain')
        amount: Cost amount (numeric, e.g. 25000.0)
        billing_cycle: One of 'Monthly', 'Quarterly', 'Yearly'
        start_date: Start date in YYYY-MM-DD format (e.g. '2026-01-01')
        renewal_date: Next renewal date in YYYY-MM-DD format (e.g. '2026-12-01')
        currency: Currency code, default 'INR'
        department: Owning department, pass '' to leave blank
        owner: Person responsible, pass '' to leave blank
        auto_renewal: Whether auto-renewal is enabled (default False)
        renewal_decision: One of 'Renew', 'Cancel', 'Under Review', 'Undecided'
        notes: Additional notes, pass '' to leave blank

    Returns:
        JSON string with created subscription details including risk score.
    """
    db = _db()
    try:
        payload = SubscriptionCreate(
            org_id=_org_id(),
            name=name,
            vendor=vendor,
            category=category,
            amount=Decimal(str(amount)),
            currency=currency,
            billing_cycle=BillingCycle(billing_cycle),
            start_date=date.fromisoformat(start_date),
            renewal_date=date.fromisoformat(renewal_date),
            department=department or None,
            owner=owner or None,
            auto_renewal=auto_renewal,
            renewal_decision=RenewalDecision(renewal_decision),
            notes=notes or None,
        )
        result = subscription_service.create_subscription(db, payload)
        return json.dumps({"success": True, "subscription": _sub_to_dict(result)}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 2: list_subscriptions
# ---------------------------------------------------------------------------

@mcp.tool()
def list_subscriptions(
    status: str = "",
    department: str = "",
    search: str = "",
    limit: int = 50,
) -> str:
    """
    List subscriptions for the authorized organization with optional filters.

    Args:
        status: Filter by status ('Active', 'Inactive', 'Cancelled', 'Paused'), or '' for all
        department: Filter by department name (partial match), or '' for all
        search: Search by subscription name or vendor (partial match), or '' for all
        limit: Max number of results to return (default 50)

    Returns:
        JSON string with list of subscriptions and their risk scores.
    """
    db = _db()
    try:
        items = subscription_service.list_subscriptions(
            db,
            org_id=_org_id(),
            status=status or None,
            department=department or None,
            search=search or None,
            limit=limit,
        )
        return json.dumps(
            {"total": len(items), "subscriptions": [_sub_to_dict(s) for s in items]},
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 3: get_subscription
# ---------------------------------------------------------------------------

@mcp.tool()
def get_subscription(subscription_id: str) -> str:
    """
    Get detailed information about a specific subscription including risk score.
    Strictly restricted to the authorized organization.

    Args:
        subscription_id: UUID of the subscription (e.g. '123e4567-e89b-12d3-a456-426614174000')

    Returns:
        JSON string with subscription details and risk analysis.
    """
    db = _db()
    try:
        result = subscription_service.get_subscription(db, uuid.UUID(subscription_id), org_id=_org_id())
        if not result:
            return json.dumps({"success": False, "error": "Subscription not found or access denied"})
        return json.dumps({"success": True, "subscription": _sub_to_dict(result)}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 4: update_subscription
# ---------------------------------------------------------------------------

@mcp.tool()
def update_subscription(
    subscription_id: str,
    name: str = "",
    vendor: str = "",
    category: str = "",
    amount: float = -1.0,
    billing_cycle: str = "",
    renewal_date: str = "",
    department: str = "",
    owner: str = "",
    status: str = "",
    renewal_decision: str = "",
    notes: str = "",
) -> str:
    """
    Update fields on an existing subscription within the authorized organization.
    Pass '' for string fields or -1 for amount to leave them unchanged.

    Args:
        subscription_id: UUID of the subscription to update
        name: New subscription name, or '' to leave unchanged
        vendor: New vendor name, or '' to leave unchanged
        category: New category, or '' to leave unchanged
        amount: New cost amount, or -1 to leave unchanged
        billing_cycle: New billing cycle ('Monthly', 'Quarterly', 'Yearly'), or '' to leave unchanged
        renewal_date: New renewal date in YYYY-MM-DD format, or '' to leave unchanged
        department: New department, or '' to leave unchanged
        owner: New owner, or '' to leave unchanged
        status: New status ('Active', 'Inactive', 'Cancelled', 'Paused'), or '' to leave unchanged
        renewal_decision: New decision ('Renew', 'Cancel', 'Under Review', 'Undecided'), or '' to leave unchanged
        notes: New notes, or '' to leave unchanged

    Returns:
        JSON string with updated subscription details.
    """
    db = _db()
    try:
        update_data: dict = {}
        if name: update_data["name"] = name
        if vendor: update_data["vendor"] = vendor
        if category: update_data["category"] = category
        if amount != -1.0: update_data["amount"] = Decimal(str(amount))
        if billing_cycle: update_data["billing_cycle"] = BillingCycle(billing_cycle)
        if renewal_date: update_data["renewal_date"] = date.fromisoformat(renewal_date)
        if department: update_data["department"] = department
        if owner: update_data["owner"] = owner
        if status: update_data["status"] = SubscriptionStatus(status)
        if renewal_decision: update_data["renewal_decision"] = RenewalDecision(renewal_decision)
        if notes: update_data["notes"] = notes

        payload = SubscriptionUpdate(**update_data)
        result = subscription_service.update_subscription(db, uuid.UUID(subscription_id), payload, org_id=_org_id())
        if not result:
            return json.dumps({"success": False, "error": "Subscription not found or access denied"})
        return json.dumps({"success": True, "subscription": _sub_to_dict(result)}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 5: get_upcoming_renewals
# ---------------------------------------------------------------------------

@mcp.tool()
def get_upcoming_renewals(days_ahead: int = 30) -> str:
    """
    Get subscriptions renewing within the next N days for the authorized organization.

    Args:
        days_ahead: Number of days to look ahead (default 30, max 365)

    Returns:
        JSON string with list of upcoming renewals sorted by renewal date.
    """
    db = _db()
    try:
        items = renewal_service.get_upcoming_renewals(db, days_ahead=min(days_ahead, 365), org_id=_org_id())
        return json.dumps(
            {"days_ahead": days_ahead, "total": len(items), "renewals": [_sub_to_dict(s) for s in items]},
            indent=2,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 6: get_spending_summary
# ---------------------------------------------------------------------------

@mcp.tool()
def get_spending_summary() -> str:
    """
    Get a full spending summary for the authorized organization including total MRR, ARR,
    department breakdown (INR-normalized), top subscriptions, and other currency breakdowns.

    Returns:
        JSON string with spending analytics.
    """
    db = _db()
    try:
        summary = analytics_service.get_spending_summary(db, org_id=_org_id())
        return json.dumps(_serialise(summary.model_dump()), indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 7: delete_subscription (with server-side confirmation safeguards)
# ---------------------------------------------------------------------------

@mcp.tool()
def delete_subscription(
    subscription_id: str,
    confirm: bool = False,
    expected_name: str = "",
) -> str:
    """
    Safely delete a subscription record from the RenewOps database.

    CRITICAL SAFEGUARDS (Enforced Server-Side):
    1. Confirmation Gate: If confirm=False, the server REFUSES to delete.
       Instead, it returns the subscription details so you can ask the user
       for explicit confirmation first.
    2. Identity Safeguard: When confirm=True, expected_name MUST match the
       actual subscription name stored in the database. If it does not match,
       the deletion is immediately aborted to prevent deleting the wrong subscription.
    3. Tenant Isolation: Operates strictly within the authorized organization.

    Workflow:
      Step 1: Identify the subscription ID and call delete_subscription(subscription_id=...).
      Step 2: Read the returned details and ask the user:
              "Are you sure you want to delete [Name] ([Vendor], [Amount])?"
      Step 3: When the user confirms ("Yes, delete it"), re-call:
              delete_subscription(subscription_id=..., confirm=True, expected_name="[Name]")

    Args:
        subscription_id: UUID of the subscription to delete
        confirm: Must be explicitly set to True to execute deletion (default: False)
        expected_name: The expected name of the subscription for safety verification

    Returns:
        JSON string indicating whether deletion succeeded, was blocked by safeguards,
        or requires confirmation.
    """
    db = _db()
    try:
        try:
            sub_uuid = uuid.UUID(subscription_id)
        except ValueError:
            return json.dumps({
                "success": False,
                "error": f"Invalid subscription_id format: '{subscription_id}'. Must be a valid UUID.",
            })

        sub = subscription_service.get_subscription(db, sub_uuid, org_id=_org_id())
        if not sub:
            return json.dumps({
                "success": False,
                "error": "Subscription not found or does not belong to authorized organization.",
            })

        # Safeguard 1: Explicit confirmation required
        if not confirm:
            return json.dumps({
                "success": False,
                "requires_confirmation": True,
                "message": (
                    f"Confirmation required before deleting '{sub.name}'. Please ask the user to confirm deleting "
                    f"'{sub.name}' from vendor '{sub.vendor}'. Once confirmed, call delete_subscription "
                    f"with confirm=True and expected_name='{sub.name}'."
                ),
                "subscription_to_delete": {
                    "id": str(sub.id),
                    "name": sub.name,
                    "vendor": sub.vendor,
                    "amount": float(sub.amount),
                    "currency": sub.currency,
                    "billing_cycle": sub.billing_cycle.value if hasattr(sub.billing_cycle, "value") else str(sub.billing_cycle),
                    "renewal_date": sub.renewal_date.isoformat() if sub.renewal_date else None,
                    "department": sub.department,
                    "owner": sub.owner,
                },
            }, indent=2)

        # Safeguard 2: Name verification to prevent deleting the wrong subscription
        if not expected_name or expected_name.strip().lower() != sub.name.strip().lower():
            return json.dumps({
                "success": False,
                "error": (
                    f"Safety check failed: provided expected_name '{expected_name}' does not match "
                    f"actual subscription name '{sub.name}'. Deletion aborted to protect data."
                ),
            }, indent=2)

        # Execute deletion
        deleted = subscription_service.delete_subscription(db, sub_uuid, org_id=_org_id())
        if not deleted:
            return json.dumps({
                "success": False,
                "error": "Failed to delete subscription record from database.",
            })

        return json.dumps({
            "success": True,
            "status": "deleted",
            "message": f"Subscription '{sub.name}' (ID: {sub.id}) was permanently deleted from RenewOps.",
            "deleted_subscription": {
                "id": str(sub.id),
                "name": sub.name,
                "vendor": sub.vendor,
                "amount": float(sub.amount),
                "currency": sub.currency,
            },
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
    finally:
        db.close()
