from typing import List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.listing import Listing
from app.models.score import ListingScore
from app.models.planning import PlanningApplication
from app.models.regen_zone import RegenerationZone
from app.models.comparable import ComparableSale
from app.schemas.listing import ListingCreate, ListingUpdate, ListingOut, ListingDetail
from app.auth.utils import get_current_user, get_current_admin
from app.services.scoring import score_listing
from app.services.comparables import match_comparables, get_nearby_planning

router = APIRouter(prefix="/listings", tags=["listings"])


def _apply_listing_filters(stmt, filters: dict):
    """Apply dynamic filter conditions to a listings SELECT statement."""
    council = filters.get("council")
    postcode = filters.get("postcode")
    min_price = filters.get("min_price")
    max_price = filters.get("max_price")
    property_type = filters.get("property_type")
    keyword = filters.get("keyword")
    price_reduced = filters.get("price_reduced")
    listing_status = filters.get("status", "active")

    if council:
        stmt = stmt.where(Listing.council.ilike(f"%{council}%"))
    if postcode:
        stmt = stmt.where(Listing.postcode.ilike(f"{postcode}%"))
    if min_price is not None:
        stmt = stmt.where(Listing.asking_price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Listing.asking_price <= max_price)
    if property_type:
        stmt = stmt.where(Listing.property_type == property_type.upper())
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                Listing.title.ilike(kw),
                Listing.description.ilike(kw),
                Listing.address.ilike(kw),
            )
        )
    if price_reduced is True:
        stmt = stmt.where(Listing.price_reduction_count > 0)
    if listing_status:
        stmt = stmt.where(Listing.status == listing_status)

    return stmt


