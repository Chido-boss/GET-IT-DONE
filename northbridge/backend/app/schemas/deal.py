from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class DealOut(BaseModel):
    id: UUID
    title: str
    address: str
    postcode: Optional[str]
    council: Optional[str]
    property_type: Optional[str]
    bedrooms: Optional[int]
    description: Optional[str]
    source_url: Optional[str]
    strategy: str
    purchase_price: int
    estimated_value: Optional[int]
    gdv: Optional[int]
    refurb_cost: Optional[int]
    other_costs: Optional[int]
    total_cost: Optional[int]
    profit: Optional[int]
    roi: Optional[float]
    annual_yield: Optional[float]
    monthly_cashflow: Optional[int]
    is_undervalued: bool
    has_planning_upside: bool
    is_high_roi: bool
    is_distressed: bool
    near_regen_zone: bool
    overall_score: Optional[float]
    roi_score: Optional[float]
    risk_score: Optional[float]
    planning_uplift_score: Optional[float]
    market_score: Optional[float]
    score_drivers: Optional[list]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class DealFilter(BaseModel):
    strategy: Optional[str] = None
    min_roi: Optional[float] = None
    max_price: Optional[int] = None
    min_price: Optional[int] = None
    council: Optional[str] = None
    is_undervalued: Optional[bool] = None
    is_high_roi: Optional[bool] = None
    has_planning_upside: Optional[bool] = None
    min_score: Optional[float] = None
    status: Optional[str] = None


class ScoreRequest(BaseModel):
    purchase_price: int
    estimated_value: Optional[int] = None
    gdv: Optional[int] = None
    refurb_cost: Optional[int] = 0
    other_costs: Optional[int] = 0
    strategy: str = "flip"
    bedrooms: Optional[int] = None
    postcode: Optional[str] = None
    description: Optional[str] = None


class ScoreResponse(BaseModel):
    overall_score: float
    roi_score: float
    risk_score: float
    planning_uplift_score: float
    market_score: float
    profit: Optional[int]
    roi: Optional[float]
    is_undervalued: bool
    is_high_roi: bool
    has_planning_upside: bool
    score_drivers: list
