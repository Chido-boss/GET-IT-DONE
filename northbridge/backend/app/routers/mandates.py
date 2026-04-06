"""Investor mandate — define criteria, get match scores per deal."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.auth.utils import get_current_user
from app.models.user import User
from app.models.mandate import InvestorMandate
from app.models.deal import Deal

router = APIRouter(prefix="/mandates", tags=["mandates"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class MandateIn(BaseModel):
    name: str = "My Investment Mandate"
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    preferred_strategies: Optional[list] = None
    min_roi: Optional[float] = None
    min_yield: Optional[float] = None
    max_risk_score: Optional[int] = 70
    min_conviction_score: Optional[int] = 50
    preferred_councils: Optional[list] = None
    regen_zones_only: bool = False
    planning_required: Optional[bool] = None
    max_refurb_level: Optional[str] = None
    min_discount_pct: Optional[float] = None
    alerts_enabled: bool = True
    alert_email: bool = True


class MandateOut(BaseModel):
    id: str
    name: str
    min_price: Optional[int]
    max_price: Optional[int]
    preferred_strategies: Optional[list]
    min_roi: Optional[float]
    min_yield: Optional[float]
    max_risk_score: Optional[int]
    min_conviction_score: Optional[int]
    preferred_councils: Optional[list]
    regen_zones_only: bool
    planning_required: Optional[bool]
    max_refurb_level: Optional[str]
    min_discount_pct: Optional[float]
    alerts_enabled: bool
    alert_email: bool
    is_active: bool

    class Config:
        from_attributes = True


class DealMatchOut(BaseModel):
    deal_id: str
    title: str
    match_score: float      # 0–100
    match_label: str        # "Perfect Match" | "Strong Match" | "Partial Match"
    match_reasons: list     # ["ROI meets mandate", "Strategy match", ...]
    match_gaps: list        # ["Price above max", ...]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/my", response_model=Optional[MandateOut])
async def get_my_mandate(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InvestorMandate).where(
            InvestorMandate.user_id == str(current_user.id),
            InvestorMandate.is_active == True,
        ).limit(1)
    )
    return result.scalar_one_or_none()


@router.post("/my", response_model=MandateOut)
async def upsert_mandate(
    body: MandateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Deactivate existing
    existing = await db.execute(
        select(InvestorMandate).where(
            InvestorMandate.user_id == str(current_user.id),
            InvestorMandate.is_active == True,
        )
    )
    for m in existing.scalars().all():
        m.is_active = False

    mandate = InvestorMandate(
        user_id=str(current_user.id),
        **body.model_dump(),
    )
    db.add(mandate)
    await db.commit()
    await db.refresh(mandate)
    return mandate


@router.get("/match-deals", response_model=list[DealMatchOut])
async def match_deals_to_mandate(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mandate_result = await db.execute(
        select(InvestorMandate).where(
            InvestorMandate.user_id == str(current_user.id),
            InvestorMandate.is_active == True,
        ).limit(1)
    )
    mandate = mandate_result.scalar_one_or_none()
    if not mandate:
        raise HTTPException(status_code=404, detail="No active mandate. Set your investment criteria first.")

    deals_result = await db.execute(
        select(Deal).where(Deal.status == "active").limit(50)
    )
    deals = deals_result.scalars().all()

    matches = []
    for deal in deals:
        match = _score_match(deal, mandate)
        if match["score"] >= 40:
            matches.append(DealMatchOut(
                deal_id=str(deal.id),
                title=deal.title,
                match_score=match["score"],
                match_label=match["label"],
                match_reasons=match["reasons"],
                match_gaps=match["gaps"],
            ))

    return sorted(matches, key=lambda x: x.match_score, reverse=True)


def _score_match(deal: Deal, mandate: InvestorMandate) -> dict:
    score = 0.0
    reasons = []
    gaps = []
    max_pts = 0

    def add(pts, condition, reason, gap=None):
        nonlocal score, max_pts
        max_pts += pts
        if condition:
            score += pts
            reasons.append(reason)
        elif gap:
            gaps.append(gap)

    add(25, not mandate.min_roi or (deal.roi and deal.roi >= mandate.min_roi),
        f"ROI {deal.roi:.0f}% meets mandate minimum" if deal.roi else "ROI meets mandate",
        f"ROI below mandate minimum of {mandate.min_roi}%")

    add(20, not mandate.preferred_strategies or deal.strategy in (mandate.preferred_strategies or []),
        f"{deal.strategy.replace('_',' ').title()} matches preferred strategy",
        f"Strategy {deal.strategy} not in preferred list")

    add(15, not mandate.max_price or (deal.purchase_price and deal.purchase_price <= mandate.max_price),
        "Price within budget",
        f"Price £{deal.purchase_price:,} exceeds budget maximum")

    add(15, not mandate.min_price or (deal.purchase_price and deal.purchase_price >= mandate.min_price),
        "Price above minimum threshold",
        f"Price below mandate minimum of £{mandate.min_price:,}")

    add(10, not mandate.min_conviction_score or (deal.overall_score and deal.overall_score >= mandate.min_conviction_score),
        f"Conviction score {deal.overall_score:.0f} meets mandate threshold",
        f"Conviction score below mandate minimum of {mandate.min_conviction_score}")

    add(10, not mandate.regen_zones_only or deal.near_regen_zone,
        "Located in regeneration zone",
        "Not in a regeneration zone (mandate preference)")

    add(5, not mandate.min_discount_pct or _calc_discount(deal) >= mandate.min_discount_pct,
        f"Discount meets mandate minimum",
        f"Discount below mandate minimum of {mandate.min_discount_pct}%")

    pct = (score / max_pts * 100) if max_pts > 0 else 0
    label = "Perfect Match" if pct >= 85 else "Strong Match" if pct >= 65 else "Partial Match"
    return {"score": round(pct, 1), "label": label, "reasons": reasons, "gaps": gaps}


def _calc_discount(deal: Deal) -> float:
    ev = deal.gdv or deal.estimated_value
    if ev and deal.purchase_price and ev > 0:
        return ((ev - deal.purchase_price) / ev) * 100
    return 0.0
