import uuid
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel

from app.schemas.score import ScoreOut


class ListingCreate(BaseModel):
    source: str
    source_id: Optional[str] = None
    title: str
    address: str
    postcode: str
    council: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    property_type: str
    tenure: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    asking_price: int
    previous_price: Optional[int] = None
    date_listed: Optional[date] = None
    description: Optional[str] = None
    url: Optional[str] = None
    status: str = "active"
    agent_name: Optional[str] = None
    agent_phone: Optional[str] = None
    days_on_market: Optional[int] = None
    price_reduction_count: int = 0
    is_flagged: bool = False
    notes: Optional[str] = None


class ListingUpdate(BaseModel):
    title: Optional[str] = None
    address: Optional[str] = None
    postcode: Optional[str] = None
    council: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    property_type: Optional[str] = None
    tenure: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    asking_price: Optional[int] = None
    previous_price: Optional[int] = None
    date_listed: Optional[date] = None
    description: Optional[str] = None
    url: Optional[str] = None
    status: Optional[str] = None
    agent_name: Optional[str] = None
    agent_phone: Optional[str] = None
    days_on_market: Optional[int] = None
    price_reduction_count: Optional[int] = None
    is_flagged: Optional[bool] = None
    notes: Optional[str] = None


class ListingOut(BaseModel):
    id: uuid.UUID
    source: str
    source_id: Optional[str] = None
    title: str
    address: str
    postcode: str
    council: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    property_type: str
    tenure: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    asking_price: int
    previous_price: Optional[int] = None
    date_listed: Optional[date] = None
    first_seen_at: datetime
    last_seen_at: datetime
    description: Optional[str] = None
    url: Optional[str] = None
    status: str
    agent_name: Optional[str] = None
    agent_phone: Optional[str] = None
    days_on_market: Optional[int] = None
    price_reduction_count: int
    is_flagged: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Computed: latest score summary
    overall_score: Optional[float] = None

    model_config = {"from_attributes": True}


class ListingFilter(BaseModel):
    council: Optional[str] = None
    postcode: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    min_score: Optional[float] = None
    property_type: Optional[str] = None
    has_planning: Optional[bool] = None
    near_regen: Optional[bool] = None
    keyword: Optional[str] = None
    price_reduced: Optional[bool] = None
    status: Optional[str] = "active"
    page: int = 1
    page_size: int = 20


class ListingDetail(ListingOut):
    scores: List[ScoreOut] = []
    nearby_planning_count: int = 0

    model_config = {"from_attributes": True}
