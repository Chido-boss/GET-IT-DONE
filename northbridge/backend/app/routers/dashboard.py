from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_db
from app.models.listing import Listing
from app.models.planning import PlanningApplication
from app.models.alert import AlertEvent
from app.models.score import ListingScore
from app.auth.utils import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Return key platform statistics for the dashboard.
    {
        total_listings, high_score_count, planning_count,
        alerts_this_week, avg_score, top_councils
    }
    """

    # Total active listings
    total_result = await db.execute(
        select(func.count()).where(Listing.status == "active")
    )
    total_listings = total_result.scalar_one()

    # High score listings (score >= 70)
    # Subquery: latest score per listing
    latest_score_subq = (
        select(
            ListingScore.listing_id,
            func.max(ListingScore.scored_at).label("max_scored_at"),
        )
        .group_by(ListingScore.listing_id)
        .subquery()
    )

    high_score_result = await db.execute(
        select(func.count())
        .select_from(ListingScore)
        .join(
            latest_score_subq,
            and_(
                ListingScore.listing_id == latest_score_subq.c.listing_id,
                ListingScore.scored_at == latest_score_subq.c.max_scored_at,
            ),
        )
        .where(ListingScore.overall_score >= 70.0)
    )
    high_score_count = high_score_result.scalar_one()

    # Planning applications count
    planning_result = await db.execute(select(func.count(PlanningApplication.id)))
    planning_count = planning_result.scalar_one()

    # Alert events this week
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    alert_result = await db.execute(
        select(func.count()).where(AlertEvent.created_at >= one_week_ago)
    )
    alerts_this_week = alert_result.scalar_one()

    # Average score (across latest scores)
    avg_score_result = await db.execute(
        select(func.avg(ListingScore.overall_score))
        .join(
            latest_score_subq,
            and_(
                ListingScore.listing_id == latest_score_subq.c.listing_id,
                ListingScore.scored_at == latest_score_subq.c.max_scored_at,
            ),
        )
    )
    avg_score_raw = avg_score_result.scalar_one()
    avg_score = round(float(avg_score_raw), 1) if avg_score_raw else 0.0

    # Top councils by listing count
    top_councils_result = await db.execute(
        select(Listing.council, func.count(Listing.id).label("count"))
        .where(Listing.status == "active", Listing.council.isnot(None))
        .group_by(Listing.council)
        .order_by(func.count(Listing.id).desc())
        .limit(5)
    )
    top_councils = [
        {"council": row.council, "count": row.count}
        for row in top_councils_result.fetchall()
    ]

    return {
        "total_listings": total_listings,
        "high_score_count": high_score_count,
        "planning_count": planning_count,
        "alerts_this_week": alerts_this_week,
        "avg_score": avg_score,
        "top_councils": top_councils,
    }
