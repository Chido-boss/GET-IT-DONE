"""
Northbridge Intelligence — Deal Scoring Engine v2
Scores deals on four weighted dimensions:
  ROI (35%) · Discount to Market (30%) · Risk (20%) · Liquidity/Exit (15%)

Produces: overall_score, tier, confidence, risk_level, component scores.
"""
from dataclasses import dataclass, field
from typing import Optional


# ── Strategy profiles ─────────────────────────────────────────────────────────

STRATEGY_BASE_RISK = {
    "flip": 40,
    "light_refurb_flip": 35,
    "brr": 38,
    "brrr": 38,
    "btl": 25,
    "income_hold": 25,
    "hmo": 45,
    "conversion": 60,
    "planning_uplift": 65,
    "auction": 50,
}

# Liquidity score (0–100): how quickly / easily you can exit this deal
STRATEGY_LIQUIDITY = {
    "flip": 80,
    "light_refurb_flip": 82,
    "auction": 75,
    "brrr": 60,
    "brr": 60,
    "btl": 55,
    "income_hold": 50,
    "hmo": 45,
    "conversion": 30,
    "planning_uplift": 25,
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

REGEN_ZONE_NAMES = {
    "NE1": "Newcastle Quayside", "NE8": "Gateshead Stadium Quarter",
    "NE9": "Gateshead South", "NE10": "Gateshead East",
    "SR1": "Sunderland Riverside", "SR2": "Sunderland Riverside",
    "TS6": "Teesworks", "TS10": "Teesworks", "TS3": "Teesworks",
    "NE33": "South Shields Waterfront", "NE34": "South Shields Waterfront",
    "TS24": "Hartlepool Marina", "TS25": "Hartlepool Marina",
    "DH1": "Northgate Durham", "NE24": "Blyth Estuary", "NE25": "Blyth Estuary",
}


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class DealScoreResult:
    # Component scores (0–100, higher always = better)
    score_roi: float
    score_discount: float
    score_risk: float       # higher = less risky = better
    score_liquidity: float

    # Overall
    overall_score: float
    tier: str               # S / A / B / C
    confidence: str         # High / Medium / Low
    risk_level: str         # Low / Medium / High

    # Derived financials
    total_cost: int
    gross_profit: Optional[int]
    net_profit: Optional[int]   # same as profit
    profit: Optional[int]       # legacy alias
    roi_pct: Optional[float]
    roi: Optional[float]        # legacy alias
    discount_pct: Optional[float]

    # Intelligence flags
    is_undervalued: bool
    is_high_roi: bool
    has_planning_upside: bool
    is_distressed: bool
    near_regen_zone: bool

    # Legacy sub-scores (kept for API compat)
    roi_score: float
    risk_score: float           # raw risk 0-100, higher = more risk
    planning_uplift_score: float
    market_score: float

    # Conviction narrative
    conviction: str
    conviction_icon: str
    conviction_explanation: str

    # Drivers
    positive_drivers: list = field(default_factory=list)
    negative_drivers: list = field(default_factory=list)
    signals: list = field(default_factory=list)
    score_drivers: list = field(default_factory=list)


# ── Main scoring function ─────────────────────────────────────────────────────

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
    days_on_market: Optional[int] = None,
    price_reductions: Optional[int] = None,
    annual_yield_pct: Optional[float] = None,
) -> DealScoreResult:
    desc = (description or "").lower()
    pc_prefix = (postcode or "").strip().upper().split(" ")[0]
    strat = (strategy or "flip").lower()

    # ── Financials ───────────────────────────────────────────────────────────
    stamp_duty = _stamp_duty(purchase_price)
    legal = 3_000
    auto_costs = stamp_duty + legal + (other_costs or 0)
    total_cost = purchase_price + (refurb_cost or 0) + auto_costs

    exit_value = gdv or estimated_value
    gross_profit = (exit_value - purchase_price) if exit_value else None
    net_profit = (exit_value - total_cost) if exit_value else None
    roi_pct = round((net_profit / total_cost) * 100, 1) if (net_profit and total_cost) else None
    discount_pct = round(((exit_value - purchase_price) / exit_value) * 100, 1) if exit_value and exit_value > 0 else None

    # ── Component: ROI score (35% weight) ───────────────────────────────────
    score_roi = _compute_roi_score(roi_pct, annual_yield_pct, strat)

    # ── Component: Discount score (30% weight) ──────────────────────────────
    score_discount = _compute_discount_score(discount_pct)

    # ── Component: Risk score (20% weight) ──────────────────────────────────
    # Returns 0-100 where higher = better (less risky)
    raw_risk, score_risk = _compute_risk_score(
        strat, refurb_cost, purchase_price, roi_pct, desc, days_on_market
    )

    # ── Component: Liquidity score (15% weight) ──────────────────────────────
    score_liquidity = _compute_liquidity_score(
        strat, discount_pct, days_on_market, price_reductions, near_regen=(pc_prefix in NE_REGEN_POSTCODES)
    )

    # ── Overall score ────────────────────────────────────────────────────────
    overall = round(
        score_roi * 0.35
        + score_discount * 0.30
        + score_risk * 0.20
        + score_liquidity * 0.15,
        1,
    )
    overall = min(overall, 100.0)

    tier = _assign_tier(overall)
    confidence = _assign_confidence(exit_value, roi_pct, discount_pct, refurb_cost)
    risk_level = _assign_risk_level(raw_risk)

    # ── Intelligence flags ───────────────────────────────────────────────────
    is_undervalued = bool(discount_pct and discount_pct >= 8)
    is_high_roi = bool(roi_pct and roi_pct >= 20)
    has_planning_upside = bool([kw for kw in PLANNING_KEYWORDS if kw in desc]) or strat in ("planning_uplift", "conversion")
    is_distressed = bool([kw for kw in DISTRESS_KEYWORDS if kw in desc])
    near_regen_zone = pc_prefix in NE_REGEN_POSTCODES

    # ── Legacy scores (for API compat) ───────────────────────────────────────
    planning_hits = [kw for kw in PLANNING_KEYWORDS if kw in desc]
    planning_uplift_score = 0.0
    if planning_hits:
        planning_uplift_score = min(len(planning_hits) * 20, 85)
    if strat in ("planning_uplift", "conversion"):
        planning_uplift_score = max(planning_uplift_score, 70)

    market_score = score_discount  # market score maps to discount score

    # ── Drivers ─────────────────────────────────────────────────────────────
    positives, negatives = _build_drivers(
        roi_pct, discount_pct, score_roi, score_discount,
        has_planning_upside, near_regen_zone, is_distressed,
        refurb_cost, purchase_price, pc_prefix, strat, planning_hits
    )

    all_drivers = [
        {"icon": d["icon"], "label": d["label"], "impact": d["impact"],
         "polarity": d["polarity"], "intensity": d.get("intensity", "mild"), "detail": d.get("detail", "")}
        for d in sorted(positives + negatives, key=lambda x: x["impact"], reverse=True)
    ]

    # ── Conviction (legacy narrative) ────────────────────────────────────────
    conviction, conviction_icon = _conviction_from_score(overall)
    conviction_explanation = _build_explanation(
        overall, conviction, roi_pct, discount_pct, strat,
        has_planning_upside, near_regen_zone, is_distressed, refurb_cost, purchase_price
    )

    return DealScoreResult(
        score_roi=round(score_roi, 1),
        score_discount=round(score_discount, 1),
        score_risk=round(score_risk, 1),
        score_liquidity=round(score_liquidity, 1),
        overall_score=overall,
        tier=tier,
        confidence=confidence,
        risk_level=risk_level,
        total_cost=total_cost,
        gross_profit=gross_profit,
        net_profit=net_profit,
        profit=net_profit,
        roi_pct=roi_pct,
        roi=roi_pct,
        discount_pct=discount_pct,
        is_undervalued=is_undervalued,
        is_high_roi=is_high_roi,
        has_planning_upside=has_planning_upside,
        is_distressed=is_distressed,
        near_regen_zone=near_regen_zone,
        roi_score=round(score_roi, 1),
        risk_score=round(raw_risk, 1),
        planning_uplift_score=round(planning_uplift_score, 1),
        market_score=round(market_score, 1),
        conviction=conviction,
        conviction_icon=conviction_icon,
        conviction_explanation=conviction_explanation,
        positive_drivers=[
            {"icon": d["icon"], "label": d["label"], "impact": d["impact"],
             "intensity": d.get("intensity", "mild"), "detail": d.get("detail", "")}
            for d in sorted(positives, key=lambda x: x["impact"], reverse=True)
        ],
        negative_drivers=[
            {"icon": d["icon"], "label": d["label"], "impact": d["impact"],
             "intensity": d.get("intensity", "mild"), "detail": d.get("detail", "")}
            for d in negatives
        ],
        signals=[
            {"key": d.get("key", ""), "label": d["label"], "icon": d["icon"],
             "polarity": d["polarity"], "intensity": d.get("intensity", "mild"), "detail": d.get("detail", "")}
            for d in sorted(positives + negatives, key=lambda x: x["impact"], reverse=True)[:4]
        ],
        score_drivers=all_drivers[:5],
    )


