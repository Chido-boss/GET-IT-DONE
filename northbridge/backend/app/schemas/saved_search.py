import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SavedSearchCreate(BaseModel):
    name: str
    filters: Optional[dict] = None


class SavedSearchOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    filters: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}
