import uuid
from datetime import datetime, date
from sqlalchemy import String, Float, Date, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSON
from app.database import Base


class PlanningApplication(Base):
    __tablename__ = "planning_applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    council: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    application_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    postcode: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    application_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    proposal: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_received: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_validated: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_decided: Mapped[date | None] = mapped_column(Date, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    uplift_signals: Mapped[list | None] = mapped_column(JSON, nullable=True)
    uplift_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("council", "application_reference", name="uq_planning_council_ref"),
    )
