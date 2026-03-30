from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.database import get_db
from app.models.planning import PlanningApplication
from app.schemas.planning import PlanningApplicationOut, PlanningApplicationCreate
from app.auth.utils import get_current_user, get_current_admin
from app.services.ingestion.csv_import import (
    _detect_planning_uplift_signals,
    _calculate_planning_uplift_score,
)

router = APIRouter(prefix="/planning", tags=["planning"])


@router.get("", response_model=dict)
async def list_planning(
    council: Optional[str] = Query(None),
    postcode: Optional[str] = Query(None),
    application_type: Optional[str] = Query(None),
    uplift_score_min: Optional[float] = Query(None),
    keyword: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List planning applications with filtering and pagination."""
    stmt = select(PlanningApplication)

    if council:
        stmt = stmt.where(PlanningApplication.council.ilike(f"%{council}%"))
    if postcode:
        stmt = stmt.where(PlanningApplication.postcode.ilike(f"{postcode}%"))
    if application_type:
        stmt = stmt.where(
            PlanningApplication.application_type.ilike(f"%{application_type}%")
        )
    if uplift_score_min is not None:
        stmt = stmt.where(PlanningApplication.uplift_score >= uplift_score_min)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                PlanningApplication.proposal.ilike(kw),
                PlanningApplication.address.ilike(kw),
                PlanningApplication.application_reference.ilike(kw),
            )
        )
    if date_from:
        from datetime import date
        try:
            from datetime import datetime
            df = datetime.strptime(date_from, "%Y-%m-%d").date()
            stmt = stmt.where(PlanningApplication.date_received >= df)
        except ValueError:
            pass

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    stmt = (
        stmt
        .order_by(PlanningApplication.date_received.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    apps = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "items": [PlanningApplicationOut.model_validate(a).model_dump() for a in apps],
    }


@router.get("/{planning_id}", response_model=PlanningApplicationOut)
async def get_planning(
    planning_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a single planning application by ID."""
    result = await db.execute(
        select(PlanningApplication).where(PlanningApplication.id == planning_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Planning application not found")
    return app


@router.post("", response_model=PlanningApplicationOut, status_code=status.HTTP_201_CREATED)
async def create_planning(
    app_in: PlanningApplicationCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Create a new planning application record (admin only)."""
    # Check for duplicate
    existing = await db.execute(
        select(PlanningApplication).where(
            PlanningApplication.council == app_in.council,
            PlanningApplication.application_reference == app_in.application_reference,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Planning application with this council/reference already exists",
        )

    data = app_in.model_dump()
    # Auto-detect uplift signals from proposal if not provided
    if not data.get("uplift_signals") and data.get("proposal"):
        signals = _detect_planning_uplift_signals(data["proposal"])
        data["uplift_signals"] = signals if signals else None
        data["uplift_score"] = _calculate_planning_uplift_score(signals)

    app = PlanningApplication(**data)
    db.add(app)
    await db.flush()
    await db.refresh(app)
    return app
