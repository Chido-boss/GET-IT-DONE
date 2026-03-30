import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ImportLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    import_type: str
    filename: Optional[str] = None
    rows_processed: int
    rows_imported: int
    rows_failed: int
    errors: Optional[List] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
