import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identity
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    postcode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    council: Mapped[str | None] = mapped_column(String(100), nullable=True)
    property_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # terraced/semi/detached/flat/commercial
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Strategy
    strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    # flip | brr | brrr | conversion | planning_uplift | hmo | btl | auction

    # Financials
    purchase_price: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_value: Mapped[int | None] = mapped_column(Integer, nullable=True)   # ARV / GDV
    gdv: Mapped[int | None] = mapped_column(Integer, nullable=True)               # Gross Development Value
    refurb_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    other_costs: Mapped[int | None] = mapped_column(Integer, nullable=True)       # legal, stamp duty, finance
    total_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    roi: Mapped[float | None] = mapped_column(Float, nullable=True)               # %
    annual_yield: Mapped[float | None] = mapped_column(Float, nullable=True)      # % for BTL/HMO
    monthly_cashflow: Mapped[int | None] = mapped_column(Integer, nullable=True)  # £/month for BTL/HMO

    # Intelligence flags
    is_undervalued: Mapped[bool] = mapped_column(Boolean, default=False)
    has_planning_upside: Mapped[bool] = mapped_column(Boolean, default=False)
    is_high_roi: Mapped[bool] = mapped_column(Boolean, default=False)
    is_distressed: Mapped[bool] = mapped_column(Boolean, default=False)
    near_regen_zone: Mapped[bool] = mapped_column(Boolean, default=False)

    # Scores
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)     # 0-100
    roi_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)        # 0-100, higher = more risk
    planning_uplift_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_drivers: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Pipeline status
    status: Mapped[str] = mapped_column(String(30), default="active")
    # active | under_offer | acquired | completed | passed

    # Meta
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
