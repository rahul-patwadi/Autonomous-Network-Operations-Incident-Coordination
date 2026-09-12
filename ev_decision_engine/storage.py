"""SQLite-backed incident-history storage.

Plumbing only: engine/session setup and a generic persistence layer for
incident records. No decision logic, scoring, or domain modeling lives here —
that belongs in `schemas.py`, `cost_model.py`, and `policy.py`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DB_PATH = Path(__file__).parent / "incident_history.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class IncidentRecord(Base):
    """A generic, append-only record of an incident and the decision made on it.

    Stores opaque JSON blobs for the incident payload and decision output so
    this module has no knowledge of (and no dependency on) the shapes defined
    in `schemas.py` / produced by `policy.py`. Callers serialize/deserialize.
    """

    __tablename__ = "incident_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(String, index=True)
    payload_json: Mapped[str] = mapped_column(String)
    decision_json: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


def init_db() -> None:
    """Create tables if they don't exist yet."""
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    """Context-managed session for a single unit of work."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
