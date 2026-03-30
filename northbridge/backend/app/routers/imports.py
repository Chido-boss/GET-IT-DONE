from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.import_log import ImportLog
from app.models.listing import Listing
from app.models.comparable import ComparableSale
from app.models.planning import PlanningApplication
from app.models.score import ListingScore
from app.models.regen_zone import RegenerationZone
from app.models.user import User
from app.schemas.import_log import ImportLogOut
from app.auth.utils import get_current_user, get_current_admin
from app.services.ingestion.csv_import import (
    parse_listings_csv,
    parse_comparables_csv,
    parse_planning_csv,
    _detect_planning_uplift_signals,
    _calculate_planning_uplift_score,
)
from app.services.scoring import score_listing
from app.services.comparables import match_comparables, get_nearby_planning

router = APIRouter(prefix="/imports", tags=["imports"])


# ---------------------------------------------------------------------------
# Listings import
# ---------------------------------------------------------------------------

@router.post("/listings", response_model=ImportLogOut, status_code=status.HTTP_201_CREATED)
async def import_listings(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Upload a listings CSV file. Creates/updates listings and auto-scores them."""
    content = await file.read()

    log = ImportLog(
        user_id=current_user.id,
        import_type="listings",
        filename=file.filename,
        status="processing",
    )
    db.add(log)
    await db.flush()

    errors: List[str] = []
    rows_processed = 0
    rows_imported = 0
    rows_failed = 0

    try:
        records = parse_listings_csv(content)
        rows_processed = len(records)

        for record in records:
            try:
                # Upsert by source + source_id if available
                existing = None
                if record.get("source") and record.get("source_id"):
                    result = await db.execute(
                        select(Listing).where(
                            Listing.source == record["source"],
                            Listing.source_id == record["source_id"],
                        )
                    )
                    existing = result.scalar_one_or_none()

                now = datetime.utcnow()
                if existing:
                    # Update price history
                    if record.get("asking_price") and record["asking_price"] != existing.asking_price:
                        existing.previous_price = existing.asking_price
                        existing.price_reduction_count = (existing.price_reduction_count or 0) + 1
                    for key, value in record.items():
                        if key not in ("source", "source_id", "previous_price", "price_reduction_count"):
                            if value is not None:
                                setattr(existing, key, value)
                    existing.last_seen_at = now
                    listing = existing
                else:
                    listing = Listing(**record, first_seen_at=now, last_seen_at=now)
                    db.add(listing)

                await db.flush()

                # Auto-score
                comparables = await match_comparables(
                    db, listing.postcode, listing.property_type, listing.bedrooms,
                    listing.latitude, listing.longitude,
                )
                nearby_planning = await get_nearby_planning(
                    db, listing.postcode, listing.latitude, listing.longitude,
                )
                regen_result = await db.execute(select(RegenerationZone))
                regen_zones = regen_result.scalars().all()

                score_result = score_listing(listing, comparables, nearby_planning, regen_zones)
                score = ListingScore(
                    listing_id=listing.id,
                    overall_score=score_result.overall_score,
                    bmv_score=score_result.bmv_score,
                    distress_score=score_result.distress_score,
                    momentum_score=score_result.momentum_score,
                    planning_score=score_result.planning_score,
                    regeneration_score=score_result.regeneration_score,
                    confidence_score=score_result.confidence_score,
                    estimated_fair_value=score_result.estimated_fair_value,
                    avg_comparable_price=score_result.avg_comparable_price,
                    discount_pct=score_result.discount_pct,
                    score_drivers=score_result.score_drivers,
                    scored_at=now,
                )
                db.add(score)
                await db.flush()
                rows_imported += 1

            except Exception as e:
                rows_failed += 1
                errors.append(str(e))

        log.status = "complete"
    except Exception as e:
        log.status = "failed"
        errors.append(f"Parse error: {e}")

    log.rows_processed = rows_processed
    log.rows_imported = rows_imported
    log.rows_failed = rows_failed
    log.errors = errors if errors else None
    log.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(log)
    return log


# ---------------------------------------------------------------------------
# Comparables import
# ---------------------------------------------------------------------------

@router.post("/comparables", response_model=ImportLogOut, status_code=status.HTTP_201_CREATED)
async def import_comparables(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Upload a Land Registry Price Paid Data CSV."""
    content = await file.read()

    log = ImportLog(
        user_id=current_user.id,
        import_type="comparables",
        filename=file.filename,
        status="processing",
    )
    db.add(log)
    await db.flush()

    errors: List[str] = []
    rows_processed = 0
    rows_imported = 0
    rows_failed = 0

    try:
        records = parse_comparables_csv(content)
        rows_processed = len(records)

        for record in records:
            try:
                # Skip duplicates by transaction_id
                if record.get("transaction_id"):
                    existing = await db.execute(
                        select(ComparableSale).where(
                            ComparableSale.transaction_id == record["transaction_id"]
                        )
                    )
                    if existing.scalar_one_or_none():
                        rows_imported += 1
                        continue

                comp = ComparableSale(**record)
                db.add(comp)
                await db.flush()
                rows_imported += 1
            except Exception as e:
                rows_failed += 1
                errors.append(str(e))

        log.status = "complete"
    except Exception as e:
        log.status = "failed"
        errors.append(f"Parse error: {e}")

    log.rows_processed = rows_processed
    log.rows_imported = rows_imported
    log.rows_failed = rows_failed
    log.errors = errors if errors else None
    log.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(log)
    return log


# ---------------------------------------------------------------------------
# Planning import
# ---------------------------------------------------------------------------

@router.post("/planning", response_model=ImportLogOut, status_code=status.HTTP_201_CREATED)
async def import_planning(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Upload a planning applications CSV file."""
    content = await file.read()

    log = ImportLog(
        user_id=current_user.id,
        import_type="planning",
        filename=file.filename,
        status="processing",
    )
    db.add(log)
    await db.flush()

    errors: List[str] = []
    rows_processed = 0
    rows_imported = 0
    rows_failed = 0

    try:
        records = parse_planning_csv(content)
        rows_processed = len(records)

        for record in records:
            try:
                # Skip duplicates
                existing = await db.execute(
                    select(PlanningApplication).where(
                        PlanningApplication.council == record["council"],
                        PlanningApplication.application_reference == record["application_reference"],
                    )
                )
                if existing.scalar_one_or_none():
                    rows_imported += 1
                    continue

                app = PlanningApplication(**record)
                db.add(app)
                await db.flush()
                rows_imported += 1
            except Exception as e:
                rows_failed += 1
                errors.append(str(e))

        log.status = "complete"
    except Exception as e:
        log.status = "failed"
        errors.append(f"Parse error: {e}")

    log.rows_processed = rows_processed
    log.rows_imported = rows_imported
    log.rows_failed = rows_failed
    log.errors = errors if errors else None
    log.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(log)
    return log


# ---------------------------------------------------------------------------
# Import history
# ---------------------------------------------------------------------------

@router.get("", response_model=List[ImportLogOut])
async def list_imports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List import history. Admins see all; regular users see their own."""
    stmt = select(ImportLog)
    if not current_user.is_admin:
        stmt = stmt.where(ImportLog.user_id == current_user.id)
    stmt = stmt.order_by(ImportLog.created_at.desc()).limit(100)
    result = await db.execute(stmt)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Rescore all listings
# ---------------------------------------------------------------------------

@router.post("/rescore", status_code=status.HTTP_202_ACCEPTED)
async def rescore_all(
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Trigger rescoring of all active listings (admin only)."""
    result = await db.execute(
        select(Listing).where(Listing.status == "active")
    )
    listings = result.scalars().all()

    regen_result = await db.execute(select(RegenerationZone))
    regen_zones = regen_result.scalars().all()

    rescored = 0
    now = datetime.utcnow()

    for listing in listings:
        try:
            comparables = await match_comparables(
                db, listing.postcode, listing.property_type, listing.bedrooms,
                listing.latitude, listing.longitude,
            )
            nearby_planning = await get_nearby_planning(
                db, listing.postcode, listing.latitude, listing.longitude,
            )
            score_result = score_listing(listing, comparables, nearby_planning, regen_zones)

            score = ListingScore(
                listing_id=listing.id,
                overall_score=score_result.overall_score,
                bmv_score=score_result.bmv_score,
                distress_score=score_result.distress_score,
                momentum_score=score_result.momentum_score,
                planning_score=score_result.planning_score,
                regeneration_score=score_result.regeneration_score,
                confidence_score=score_result.confidence_score,
                estimated_fair_value=score_result.estimated_fair_value,
                avg_comparable_price=score_result.avg_comparable_price,
                discount_pct=score_result.discount_pct,
                score_drivers=score_result.score_drivers,
                scored_at=now,
            )
            db.add(score)
            rescored += 1
        except Exception:
            pass

    await db.flush()
    return {"message": f"Rescored {rescored} listings", "count": rescored}
