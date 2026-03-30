"""
Deal scoring engine — full financial + intelligence scoring for deals.
Scores: ROI, risk, planning uplift, market position.
Flags: undervalued, high ROI, planning upside, distressed.
"""
from dataclasses import dataclass, field
from typing import Optional


STRATEGY_RISK = {
    "flip": 45,
    "brr": 40,
    "brrr": 40,
    "hmo": 50,
    "btl": 30,
    "conversion": 60,
    "planning_uplift": 65,
    "auction": 55,
}

PLANNING_KEYWORDS = [
    "change of use", "prior approval", "conversion", "planning potential",
    "planning permission", "permitted development", "class ma", "development opportunity",
    "planning uplift", "outline planning", "barn conversion", "agricultural",
    "commercial to residential", "office to residential",
]

DISTRESS_KEYWORDS = [
    "chain free", "no chain", "motivated seller", "cash buyers", "sold as seen",
    "probate", "executor", "repossession", "vacant possession", "quick sale",
    "price reduction", "reduced", "priced to sell",
]

NE_REGEN_POSTCODES = [
    "NE1", "NE8", "NE9", "NE10", "SR1", "SR2", "TS6", "TS10", "TS3",
    "NE33", "NE34", "TS24", "TS25", "DH1", "NE24", "NE25",
]


@dataclass
class DealScoreResult:
    overall_score: float
    roi_score: float
    risk_score: float
    planning_uplift_score: float
    market_score: float
    profit: Optional[int]
    roi: Optional[float]
    total_cost: int
    is_undervalued: bool
    is_high_roi: bool
    has_planning_upside: bool
    is_distressed: bool
    near_regen_zone: bool
    score_drivers: list = field(default_factory=list)


