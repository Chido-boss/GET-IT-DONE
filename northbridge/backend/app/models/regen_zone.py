import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class RegenerationZone(Base):
    __tablename__ = "regeneration_zones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    council: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # Active/Planning/Complete
    funding_amount: Mapped[str | None] = mapped_column(String(100), nullable=True)
    announcement_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completion_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    center_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    radius_km: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    postcodes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    opportunity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
