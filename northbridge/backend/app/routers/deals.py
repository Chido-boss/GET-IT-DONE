import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.database import get_db
from app.models.deal import Deal
from app.schemas.deal import DealOut, ScoreRequest, ScoreResponse
from app.services.deal_scoring import score_deal, rank_deals
from app.auth.utils import get_current_user
from app.models.user import User

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("", response_model=dict)
async def list_deals(
    strategy: Optional[str] = Query(None),
    min_roi: Optional[float] = Query(None),
    max_price: Optional[int] = Query(None),
    min_price: Optional[int] = Query(None),
    council: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search address/council/strategy"),
    is_undervalued: Optional[bool] = Query(None),
    is_high_roi: Optional[bool] = Query(None),
    has_planning_upside: Optional[bool] = Query(None),
    min_score: Optional[float] = Query(None),
    tier: Optional[str] = Query(None, description="S|A|B|C"),
    min_discount: Optional[float] = Query(None),
    status: Optional[str] = Query(None, description="active|under_offer|acquired|completed|passed"),
    sort: Optional[str] = Query("score", description="score|roi|discount|price|created"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Deal)

    if strategy:
        q = q.where(Deal.strategy == strategy)
    if min_roi is not None:
        q = q.where(
            or_(Deal.roi_pct >= min_roi, Deal.roi >= min_roi)
        )
    if max_price is not None:
        q = q.where(Deal.purchase_price <= max_price)
    if min_price is not None:
        q = q.where(Deal.purchase_price >= min_price)
    if council:
        q = q.where(Deal.council.ilike(f"%{council}%"))
    if search:
        term = f"%{search}%"
        q = q.where(
            or_(
                Deal.address.ilike(term),
                Deal.council.ilike(term),
                Deal.strategy.ilike(term),
                Deal.title.ilike(term),
            )
        )
    if is_undervalued is not None:
        q = q.where(Deal.is_undervalued == is_undervalued)
    if is_high_roi is not None:
        q = q.where(Deal.is_high_roi == is_high_roi)
    if has_planning_upside is not None:
        q = q.where(Deal.has_planning_upside == has_planning_upside)
    if min_score is not None:
        q = q.where(Deal.overall_score >= min_score)
    if tier:
        q = q.where(Deal.tier == tier)
    if min_discount is not None:
        q = q.where(Deal.discount_pct >= min_discount)
    if status:
        q = q.where(Deal.status == status)
    else:
        q = q.where(Deal.status != "passed")

    # Sort
    if sort == "roi":
        q = q.order_by(
            Deal.roi_pct.desc().nulls_last(),
            Deal.roi.desc().nulls_last(),
        )
    elif sort == "discount":
        q = q.order_by(Deal.discount_pct.desc().nulls_last())
    elif sort == "price":
        q = q.order_by(Deal.purchase_price.asc())
    elif sort == "created":
        q = q.order_by(Deal.created_at.desc())
    else:
        q = q.order_by(Deal.overall_score.desc().nulls_last())

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar() or 0

    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    deals = result.scalars().all()

    deals_data = [_deal_to_dict(d) for d in deals]
    ranked = rank_deals(deals_data)

    # Build KPI summary for dashboard
    all_for_kpi_result = await db.execute(
        select(Deal).where(Deal.status != "passed").limit(500)
    )
    all_for_kpi = all_for_kpi_result.scalars().all()
    avg_score = 0.0
    if all_for_kpi:
        scored = [d.overall_score for d in all_for_kpi if d.overall_score is not None]
        avg_score = round(sum(scored) / len(scored), 1) if scored else 0.0

    strategy_counts: dict[str, int] = {}
    for d in all_for_kpi:
        strategy_counts[d.strategy] = strategy_counts.get(d.strategy, 0) + 1
    top_strategy = max(strategy_counts, key=lambda k: strategy_counts[k]) if strategy_counts else "—"

    councils = set(d.council for d in all_for_kpi if d.council)

    return {
        "items": ranked,
        "total": total,
        "kpis": {
            "active_deals": len(all_for_kpi),
            "avg_score": avg_score,
            "top_strategy": top_strategy,
            "councils_covered": len(councils),
        },
    }


@router.get("/pipeline", response_model=dict)
async def get_pipeline(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dashboard pipeline summary."""
    result = await db.execute(select(Deal))
    all_deals = result.scalars().all()

    pipeline: dict[str, list] = {}
    for status in ["active", "under_offer", "acquired", "completed", "passed"]:
        pipeline[status] = [_deal_to_dict(d) for d in all_deals if d.status == status]

    total_profit = sum(d.profit or 0 for d in all_deals if d.status == "completed")
    avg_roi = 0.0
    roi_deals = [d.roi_pct or d.roi for d in all_deals if (d.roi_pct or d.roi) is not None]
    if roi_deals:
        avg_roi = round(sum(roi_deals) / len(roi_deals), 1)

    top_deals = sorted(
        [_deal_to_dict(d) for d in all_deals if d.status == "active"],
        key=lambda x: x.get("overall_score") or 0,
        reverse=True
    )[:5]

    strategy_counts: dict[str, int] = {}
    for d in all_deals:
        strategy_counts[d.strategy] = strategy_counts.get(d.strategy, 0) + 1

    roi_distribution = _roi_buckets(all_deals)

    return {
        "pipeline": {k: len(v) for k, v in pipeline.items()},
        "total_completed_profit": total_profit,
        "avg_roi": avg_roi,
        "top_deals": top_deals,
        "strategy_breakdown": strategy_counts,
        "roi_distribution": roi_distribution,
        "total_deals": len(all_deals),
        "high_score_count": sum(1 for d in all_deals if (d.overall_score or 0) >= 65),
    }


@router.get("/{deal_id}", response_model=DealOut)
async def get_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(404, "Deal not found")
    d = _deal_to_dict(deal)
    return d


@router.post("/score", response_model=ScoreResponse)
async def score_deal_endpoint(
    req: ScoreRequest,
    current_user: User = Depends(get_current_user),
):
    """Score any deal without saving it."""
    result = score_deal(
        purchase_price=req.purchase_price,
        strategy=req.strategy,
        estimated_value=req.estimated_value,
        gdv=req.gdv,
        refurb_cost=req.refurb_cost or 0,
        other_costs=req.other_costs or 0,
        description=req.description or "",
        postcode=req.postcode or "",
        bedrooms=req.bedrooms,
        days_on_market=req.days_on_market,
        price_reductions=req.price_reductions,
        annual_yield_pct=req.annual_yield_pct,
    )
    return ScoreResponse(
        overall_score=result.overall_score,
        score_roi=result.score_roi,
        score_discount=result.score_discount,
        score_risk=result.score_risk,
        score_liquidity=result.score_liquidity,
        tier=result.tier,
        confidence=result.confidence,
        risk_level=result.risk_level,
        roi_score=result.roi_score,
        risk_score=result.risk_score,
        planning_uplift_score=result.planning_uplift_score,
        market_score=result.market_score,
        gross_profit=result.gross_profit,
        net_profit=result.net_profit,
        profit=result.profit,
        roi=result.roi,
        roi_pct=result.roi_pct,
        discount_pct=result.discount_pct,
        is_undervalued=result.is_undervalued,
        is_high_roi=result.is_high_roi,
        has_planning_upside=result.has_planning_upside,
        score_drivers=result.score_drivers,
    )


def _deal_to_dict(d: Deal) -> dict:
    roi = d.roi_pct if d.roi_pct is not None else d.roi
    annual_yield = d.annual_yield_pct if d.annual_yield_pct is not None else d.annual_yield
    net_profit = d.net_profit if d.net_profit is not None else d.profit
    discount = d.discount_pct

    return {
        "id": str(d.id),
        "title": d.title,
        "address": d.address,
        "postcode": d.postcode,
        "council": d.council,
        "property_type": d.property_type,
        "bedrooms": d.bedrooms,
        "strategy": d.strategy,
        "exit_strategy": d.exit_strategy,
        "source": d.source,
        "days_on_market": d.days_on_market,
        "price_reductions": d.price_reductions,
        "purchase_price": d.purchase_price,
        "asking_price": d.asking_price or d.purchase_price,
        "estimated_value": d.estimated_value,
        "gdv": d.gdv,
        "refurb_cost": d.refurb_cost,
        "other_costs": d.other_costs,
        "total_cost": d.total_cost,
        "gross_profit": d.gross_profit,
        "net_profit": net_profit,
        "profit": net_profit,
        "roi": roi,
        "roi_pct": roi,
        "discount_pct": discount,
        "annual_yield": annual_yield,
        "annual_yield_pct": annual_yield,
        "monthly_cashflow": d.monthly_cashflow,
        "is_undervalued": d.is_undervalued,
        "has_planning_upside": d.has_planning_upside,
        "is_high_roi": d.is_high_roi,
        "is_distressed": d.is_distressed,
        "near_regen_zone": d.near_regen_zone,
        # Component scores
        "score_roi": d.score_roi,
        "score_discount": d.score_discount,
        "score_risk": d.score_risk,
        "score_liquidity": d.score_liquidity,
        # Overall & classification
        "overall_score": d.overall_score,
        "tier": d.tier,
        "confidence": d.confidence,
        "risk_level": d.risk_level,
        # Legacy
        "roi_score": d.roi_score or d.score_roi,
        "risk_score": d.risk_score,
        "planning_uplift_score": d.planning_uplift_score,
        "market_score": d.market_score or d.score_discount,
        "score_drivers": d.score_drivers,
        # Context
        "tags": d.tags or [],
        "summary": d.summary,
        "risk_notes": d.risk_notes,
        "opportunity_notes": d.opportunity_notes,
        "description": d.description,
        "source_url": d.source_url,
        "status": d.status,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def _roi_buckets(deals) -> list[dict]:
    buckets = [
        {"label": "<0%", "min": None, "max": 0, "count": 0},
        {"label": "0–10%", "min": 0, "max": 10, "count": 0},
        {"label": "10–20%", "min": 10, "max": 20, "count": 0},
        {"label": "20–30%", "min": 20, "max": 30, "count": 0},
        {"label": "30%+", "min": 30, "max": None, "count": 0},
    ]
    for d in deals:
        roi = d.roi_pct if d.roi_pct is not None else d.roi
        if roi is None:
            continue
        for b in buckets:
            lo = b["min"] if b["min"] is not None else float("-inf")
            hi = b["max"] if b["max"] is not None else float("inf")
            if lo <= roi < hi:
                b["count"] += 1
                break
    return [{"label": b["label"], "count": b["count"]} for b in buckets]
