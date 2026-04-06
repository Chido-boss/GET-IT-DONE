import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class InvestorMandate(Base):
    __tablename__ = "investor_mandates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="My Investment Mandate")

    # Budget
    min_price: Mapped[int] = mapped_column(Integer, nullable=True)
    max_price: Mapped[int] = mapped_column(Integer, nullable=True)

    # Strategy preferences (JSON list)
    preferred_strategies: Mapped[list] = mapped_column(JSON, nullable=True)  # ["flip","hmo",...]

    # Return requirements
    min_roi: Mapped[float] = mapped_column(Float, nullable=True)
    min_yield: Mapped[float] = mapped_column(Float, nullable=True)

    # Risk
    max_risk_score: Mapped[int] = mapped_column(Integer, nullable=True, default=70)
    min_conviction_score: Mapped[int] = mapped_column(Integer, nullable=True, default=50)

    # Geography
    preferred_councils: Mapped[list] = mapped_column(JSON, nullable=True)
    regen_zones_only: Mapped[bool] = mapped_column(Boolean, default=False)

    # Deal characteristics
    planning_required: Mapped[bool] = mapped_column(Boolean, nullable=True)
    max_refurb_level: Mapped[str] = mapped_column(String(20), nullable=True)  # light/mid/heavy
    min_discount_pct: Mapped[float] = mapped_column(Float, nullable=True)

    # Alerts
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_email: Mapped[bool] = mapped_column(Boolean, default=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