def score_deal(
    purchase_price: int,
    strategy: str,
    estimated_value: Optional[int] = None,
    gdv: Optional[int] = None,
    refurb_cost: int = 0,
    other_costs: int = 0,
    description: str = "",
    postcode: str = "",
    bedrooms: Optional[int] = None,
) -> DealScoreResult:
    drivers = []
    desc = (description or "").lower()
    pc_prefix = (postcode or "").strip().upper().split(" ")[0]

    # ── Costs & profit ───────────────────────────────────────────────────────
    stamp_duty = _stamp_duty(purchase_price)
    legal = 3_000
    auto_costs = stamp_duty + legal + (other_costs or 0)
    total_cost = purchase_price + (refurb_cost or 0) + auto_costs

    exit_value = gdv or estimated_value
    profit = (exit_value - total_cost) if exit_value else None
    roi = round((profit / total_cost) * 100, 1) if (profit and total_cost) else None

    # ── ROI score (0-100) ────────────────────────────────────────────────────
    roi_score = 0.0
    if roi is not None:
        if roi >= 30:
            roi_score = 95
            drivers.append({"icon": "🚀", "label": f"Exceptional ROI: {roi:.0f}%", "impact": 95})
        elif roi >= 20:
            roi_score = 80
            drivers.append({"icon": "📈", "label": f"Strong ROI: {roi:.0f}%", "impact": 80})
        elif roi >= 12:
            roi_score = 60
            drivers.append({"icon": "📊", "label": f"Solid ROI: {roi:.0f}%", "impact": 60})
        elif roi >= 6:
            roi_score = 35
            drivers.append({"icon": "📉", "label": f"Modest ROI: {roi:.0f}%", "impact": 35})
        else:
            roi_score = 10
            drivers.append({"icon": "⚠️", "label": f"Low ROI: {roi:.0f}% — review costs", "impact": 10})

    # ── Market / BMV score (0-100) ───────────────────────────────────────────
    market_score = 0.0
    is_undervalued = False
    if exit_value and purchase_price:
        discount = ((exit_value - purchase_price) / exit_value) * 100
        if discount >= 25:
            market_score = 90
            is_undervalued = True
            drivers.append({"icon": "🔻", "label": f"Buying {discount:.0f}% below estimated value", "impact": 90})
        elif discount >= 15:
            market_score = 70
            is_undervalued = True
            drivers.append({"icon": "📉", "label": f"{discount:.0f}% below estimated value — BMV", "impact": 70})
        elif discount >= 8:
            market_score = 45
            is_undervalued = True
            drivers.append({"icon": "📊", "label": f"{discount:.0f}% below estimated value", "impact": 45})
        elif discount > 0:
            market_score = 20
        else:
            market_score = 5
            drivers.append({"icon": "⚠️", "label": "Paying at or above estimated value", "impact": 5})

    # ── Planning uplift score (0-100) ────────────────────────────────────────
    planning_uplift_score = 0.0
    has_planning_upside = False
    planning_hits = [kw for kw in PLANNING_KEYWORDS if kw in desc]
    if planning_hits:
        planning_uplift_score = min(len(planning_hits) * 20, 85)
        has_planning_upside = True
        drivers.append({"icon": "🏗️", "label": f"Planning signals: {', '.join(planning_hits[:2])}", "impact": planning_uplift_score})
    if strategy in ("planning_uplift", "conversion"):
        planning_uplift_score = max(planning_uplift_score, 70)
        has_planning_upside = True

    # ── Distress signals ─────────────────────────────────────────────────────
    is_distressed = False
    distress_hits = [kw for kw in DISTRESS_KEYWORDS if kw in desc]
    if distress_hits:
        is_distressed = True
        drivers.append({"icon": "⚠️", "label": f"Distress signals: {', '.join(distress_hits[:2])}", "impact": 40})

    # ── Regen zone proximity ─────────────────────────────────────────────────
    near_regen_zone = pc_prefix in NE_REGEN_POSTCODES
    if near_regen_zone:
        drivers.append({"icon": "🔄", "label": f"Located in/near active NE regeneration zone ({pc_prefix})", "impact": 55})

    # ── Risk score (0-100, higher = riskier) ────────────────────────────────
    base_risk = STRATEGY_RISK.get(strategy, 50)
    risk_score = float(base_risk)
    if refurb_cost and purchase_price and refurb_cost > purchase_price * 0.20:
        risk_score = min(risk_score + 15, 95)
        drivers.append({"icon": "⚡", "label": f"Heavy refurb (£{refurb_cost:,}) increases risk", "impact": 0})
    if roi and roi < 10:
        risk_score = min(risk_score + 10, 95)

    # ── Overall score ────────────────────────────────────────────────────────
    overall = (
        roi_score * 0.35 +
        market_score * 0.30 +
        planning_uplift_score * 0.20 +
        (100 - risk_score) * 0.15
    )
    overall = round(min(overall, 100), 1)

    is_high_roi = bool(roi and roi >= 20)

    # Sort drivers by impact
    drivers.sort(key=lambda d: d.get("impact", 0), reverse=True)

    return DealScoreResult(
        overall_score=overall,
        roi_score=round(roi_score, 1),
        risk_score=round(risk_score, 1),
        planning_uplift_score=round(planning_uplift_score, 1),
        market_score=round(market_score, 1),
        profit=profit,
        roi=roi,
        total_cost=total_cost,
        is_undervalued=is_undervalued,
        is_high_roi=is_high_roi,
        has_planning_upside=has_planning_upside,
        is_distressed=is_distressed,
        near_regen_zone=near_regen_zone,
        score_drivers=drivers[:5],
    )


def _stamp_duty(price: int) -> int:
    """Additional dwelling SDLT (3% surcharge for investment property)."""
    if price <= 250_000:
        return int(price * 0.03)
    elif price <= 925_000:
        return int(250_000 * 0.03 + (price - 250_000) * 0.08)
    return int(250_000 * 0.03 + 675_000 * 0.08 + (price - 925_000) * 0.13)


def rank_deals(deals: list[dict]) -> list[dict]:
    """Sort deals by overall_score desc, assign rank and tier."""
    sorted_deals = sorted(deals, key=lambda d: d.get("overall_score") or 0, reverse=True)
    for i, d in enumerate(sorted_deals):
        d["rank"] = i + 1
        score = d.get("overall_score") or 0
        d["tier"] = "S" if score >= 75 else "A" if score >= 60 else "B" if score >= 45 else "C"
    return sorted_deals
