import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.alert import Alert, AlertEvent
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertUpdate, AlertOut, AlertEventOut
from app.auth.utils import get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/events", response_model=List[AlertEventOut])
async def get_alert_events(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current user's unread alert events."""
    # Get alert IDs belonging to this user
    alerts_result = await db.execute(
        select(Alert.id).where(Alert.user_id == current_user.id)
    )
    alert_ids = [row[0] for row in alerts_result.fetchall()]

    if not alert_ids:
        return []

    result = await db.execute(
        select(AlertEvent)
        .where(
            AlertEvent.alert_id.in_(alert_ids),
            AlertEvent.is_read == False,  # noqa: E712
        )
        .order_by(AlertEvent.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.post("", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
async def create_alert(
    alert_in: AlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new alert for the current user."""
    alert = Alert(
        user_id=current_user.id,
        title=alert_in.title,
        alert_type=alert_in.alert_type,
        criteria=alert_in.criteria,
        channels=alert_in.channels or {"email": False, "telegram": False, "in_app": True},
        is_active=alert_in.is_active,
    )
    db.add(alert)
    await db.flush()
    await db.refresh(alert)
    return alert


@router.get("", response_model=List[AlertOut])
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all alerts for the current user."""
    result = await db.execute(
        select(Alert)
        .where(Alert.user_id == current_user.id)
        .order_by(Alert.created_at.desc())
    )
    return result.scalars().all()


@router.put("/{alert_id}", response_model=AlertOut)
async def update_alert(
    alert_id: uuid.UUID,
    alert_in: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an alert (owner only)."""
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    update_data = alert_in.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(alert, key, value)

    await db.flush()
    await db.refresh(alert)
    return alert


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an alert (owner only)."""
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.delete(alert)


@router.post("/events/{event_id}/read", response_model=AlertEventOut)
async def mark_event_read(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark an alert event as read."""
    # Verify ownership via alert
    result = await db.execute(
        select(AlertEvent)
        .join(Alert, AlertEvent.alert_id == Alert.id)
        .where(
            AlertEvent.id == event_id,
            Alert.user_id == current_user.id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Alert event not found")

    event.is_read = True
    await db.flush()
    await db.refresh(event)
    return event
