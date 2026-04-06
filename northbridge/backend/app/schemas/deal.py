from pydantic import BaseModel
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime


class DealOut(BaseModel):
    id: UUID
    title: str
    address: str
    postcode: Optional[str] = None
    council: Optional[str] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    description: Optional[str] = None
    summary: Optional[str] = None
    source_url: Optional[str] = None
    source: Optional[str] = None
    strategy: str
    exit_strategy: Optional[str] = None

    # Market intelligence
    days_on_market: Optional[int] = None
    price_reductions: Optional[int] = None

    # Financials
    purchase_price: int
    asking_price: Optional[int] = None
    estimated_value: Optional[int] = None
    gdv: Optional[int] = None
    refurb_cost: Optional[int] = None
    other_costs: Optional[int] = None
    total_cost: Optional[int] = None

    # Computed financials
    gross_profit: Optional[int] = None
    net_profit: Optional[int] = None
    profit: Optional[int] = None
    roi: Optional[float] = None
    roi_pct: Optional[float] = None
    discount_pct: Optional[float] = None
    annual_yield: Optional[float] = None
    annual_yield_pct: Optional[float] = None
    monthly_cashflow: Optional[int] = None

    # Intelligence flags
    is_undervalued: bool = False
    has_planning_upside: bool = False
    is_high_roi: bool = False
    is_distressed: bool = False
    near_regen_zone: bool = False

    # Component scores
    score_roi: Optional[float] = None
    score_discount: Optional[float] = None
    score_risk: Optional[float] = None
    score_liquidity: Optional[float] = None

    # Legacy scores
    overall_score: Optional[float] = None
    roi_score: Optional[float] = None
    risk_score: Optional[float] = None
    planning_uplift_score: Optional[float] = None
    market_score: Optional[float] = None
    score_drivers: Optional[List[Any]] = None

    # Classification
    tier: Optional[str] = None
    confidence: Optional[str] = None
    risk_level: Optional[str] = None

    # Rich context
    tags: Optional[List[str]] = None
    risk_notes: Optional[str] = None
    opportunity_notes: Optional[str] = None

    # Pipeline
    status: str
    rank: Optional[int] = None
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
    tier: Optional[str] = None
    min_discount: Optional[float] = None
    search: Optional[str] = None


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
    days_on_market: Optional[int] = None
    price_reductions: Optional[int] = None
    annual_yield_pct: Optional[float] = None


class ScoreResponse(BaseModel):
    overall_score: float
    score_roi: float
    score_discount: float
    score_risk: float
    score_liquidity: float
    tier: str
    confidence: str
    risk_level: str
    roi_score: float
    risk_score: float
    planning_uplift_score: float
    market_score: float
    gross_profit: Optional[int] = None
    net_profit: Optional[int] = None
    profit: Optional[int] = None
    roi: Optional[float] = None
    roi_pct: Optional[float] = None
    discount_pct: Optional[float] = None
    is_undervalued: bool
    is_high_roi: bool
    has_planning_upside: bool
    score_drivers: list
