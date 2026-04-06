import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class DealAction(Base):
    __tablename__ = "deal_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id: Mapped[str] = mapped_column(String(36), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # action_type: "express_interest" | "jv_interest" | "request_deal_pack" | "save" | "unsave"
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    budget_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    finance_type: Mapped[str] = mapped_column(String(50), nullable=True)  # cash/bridging/mortgage
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DealView(Base):
    __tablename__ = "deal_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[str] = mapped_column(String(36), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    reached_paywall: Mapped[bool] = mapped_column(Boolean, default=False)
    unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