@router.get("", response_model=dict)
async def list_listings(
    council: Optional[str] = Query(None),
    postcode: Optional[str] = Query(None),
    min_price: Optional[int] = Query(None),
    max_price: Optional[int] = Query(None),
    min_score: Optional[float] = Query(None),
    property_type: Optional[str] = Query(None),
    has_planning: Optional[bool] = Query(None),
    near_regen: Optional[bool] = Query(None),
    keyword: Optional[str] = Query(None),
    price_reduced: Optional[bool] = Query(None),
    listing_status: Optional[str] = Query("active", alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    List listings with filtering and pagination.
    Includes latest overall score for each listing.
    """
    filters = {
        "council": council,
        "postcode": postcode,
        "min_price": min_price,
        "max_price": max_price,
        "property_type": property_type,
        "keyword": keyword,
        "price_reduced": price_reduced,
        "status": listing_status,
    }

    # Subquery: latest score per listing
    latest_score_subq = (
        select(
            ListingScore.listing_id,
            func.max(ListingScore.scored_at).label("max_scored_at"),
        )
        .group_by(ListingScore.listing_id)
        .subquery()
    )

    score_subq = (
        select(ListingScore.listing_id, ListingScore.overall_score)
        .join(
            latest_score_subq,
            and_(
                ListingScore.listing_id == latest_score_subq.c.listing_id,
                ListingScore.scored_at == latest_score_subq.c.max_scored_at,
            ),
        )
        .subquery()
    )

    base_stmt = select(Listing)
    base_stmt = _apply_listing_filters(base_stmt, filters)

    # min_score filter — join to score subquery
    if min_score is not None:
        base_stmt = (
            base_stmt.join(score_subq, Listing.id == score_subq.c.listing_id)
            .where(score_subq.c.overall_score >= min_score)
        )

    # has_planning filter — check if any planning app has matching postcode
    if has_planning is True:
        planning_postcode_subq = (
            select(PlanningApplication.postcode).distinct().subquery()
        )
        base_stmt = base_stmt.where(
            Listing.postcode.in_(select(planning_postcode_subq))
        )

    # near_regen filter — check if listing postcode prefix matches any zone postcode
    if near_regen is True:
        regen_result = await db.execute(select(RegenerationZone))
        regen_zones = regen_result.scalars().all()
        regen_postcodes: List[str] = []
        for zone in regen_zones:
            if zone.postcodes:
                regen_postcodes.extend(
                    [p.strip().upper() for p in zone.postcodes.split(",") if p.strip()]
                )
        if regen_postcodes:
            conditions = [Listing.postcode.ilike(f"{rp}%") for rp in regen_postcodes]
            base_stmt = base_stmt.where(or_(*conditions))

    # Count total
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Paginate
    offset = (page - 1) * page_size
    paginated_stmt = (
        base_stmt
        .order_by(Listing.first_seen_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(paginated_stmt)
    listings = result.scalars().all()

    # Fetch latest scores for fetched listings
    listing_ids = [l.id for l in listings]
    scores_map: dict = {}
    if listing_ids:
        scores_stmt = (
            select(ListingScore)
            .join(
                latest_score_subq,
                and_(
                    ListingScore.listing_id == latest_score_subq.c.listing_id,
                    ListingScore.scored_at == latest_score_subq.c.max_scored_at,
                ),
            )
            .where(ListingScore.listing_id.in_(listing_ids))
        )
        scores_result = await db.execute(scores_stmt)
        for score in scores_result.scalars().all():
            scores_map[score.listing_id] = score.overall_score

    # Build response
    items = []
    for listing in listings:
        out = ListingOut.model_validate(listing)
        out.overall_score = scores_map.get(listing.id)
        items.append(out.model_dump())

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "items": items,
    }


@router.get("/{listing_id}", response_model=ListingDetail)
async def get_listing(
    listing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a single listing with full score history and nearby planning count."""
    result = await db.execute(
        select(Listing)
        .options(selectinload(Listing.scores))
        .where(Listing.id == listing_id)
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Count nearby planning applications (same postcode prefix)
    prefix = listing.postcode.split(" ")[0] if listing.postcode else ""
    planning_count_result = await db.execute(
        select(func.count()).where(
            PlanningApplication.postcode.ilike(f"{prefix}%")
        )
    )
    nearby_planning_count = planning_count_result.scalar_one()

    out = ListingDetail.model_validate(listing)
    out.nearby_planning_count = nearby_planning_count
    if listing.scores:
        latest = max(listing.scores, key=lambda s: s.scored_at)
        out.overall_score = latest.overall_score
    return out


@router.post("", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
async def create_listing(
    listing_in: ListingCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Create a new listing (admin only). Automatically scores on creation."""
    now = datetime.utcnow()
    listing = Listing(
        **listing_in.model_dump(),
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(listing)
    await db.flush()
    await db.refresh(listing)

    # Auto-score
    await _score_and_save(db, listing)
    await db.refresh(listing)
    return listing


@router.put("/{listing_id}", response_model=ListingOut)
async def update_listing(
    listing_id: uuid.UUID,
    listing_in: ListingUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Update a listing (admin only). Rescores automatically."""
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    update_data = listing_in.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(listing, key, value)
    listing.last_seen_at = datetime.utcnow()

    await db.flush()
    await _score_and_save(db, listing)
    await db.refresh(listing)
    return listing


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(
    listing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Delete a listing (admin only)."""
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    await db.delete(listing)


@router.post("/{listing_id}/flag", response_model=ListingOut)
async def flag_listing(
    listing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Toggle the flagged state of a listing."""
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    listing.is_flagged = not listing.is_flagged
    await db.flush()
    await db.refresh(listing)
    return listing


@router.post("/{listing_id}/notes", response_model=ListingOut)
async def update_notes(
    listing_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update notes on a listing. Body: {notes: str}"""
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    listing.notes = body.get("notes", "")
    await db.flush()
    await db.refresh(listing)
    return listing


# ---------------------------------------------------------------------------
# Internal scoring helper
# ---------------------------------------------------------------------------

async def _score_and_save(db: AsyncSession, listing: Listing) -> ListingScore:
    """Run the scoring engine and persist the result."""
    comparables = await match_comparables(
        db,
        postcode=listing.postcode,
        property_type=listing.property_type,
        bedrooms=listing.bedrooms,
        listing_lat=listing.latitude,
        listing_lng=listing.longitude,
    )
    nearby_planning = await get_nearby_planning(
        db,
        postcode=listing.postcode,
        listing_lat=listing.latitude,
        listing_lng=listing.longitude,
    )
    regen_result = await db.execute(select(RegenerationZone))
    regen_zones = regen_result.scalars().all()

    result = score_listing(listing, comparables, nearby_planning, regen_zones)

    score = ListingScore(
        listing_id=listing.id,
        overall_score=result.overall_score,
        bmv_score=result.bmv_score,
        distress_score=result.distress_score,
        momentum_score=result.momentum_score,
        planning_score=result.planning_score,
        regeneration_score=result.regeneration_score,
        confidence_score=result.confidence_score,
        estimated_fair_value=result.estimated_fair_value,
        avg_comparable_price=result.avg_comparable_price,
        discount_pct=result.discount_pct,
        score_drivers=result.score_drivers,
        scored_at=datetime.utcnow(),
    )
    db.add(score)
    await db.flush()
    return score
