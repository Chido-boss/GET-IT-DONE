import uuid
from datetime import datetime, date
from sqlalchemy import String, Integer, Boolean, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class ComparableSale(Base):
    __tablename__ = "comparable_sales"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transaction_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    date_sold: Mapped[date] = mapped_column(Date, nullable=False)
    postcode: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    property_type: Mapped[str] = mapped_column(String(1), nullable=False)
    new_build: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    estate_type: Mapped[str | None] = mapped_column(String(1), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    county: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="land_registry", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
