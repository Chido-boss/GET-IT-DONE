import uuid
from datetime import datetime
from sqlalchemy import Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSON
from app.database import Base


class ListingScore(Base):
    __tablename__ = "listing_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    bmv_score: Mapped[float] = mapped_column(Float, nullable=False)
    distress_score: Mapped[float] = mapped_column(Float, nullable=False)
    momentum_score: Mapped[float] = mapped_column(Float, nullable=False)
    planning_score: Mapped[float] = mapped_column(Float, nullable=False)
    regeneration_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_fair_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_comparable_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_drivers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    scored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    listing: Mapped["Listing"] = relationship(  # noqa: F821
        "Listing", back_populates="scores"
    )