# ── Component scorers ─────────────────────────────────────────────────────────

def _compute_roi_score(roi_pct: Optional[float], annual_yield: Optional[float], strategy: str) -> float:
    """0–100 score for profitability. Accounts for BTL yield deals."""
    # For yield strategies, use yield if ROI not computable
    if roi_pct is None and annual_yield and strategy in ("btl", "hmo", "income_hold"):
        if annual_yield >= 14:
            return 88.0
        elif annual_yield >= 10:
            return 72.0
        elif annual_yield >= 7:
            return 52.0
        elif annual_yield >= 5:
            return 32.0
        return 15.0

    if roi_pct is None:
        return 0.0

    if roi_pct >= 40:
        return 100.0
    elif roi_pct >= 30:
        return 90.0 + (roi_pct - 30) * 1.0
    elif roi_pct >= 20:
        return 75.0 + (roi_pct - 20) * 1.5
    elif roi_pct >= 12:
        return 50.0 + (roi_pct - 12) * 3.1
    elif roi_pct >= 6:
        return 20.0 + (roi_pct - 6) * 5.0
    elif roi_pct >= 0:
        return roi_pct * 3.3
    return 0.0


def _compute_discount_score(discount_pct: Optional[float]) -> float:
    """0–100 score for buying below market."""
    if discount_pct is None:
        return 0.0
    if discount_pct <= 0:
        return 0.0
    elif discount_pct >= 35:
        return 100.0
    elif discount_pct >= 25:
        return 85.0 + (discount_pct - 25) * 1.5
    elif discount_pct >= 15:
        return 60.0 + (discount_pct - 15) * 2.5
    elif discount_pct >= 8:
        return 30.0 + (discount_pct - 8) * 4.3
    elif discount_pct >= 3:
        return 8.0 + (discount_pct - 3) * 4.4
    return discount_pct * 2.0


