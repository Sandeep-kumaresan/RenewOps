"""SQLAlchemy ORM models for RenewOps."""

import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Numeric, Boolean, Date, DateTime,
    Text, ForeignKey, Enum as SAEnum, func
)
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
import enum

from app.db.session import Base


# ---------------------------------------------------------------------------
# Cross-dialect GUID (Native UUID on PostgreSQL, CHAR(36) on SQLite)
# ---------------------------------------------------------------------------

class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's native UUID, otherwise stores as CHAR(36).
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(str(value)))
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(str(value))
        return value


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BillingCycle(str, enum.Enum):
    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    YEARLY = "Yearly"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    CANCELLED = "Cancelled"
    PAUSED = "Paused"


class RenewalDecision(str, enum.Enum):
    RENEW = "Renew"
    CANCEL = "Cancel"
    UNDER_REVIEW = "Under Review"
    UNDECIDED = "Undecided"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Organization(Base):
    """Tenant / organisation record (single-tenant MVP uses one demo org)."""
    __tablename__ = "organizations"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    subscriptions = relationship("Subscription", back_populates="organization")


class Subscription(Base):
    """Core subscription / contract record."""
    __tablename__ = "subscriptions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    org_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    name = Column(String(255), nullable=False)
    vendor = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    billing_cycle = Column(
        SAEnum(BillingCycle, name="billing_cycle_enum", create_type=True),
        nullable=False,
    )

    start_date = Column(Date, nullable=False)
    renewal_date = Column(Date, nullable=False)

    department = Column(String(100), nullable=True)
    owner = Column(String(255), nullable=True)

    status = Column(
        SAEnum(SubscriptionStatus, name="subscription_status_enum", create_type=True),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )
    auto_renewal = Column(Boolean, default=False, nullable=False)
    renewal_decision = Column(
        SAEnum(RenewalDecision, name="renewal_decision_enum", create_type=True),
        default=RenewalDecision.UNDECIDED,
        nullable=False,
    )

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization = relationship("Organization", back_populates="subscriptions")
    renewal_logs = relationship(
        "RenewalLog", back_populates="subscription", cascade="all, delete-orphan"
    )


class RenewalLog(Base):
    """Audit trail for every renewal-decision change."""
    __tablename__ = "renewal_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(
        GUID(), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )

    old_decision = Column(String(50), nullable=True)
    new_decision = Column(String(50), nullable=False)
    changed_by = Column(String(255), nullable=True)   # username / "MCP" / "API"
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)

    subscription = relationship("Subscription", back_populates="renewal_logs")
