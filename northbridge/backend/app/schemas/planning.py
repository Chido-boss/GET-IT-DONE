import uuid
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel


class PlanningApplicationOut(BaseModel):
    id: uuid.UUID
    council: str
    application_reference: str
    address: str
    postcode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    application_type: Optional[str] = None
    proposal: Optional[str] = None
    status: Optional[str] = None
    decision: Optional[str] = None
    date_received: Optional[date] = None
    date_validated: Optional[date] = None
    date_decided: Optional[date] = None
    url: Optional[str] = None
    uplift_signals: Optional[List[str]] = None
    uplift_score: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlanningApplicationCreate(BaseModel):
    council: str
    application_reference: str
    address: str
    postcode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    application_type: Optional[str] = None
    proposal: Optional[str] = None
    status: Optional[str] = None
    decision: Optional[str] = None
    date_received: Optional[date] = None
    date_validated: Optional[date] = None
    date_decided: Optional[date] = None
    url: Optional[str] = None
    uplift_signals: Optional[List[str]] = None
    uplift_score: float = 0.0


class PlanningFilter(BaseModel):
    council: Optional[str] = None
    postcode: Optional[str] = None
    application_type: Optional[str] = None
    uplift_score_min: Optional[float] = None
    keyword: Optional[str] = None
    date_from: Optional[date] = None
    page: int = 1
    page_size: int = 20