def _compute_risk_score(
    strategy: str,
    refurb_cost: Optional[int],
    purchase_price: int,
    roi_pct: Optional[float],
    desc: str,
    days_on_market: Optional[int],
) -> tuple[float, float]:
    """Returns (raw_risk 0-100 higher=more_risk, score_risk 0-100 higher=better/less_risk)."""
    base = STRATEGY_BASE_RISK.get(strategy, 45)
    raw = float(base)

    if refurb_cost and purchase_price:
        ratio = refurb_cost / purchase_price
        if ratio > 0.40:
            raw = min(raw + 20, 95)
        elif ratio > 0.20:
            raw = min(raw + 10, 90)

    if roi_pct is not None and roi_pct < 10:
        raw = min(raw + 8, 90)

    if strategy in ("planning_uplift", "conversion"):
        raw = min(raw + 5, 95)

    distress_hits = [kw for kw in DISTRESS_KEYWORDS if kw in desc]
    if len(distress_hits) >= 2:
        raw = max(raw - 5, 10)  # motivated seller reduces negotiation risk

    # Longer DOM can signal demand issues (risk up)
    if days_on_market and days_on_market > 120:
        raw = min(raw + 5, 95)

    score_risk = max(0.0, 100.0 - raw)
    return raw, score_risk


def _compute_liquidity_score(
    strategy: str,
    discount_pct: Optional[float],
    days_on_market: Optional[int],
    price_reductions: Optional[int],
    near_regen: bool,
) -> float:
    """0–100 score for how easy it is to exit this deal profitably."""
    base = float(STRATEGY_LIQUIDITY.get(strategy, 50))

    # Better discount = more buyer appetite = higher liquidity
    if discount_pct:
        if discount_pct >= 20:
            base = min(base + 10, 95)
        elif discount_pct >= 12:
            base = min(base + 5, 95)

    # Regen zone: higher future demand
    if near_regen:
        base = min(base + 8, 95)

    # DOM signal: if it was hard to sell before, liquidity is lower
    if days_on_market:
        if days_on_market > 180:
            base = max(base - 10, 5)
        elif days_on_market > 90:
            base = max(base - 5, 5)

    # Multiple price reductions suggest price was wrong — tighter market
    if price_reductions and price_reductions >= 2:
        base = max(base - 5, 5)

    return min(round(base, 1), 100.0)


