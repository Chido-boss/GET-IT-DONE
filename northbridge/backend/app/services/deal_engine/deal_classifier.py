"""
Deal classifier — determines the most viable investment strategy for a listing.
"""
from dataclasses import dataclass
from enum import Enum


class DealType(str, Enum):
    BMV_FLIP = "bmv_flip"
    BTL = "btl"
    HMO = "hmo"
    PLANNING_GAIN = "planning_gain"
    CONVERSION = "conversion"
    BRRR = "brrr"
    AUCTION_PLAY = "auction_play"
    PASS = "pass"


@dataclass
class ClassificationResult:
    primary_strategy: DealType
    secondary_strategies: list[DealType]
    rationale: str
    confidence: float  # 0-1


# Postcode prefixes near university towns — good HMO demand
HMO_DEMAND_AREAS = {
    "NE1", "NE2", "NE6", "NE7",   # Newcastle / Northumbria uni
    "SR1", "SR2",                   # Sunderland uni
    "DH1",                          # Durham uni
    "TS1",                          # Teesside uni
}

COMMERCIAL_TYPES = {"O", "C"}
RESIDENTIAL_TYPES = {"D", "S", "T", "F"}


def classify_deal(
    asking_price: int,
    property_type: str,
    bedrooms: int | None,
    postcode: str | None,
    description: str | None,
    bmv_score: float,
    distress_score: float,
    planning_score: float,
    conversion_hits: list[str] | None = None,
    discount_pct: float | None = None,
) -> ClassificationResult:
    """Classify the most viable strategy for this deal."""
    strategies = []
    postcode_prefix = (postcode or "").strip().upper().split(" ")[0]
    desc_lower = (description or "").lower()

    # Conversion / planning play for commercial
    if property_type in COMMERCIAL_TYPES:
        if planning_score >= 30 or conversion_hits:
            strategies.append(DealType.CONVERSION)
        strategies.append(DealType.PLANNING_GAIN)

    # BMV flip — residential with clear discount
    if property_type in RESIDENTIAL_TYPES and (discount_pct or 0) >= 10:
        strategies.append(DealType.BMV_FLIP)

    # BRRR — distressed residential with refinance potential
    if distress_score >= 40 and property_type in {"T", "S"} and asking_price < 150_000:
        strategies.append(DealType.BRRR)

    # HMO — right area, enough bedrooms
    if postcode_prefix in HMO_DEMAND_AREAS and (bedrooms or 0) >= 3:
        strategies.append(DealType.HMO)

    # BTL — any residential that pencils on yield
    if property_type in RESIDENTIAL_TYPES:
        strategies.append(DealType.BTL)

    # Planning gain — planning signals present
    if planning_score >= 50:
        strategies.append(DealType.PLANNING_GAIN)

    # Auction play — explicit auction signal
    if "auction" in desc_lower:
        strategies.append(DealType.AUCTION_PLAY)

    # Default
    if not strategies:
        if bmv_score < 20 and distress_score < 20:
            return ClassificationResult(
                primary_strategy=DealType.PASS,
                secondary_strategies=[],
                rationale="No strong signals for any strategy at this price.",
                confidence=0.7,
            )
        strategies.append(DealType.BTL)

    primary = strategies[0]

    rationale_map = {
        DealType.BMV_FLIP: f"Property priced {discount_pct:.0f}% below market estimate — strong refurb-and-sell candidate.",
        DealType.BRRR: "Distressed residential in accessible price bracket. Buy-refurb-refinance-rent strategy viable.",
        DealType.BTL: "Standard residential yield play. Run yield calculation before proceeding.",
        DealType.HMO: f"Location near university ({postcode_prefix}) with sufficient bedrooms — HMO licensing likely viable.",
        DealType.PLANNING_GAIN: "Planning signals detected. Potential to secure permission and sell with PP in place.",
        DealType.CONVERSION: "Commercial to residential conversion signals. Check PD rights and class MA eligibility.",
        DealType.AUCTION_PLAY: "Auction listing — attend with clear max bid based on comparables.",
        DealType.PASS: "Insufficient signals to recommend a strategy at current asking price.",
    }

    return ClassificationResult(
        primary_strategy=primary,
        secondary_strategies=strategies[1:3],
        rationale=rationale_map.get(primary, "Review manually."),
        confidence=min(0.5 + (bmv_score + distress_score) / 200, 0.95),
    )
