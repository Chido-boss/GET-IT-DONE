import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class ScoreDriverOut(BaseModel):
    label: str
    value: Any
    impact: float
    icon: str


class ScoreOut(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    overall_score: float
    bmv_score: float
    distress_score: float
    momentum_score: float
    planning_score: float
    regeneration_score: float
    confidence_score: float
    estimated_fair_value: Optional[int] = None
    avg_comparable_price: Optional[int] = None
    discount_pct: Optional[float] = None
    score_drivers: Optional[list[dict]] = None
    scored_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
