"""Database initialisation – creates all tables and seeds demo data."""

import uuid
from sqlalchemy.orm import Session
from app.db.session import engine, Base, SessionLocal
from app.db.models import Organization, Subscription, RenewalLog
from app.core.config import settings


def init_db() -> None:
    """Create all tables (safe to call multiple times – uses CREATE IF NOT EXISTS)."""
    Base.metadata.create_all(bind=engine)
    _seed_demo_org()


def _seed_demo_org() -> None:
    """Insert the demo organisation if it doesn't already exist."""
    db: Session = SessionLocal()
    try:
        demo_id = uuid.UUID(settings.DEMO_ORG_ID)
        existing = db.query(Organization).filter(Organization.id == demo_id).first()
        if not existing:
            demo_org = Organization(id=demo_id, name=settings.DEMO_ORG_NAME)
            db.add(demo_org)
            db.commit()
            print(f"[init_db] Demo organisation seeded: {settings.DEMO_ORG_NAME}")
        else:
            print(f"[init_db] Demo organisation already exists – skipping seed.")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()

