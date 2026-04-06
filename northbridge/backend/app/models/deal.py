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
    property_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Rightmove / Auction / Off-market / Direct

    # Strategy
    strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    exit_strategy: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Market intelligence
    days_on_market: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_reductions: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Financials — core
    purchase_price: Mapped[int] = mapped_column(Integer, nullable=False)
    asking_price: Mapped[int | None] = mapped_column(Integer, nullable=True)  # alias / original ask
    estimated_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gdv: Mapped[int | None] = mapped_column(Integer, nullable=True)
    refurb_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    other_costs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Computed financials
    gross_profit: Mapped[int | None] = mapped_column(Integer, nullable=True)  # exit_value - purchase_price
    profit: Mapped[int | None] = mapped_column(Integer, nullable=True)        # exit_value - total_cost (net)
    net_profit: Mapped[int | None] = mapped_column(Integer, nullable=True)    # same as profit, explicit alias
    roi: Mapped[float | None] = mapped_column(Float, nullable=True)           # %
    roi_pct: Mapped[float | None] = mapped_column(Float, nullable=True)       # explicit alias for roi
    discount_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # % below estimated value
    annual_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    annual_yield_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_cashflow: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Intelligence flags
    is_undervalued: Mapped[bool] = mapped_column(Boolean, default=False)
    has_planning_upside: Mapped[bool] = mapped_column(Boolean, default=False)
    is_high_roi: Mapped[bool] = mapped_column(Boolean, default=False)
    is_distressed: Mapped[bool] = mapped_column(Boolean, default=False)
    near_regen_zone: Mapped[bool] = mapped_column(Boolean, default=False)

    # Scoring — component scores (0-100, higher = better)
    score_roi: Mapped[float | None] = mapped_column(Float, nullable=True)        # ROI component (35% weight)
    score_discount: Mapped[float | None] = mapped_column(Float, nullable=True)   # Discount component (30% weight)
    score_risk: Mapped[float | None] = mapped_column(Float, nullable=True)       # Risk component (20% weight), higher = less risk
    score_liquidity: Mapped[float | None] = mapped_column(Float, nullable=True)  # Liquidity/exit component (15%)

    # Legacy score fields (kept for backward compat)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    roi_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)        # raw risk 0-100, higher = more risk
    planning_uplift_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_drivers: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Classification
    tier: Mapped[str | None] = mapped_column(String(2), nullable=True)          # S / A / B / C
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)   # High / Medium / Low
    risk_level: Mapped[str | None] = mapped_column(String(10), nullable=True)   # Low / Medium / High

    # Rich context
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    risk_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    opportunity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pipeline status
    status: Mapped[str] = mapped_column(String(30), default="active")

    # Meta
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
