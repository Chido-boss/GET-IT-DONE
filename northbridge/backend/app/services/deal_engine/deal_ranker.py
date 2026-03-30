"""
Deal ranker — applies final weighting and ranks a list of deals.
Provides the ordered deal feed for the dashboard.
"""
from dataclasses import dataclass

WEIGHTS = {
    "bmv": 0.30,
    "distress": 0.22,
    "momentum": 0.13,
    "planning": 0.15,
    "regeneration": 0.15,
    "confidence": 0.05,  # confidence is a modifier, not a primary driver
}


@dataclass
class RankedDeal:
    listing_id: str
    overall_score: float
    rank: int
    tier: str           # S / A / B / C
    bmv_score: float
    distress_score: float
    momentum_score: float
    planning_score: float
    regeneration_score: float
    confidence_score: float
    estimated_fair_value: int | None
    discount_pct: float | None
    primary_strategy: str


def calculate_overall_score(
    bmv_score: float,
    distress_score: float,
    momentum_score: float,
    planning_score: float,
    regeneration_score: float,
    confidence_score: float,
) -> float:
    """Weighted composite score."""
    raw = (
        bmv_score * WEIGHTS["bmv"] +
        distress_score * WEIGHTS["distress"] +
        momentum_score * WEIGHTS["momentum"] +
        planning_score * WEIGHTS["planning"] +
        regeneration_score * WEIGHTS["regeneration"]
    )
    # Confidence acts as a dampener for low-data scores
    confidence_factor = 0.7 + (confidence_score / 100) * 0.3
    return round(min(raw * confidence_factor, 100.0), 1)


def get_tier(score: float) -> str:
    if score >= 80:
        return "S"
    elif score >= 65:
        return "A"
    elif score >= 50:
        return "B"
    else:
        return "C"


def rank_deals(scored_listings: list[dict]) -> list[RankedDeal]:
    """
    Given a list of listings with component scores, produce a ranked deal feed.
    Each listing dict must have: id, bmv_score, distress_score, momentum_score,
    planning_score, regeneration_score, confidence_score, estimated_fair_value,
    discount_pct, primary_strategy
    """
    results = []
    for listing in scored_listings:
        overall = calculate_overall_score(
            listing.get("bmv_score", 0),
            listing.get("distress_score", 0),
            listing.get("momentum_score", 0),
            listing.get("planning_score", 0),
            listing.get("regeneration_score", 0),
            listing.get("confidence_score", 50),
        )
        results.append(RankedDeal(
            listing_id=str(listing["id"]),
            overall_score=overall,
            rank=0,
            tier=get_tier(overall),
            bmv_score=listing.get("bmv_score", 0),
            distress_score=listing.get("distress_score", 0),
            momentum_score=listing.get("momentum_score", 0),
            planning_score=listing.get("planning_score", 0),
            regeneration_score=listing.get("regeneration_score", 0),
            confidence_score=listing.get("confidence_score", 50),
            estimated_fair_value=listing.get("estimated_fair_value"),
            discount_pct=listing.get("discount_pct"),
            primary_strategy=listing.get("primary_strategy", "btl"),
        ))

    results.sort(key=lambda d: d.overall_score, reverse=True)
    for i, d in enumerate(results):
        d.rank = i + 1

    return results