# ── Classification helpers ────────────────────────────────────────────────────

def _assign_tier(overall: float) -> str:
    if overall >= 80:
        return "S"
    elif overall >= 70:
        return "A"
    elif overall >= 60:
        return "B"
    return "C"


def _assign_confidence(
    exit_value: Optional[int],
    roi_pct: Optional[float],
    discount_pct: Optional[float],
    refurb_cost: Optional[int],
) -> str:
    score = 0
    if exit_value:
        score += 2
    if roi_pct is not None:
        score += 2
    if discount_pct and discount_pct > 0:
        score += 1
    if refurb_cost is not None:
        score += 1
    if score >= 5:
        return "High"
    elif score >= 3:
        return "Medium"
    return "Low"


def _assign_risk_level(raw_risk: float) -> str:
    if raw_risk <= 35:
        return "Low"
    elif raw_risk <= 55:
        return "Medium"
    return "High"


def _conviction_from_score(overall: float) -> tuple[str, str]:
    if overall >= 80:
        return "VERY HIGH", "⬆⬆"
    elif overall >= 65:
        return "HIGH", "⬆"
    elif overall >= 50:
        return "MEDIUM", "→"
    elif overall >= 35:
        return "LOW", "⬇"
    return "VERY LOW", "⬇⬇"


# ── Drivers builder ───────────────────────────────────────────────────────────

def _build_drivers(
    roi_pct, discount_pct, score_roi, score_discount,
    has_planning, near_regen, is_distressed,
    refurb_cost, purchase_price, pc_prefix, strategy, planning_hits
):
    positives = []
    negatives = []

    # ROI driver
    if roi_pct is not None:
        if roi_pct >= 30:
            positives.append({"key": "roi_exceptional", "icon": "🚀", "polarity": "positive", "intensity": "very_strong",
                "label": f"Exceptional ROI: {roi_pct:.0f}%", "impact": score_roi,
                "detail": f"{roi_pct:.0f}% return on fully-loaded capital — top-decile NE deal"})
        elif roi_pct >= 20:
            positives.append({"key": "roi_strong", "icon": "📈", "polarity": "positive", "intensity": "strong",
                "label": f"Strong ROI: {roi_pct:.0f}%", "impact": score_roi,
                "detail": f"{roi_pct:.0f}% ROI — well above NE average of 12–18%"})
        elif roi_pct >= 12:
            positives.append({"key": "roi_solid", "icon": "📊", "polarity": "positive", "intensity": "mild",
                "label": f"Solid ROI: {roi_pct:.0f}%", "impact": score_roi,
                "detail": f"{roi_pct:.0f}% ROI — acceptable for this strategy"})
        elif roi_pct >= 6:
            negatives.append({"key": "roi_low", "icon": "📉", "polarity": "negative", "intensity": "mild",
                "label": f"Modest ROI: {roi_pct:.0f}%", "impact": score_roi,
                "detail": f"Only {roi_pct:.0f}% return — limited margin for error"})
        else:
            negatives.append({"key": "roi_very_low", "icon": "⚠️", "polarity": "negative", "intensity": "strong",
                "label": f"Low ROI: {roi_pct:.0f}%", "impact": score_roi,
                "detail": f"{roi_pct:.0f}% ROI is below minimum viable threshold"})

    # Discount driver
    if discount_pct:
        if discount_pct >= 25:
            positives.append({"key": "bmv_deep", "icon": "🔻", "polarity": "positive", "intensity": "very_strong",
                "label": f"Deep BMV: {discount_pct:.0f}% below market", "impact": score_discount,
                "detail": f"Buying {discount_pct:.0f}% below estimated value — exceptional entry"})
        elif discount_pct >= 15:
            positives.append({"key": "bmv_strong", "icon": "📉", "polarity": "positive", "intensity": "strong",
                "label": f"BMV: {discount_pct:.0f}% below market", "impact": score_discount,
                "detail": f"Priced {discount_pct:.0f}% below comparables — strong entry position"})
        elif discount_pct >= 8:
            positives.append({"key": "bmv_mild", "icon": "📊", "polarity": "positive", "intensity": "mild",
                "label": f"Slight BMV: {discount_pct:.0f}% below market", "impact": score_discount,
                "detail": f"Modest {discount_pct:.0f}% discount — some downside protection"})
        elif discount_pct <= 0:
            negatives.append({"key": "at_market", "icon": "⚠️", "polarity": "negative", "intensity": "strong",
                "label": "Priced at or above market value", "impact": 5,
                "detail": "No discount — limited downside protection"})

    # Planning
    if has_planning and planning_hits:
        positives.append({"key": "planning_upside", "icon": "🏗️", "polarity": "positive",
            "intensity": "strong" if len(planning_hits) >= 2 else "mild",
            "label": "Planning opportunity detected", "impact": 55,
            "detail": f"Signals: {', '.join(planning_hits[:3])} — potential value uplift"})

    # Regen zone
    if near_regen:
        zone = REGEN_ZONE_NAMES.get(pc_prefix, "NE Regeneration Zone")
        positives.append({"key": "regen_zone", "icon": "🔄", "polarity": "positive", "intensity": "strong",
            "label": f"Regen zone: {zone}", "impact": 55,
            "detail": f"Within {zone} — active public investment supports appreciation"})

    # Distress
    if is_distressed:
        positives.append({"key": "distressed", "icon": "⚠️", "polarity": "positive", "intensity": "mild",
            "label": "Motivated seller signals", "impact": 40,
            "detail": "Distress indicators suggest negotiation leverage"})

    # Heavy refurb risk
    if refurb_cost and purchase_price and refurb_cost > purchase_price * 0.20:
        negatives.append({"key": "heavy_refurb", "icon": "🔧", "polarity": "negative", "intensity": "strong",
            "label": f"Heavy refurb required (£{refurb_cost:,})", "impact": 0,
            "detail": f"Refurb at {(refurb_cost/purchase_price*100):.0f}% of purchase — execution risk"})

    if strategy in ("planning_uplift", "conversion"):
        negatives.append({"key": "planning_risk", "icon": "📋", "polarity": "negative", "intensity": "mild",
            "label": "Planning consent required", "impact": 0,
            "detail": "Returns contingent on planning outcome — timeline and approval risk"})

    return positives, negatives


