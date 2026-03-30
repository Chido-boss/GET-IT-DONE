import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class AlertCreate(BaseModel):
    title: str
    alert_type: str  # new_listing / price_drop / planning / score_threshold
    criteria: Optional[dict] = None
    channels: Optional[dict] = None
    is_active: bool = True


class AlertUpdate(BaseModel):
    title: Optional[str] = None
    alert_type: Optional[str] = None
    criteria: Optional[dict] = None
    channels: Optional[dict] = None
    is_active: Optional[bool] = None


class AlertOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    alert_type: str
    criteria: Optional[dict] = None
    channels: Optional[dict] = None
    is_active: bool
    last_triggered_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertEventOut(BaseModel):
    id: uuid.UUID
    alert_id: uuid.UUID
    listing_id: Optional[uuid.UUID] = None
    planning_id: Optional[uuid.UUID] = None
    message: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
