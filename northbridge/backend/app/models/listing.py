import uuid
from datetime import datetime, date
from sqlalchemy import (
    String, Integer, Float, Boolean, Date, DateTime, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    postcode: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    council: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Property details
    property_type: Mapped[str] = mapped_column(String(1), nullable=False)  # D/S/T/F/O/C
    tenure: Mapped[str | None] = mapped_column(String(20), nullable=True)  # freehold/leasehold
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Pricing
    asking_price: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Dates
    date_listed: Mapped[date | None] = mapped_column(Date, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Content
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)

    # Agent info
    agent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Computed / tracked
    days_on_market: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_reduction_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # User annotations
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_listing_source_source_id"),
    )

    # Relationships
    scores: Mapped[list["ListingScore"]] = relationship(  # noqa: F821
        "ListingScore", back_populates="listing", cascade="all, delete-orphan",
        order_by="ListingScore.scored_at.desc()"
    )
    planning_links: Mapped[list["PlanningApplication"]] = relationship(  # noqa: F821
        "PlanningApplication",
        primaryjoin="foreign(PlanningApplication.postcode) == Listing.postcode",
        viewonly=True,
        uselist=True,
    )