# ── Conviction narrative ──────────────────────────────────────────────────────

def _build_explanation(overall, conviction, roi, discount_pct, strategy,
                        has_planning, near_regen, is_distressed, refurb, price):
    parts = []
    if roi and roi >= 20:
        parts.append(f"{roi:.0f}% ROI on fully-loaded costs")
    elif roi and roi >= 10:
        parts.append(f"achievable {roi:.0f}% return with disciplined execution")
    if discount_pct and discount_pct >= 20:
        parts.append(f"priced {discount_pct:.0f}% below estimated market value")
    elif discount_pct and discount_pct >= 10:
        parts.append(f"modest {discount_pct:.0f}% BMV entry")
    if has_planning:
        parts.append("planning uplift potential adds secondary exit route")
    if near_regen:
        parts.append("regeneration investment supports medium-term appreciation")
    if is_distressed:
        parts.append("motivated seller signals room to negotiate")
    if refurb and price and refurb > price * 0.2:
        parts.append(f"heavy refurb (£{refurb:,}) elevates execution risk")

    if not parts:
        return f"Conviction score {overall:.0f}/100. Review deal fundamentals before proceeding."

    narrative = ". ".join(p.capitalize() for p in parts[:3]) + "."
    return f"Conviction {overall:.0f}/100 — {conviction}. {narrative}"


# ── Stamp duty (3% surcharge for investment) ─────────────────────────────────

def _stamp_duty(price: int) -> int:
    if price <= 250_000:
        return int(price * 0.03)
    elif price <= 925_000:
        return int(250_000 * 0.03 + (price - 250_000) * 0.08)
    return int(250_000 * 0.03 + 675_000 * 0.08 + (price - 925_000) * 0.13)


# ── Rank deals list ───────────────────────────────────────────────────────────

def rank_deals(deals: list[dict]) -> list[dict]:
    sorted_deals = sorted(deals, key=lambda d: d.get("overall_score") or 0, reverse=True)
    for i, d in enumerate(sorted_deals):
        d["rank"] = i + 1
        score = d.get("overall_score") or 0
        d["tier"] = d.get("tier") or _assign_tier(score)
    return sorted_deals
