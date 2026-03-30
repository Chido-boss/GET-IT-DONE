import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.regen_zone import RegenerationZone
from app.auth.utils import get_current_user, get_current_admin

router = APIRouter(prefix="/regen-zones", tags=["regen-zones"])


class RegenZoneCreate(BaseModel):
    name: str
    council: str
    description: Optional[str] = None
    status: str = "Active"
    funding_amount: Optional[str] = None
    announcement_date: Optional[str] = None
    completion_date: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_km: float = 1.0
    postcodes: Optional[str] = None
    opportunity_notes: Optional[str] = None


class RegenZoneUpdate(BaseModel):
    name: Optional[str] = None
    council: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    funding_amount: Optional[str] = None
    announcement_date: Optional[str] = None
    completion_date: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_km: Optional[float] = None
    postcodes: Optional[str] = None
    opportunity_notes: Optional[str] = None


class RegenZoneOut(BaseModel):
    id: uuid.UUID
    name: str
    council: str
    description: Optional[str] = None
    status: str
    funding_amount: Optional[str] = None
    announcement_date: Optional[str] = None
    completion_date: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    radius_km: float
    postcodes: Optional[str] = None
    opportunity_notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=List[RegenZoneOut])
async def list_regen_zones(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all regeneration zones."""
    result = await db.execute(
        select(RegenerationZone).order_by(RegenerationZone.name)
    )
    return result.scalars().all()


@router.get("/{zone_id}", response_model=RegenZoneOut)
async def get_regen_zone(
    zone_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a single regeneration zone."""
    result = await db.execute(
        select(RegenerationZone).where(RegenerationZone.id == zone_id)
    )
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="Regeneration zone not found")
    return zone


@router.post("", response_model=RegenZoneOut, status_code=status.HTTP_201_CREATED)
async def create_regen_zone(
    zone_in: RegenZoneCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Create a new regeneration zone (admin only)."""
    zone = RegenerationZone(**zone_in.model_dump())
    db.add(zone)
    await db.flush()
    await db.refresh(zone)
    return zone


@router.put("/{zone_id}", response_model=RegenZoneOut)
async def update_regen_zone(
    zone_id: uuid.UUID,
    zone_in: RegenZoneUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Update a regeneration zone (admin only)."""
    result = await db.execute(
        select(RegenerationZone).where(RegenerationZone.id == zone_id)
    )
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="Regeneration zone not found")

    update_data = zone_in.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(zone, key, value)

    await db.flush()
    await db.refresh(zone)
    return zone
