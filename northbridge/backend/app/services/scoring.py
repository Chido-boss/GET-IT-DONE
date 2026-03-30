"""
Northbridge Intelligence — Scoring Engine
Calculates a composite investment opportunity score for each property listing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCORE_WEIGHTS = {
    "bmv": 0.30,
    "distress": 0.25,
    "momentum": 0.15,
    "planning": 0.15,
    "regeneration": 0.15,
}

DISTRESS_KEYWORDS = [
    "chain free",
    "no chain",
    "vacant possession",
    "sold as seen",
    "motivated seller",
    "quick sale",
    "cash buyers only",
    "cash buyer",
    "requires modernisation",
    "refurbishment opportunity",
    "in need of modernisation",
    "investment opportunity",
    "development opportunity",
    "priced to sell",
    "below market",
    "below asking",
    "price reduction",
    "reduced",
    "executor",
    "probate",
    "repossession",
    "auction",
    "as seen",
]

PLANNING_UPLIFT_KEYWORDS = [
    "change of use",
    "conversion",
    "mixed use",
    "residential development",
    "new dwellings",
    "new homes",
    "regeneration",
    "commercial to residential",
    "office to residential",
    "retail to residential",
    "permitted development",
    "major development",
    "strategic site",
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ScoreResult:
    overall_score: float
    bmv_score: float
    distress_score: float
    momentum_score: float
    planning_score: float
    regeneration_score: float
    confidence_score: float
    estimated_fair_value: Optional[int]
    avg_comparable_price: Optional[int]
    discount_pct: Optional[float]
    score_drivers: List[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Haversine helper
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in km between two lat/lng points."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Sub-scorers
# ---------------------------------------------------------------------------

def calculate_bmv_score(
    asking_price: int,
    estimated_value: Optional[int],
) -> Tuple[float, List[dict]]:
    """
    Score based on discount to estimated market value.
    Returns (score 0-100, list_of_drivers).
    """
    drivers: List[dict] = []

    if estimated_value is None or estimated_value <= 0:
        return 0.0, drivers

    discount_pct = (estimated_value - asking_price) / estimated_value * 100

    if discount_pct >= 30:
        score = 100.0
    elif discount_pct >= 20:
        score = 80.0 + (discount_pct - 20) * 2.0  # 80-100
    elif discount_pct >= 10:
        score = 50.0 + (discount_pct - 10) * 3.0  # 50-80
    elif discount_pct >= 0:
        score = discount_pct * 5.0  # 0-50
    elif discount_pct >= -10:
        score = max(0.0, 10.0 + discount_pct * 1.0)
    else:
        score = 0.0

    score = max(0.0, min(100.0, score))

    if discount_pct >= 1:
        drivers.append({
            "label": f"Asking price {discount_pct:.0f}% below market average",
            "value": f"£{asking_price:,} vs £{estimated_value:,} est.",
            "impact": score * SCORE_WEIGHTS["bmv"],
            "icon": "trending_down",
        })
    elif discount_pct < 0:
        drivers.append({
            "label": f"Asking price {abs(discount_pct):.0f}% above market average",
            "value": f"£{asking_price:,} vs £{estimated_value:,} est.",
            "impact": score * SCORE_WEIGHTS["bmv"],
            "icon": "trending_up",
        })

    return score, drivers


def calculate_distress_score(
    description: Optional[str],
    title: Optional[str],
    price_reduction_count: int,
    days_on_market: Optional[int],
) -> Tuple[float, List[dict]]:
    """
    Score based on distress signals in listing text and behaviour.
    Returns (score 0-100, list_of_drivers).
    """
    drivers: List[dict] = []
    combined_text = " ".join(
        filter(None, [description or "", title or ""])
    ).lower()

    found_keywords = [kw for kw in DISTRESS_KEYWORDS if kw in combined_text]
    keyword_count = len(found_keywords)

    # Keyword score: up to 70 points
    keyword_score = min(70.0, keyword_count * 14.0)

    # Price reduction bonus: up to 20 points
    reduction_score = min(20.0, price_reduction_count * 10.0)

    # DOM bonus: up to 10 points (>90 days = 10)
    dom_score = 0.0
    if days_on_market and days_on_market > 90:
        dom_score = 10.0
    elif days_on_market and days_on_market > 60:
        dom_score = 7.0
    elif days_on_market and days_on_market > 30:
        dom_score = 4.0

    total = min(100.0, keyword_score + reduction_score + dom_score)

    if found_keywords:
        # Group labels nicely
        short_labels = [kw.title() for kw in found_keywords[:4]]
        label_str = " + ".join(short_labels)
        if len(found_keywords) > 4:
            label_str += f" (+{len(found_keywords) - 4} more signals)"
        drivers.append({
            "label": f"Distress signals: {label_str}",
            "value": f"{keyword_count} signal(s) detected in listing text",
            "impact": total * SCORE_WEIGHTS["distress"],
            "icon": "warning",
        })

    if price_reduction_count > 0:
        drivers.append({
            "label": f"{price_reduction_count} price reduction(s) recorded",
            "value": f"Price has been cut {price_reduction_count} time(s)",
            "impact": reduction_score * SCORE_WEIGHTS["distress"],
            "icon": "price_change",
        })

    return total, drivers


def calculate_momentum_score(
    days_on_market: Optional[int],
    price_reduction_count: int,
    date_listed: Optional[date],
) -> Tuple[float, List[dict]]:
    """
    Score based on listing momentum (stale + price cuts = motivated seller).
    Returns (score 0-100, list_of_drivers).
    """
    drivers: List[dict] = []

    # If we don't have DOM, estimate from date_listed
    dom = days_on_market
    if dom is None and date_listed is not None:
        dom = (date.today() - date_listed).days

    if dom is None:
        return 0.0, drivers

    # DOM scoring: sweet spot is 30-120 days (seller likely motivated)
    if dom < 14:
        dom_score = 10.0  # Too new
    elif dom < 30:
        dom_score = 25.0
    elif dom < 60:
        dom_score = 50.0
    elif dom < 90:
        dom_score = 70.0
    elif dom < 120:
        dom_score = 85.0
    elif dom < 180:
        dom_score = 90.0
    else:
        dom_score = 95.0  # Very stale — seller likely motivated

    # Price reductions add urgency
    reduction_bonus = min(5.0, price_reduction_count * 2.5)
    total = min(100.0, dom_score + reduction_bonus)

    if dom >= 30:
        reduction_text = (
            f" with {price_reduction_count} price reduction(s)"
            if price_reduction_count > 0
            else ""
        )
        drivers.append({
            "label": f"{dom} days on market{reduction_text}",
            "value": f"Listed {dom} days ago",
            "impact": total * SCORE_WEIGHTS["momentum"],
            "icon": "schedule",
        })

    return total, drivers


def calculate_planning_score(
    nearby_planning_apps: list,
) -> Tuple[float, List[dict]]:
    """
    Score based on nearby planning applications that suggest area uplift.
    Returns (score 0-100, list_of_drivers).
    """
    drivers: List[dict] = []

    if not nearby_planning_apps:
        return 0.0, drivers

    app_count = len(nearby_planning_apps)
    high_uplift = [a for a in nearby_planning_apps if getattr(a, "uplift_score", 0) >= 5.0]
    high_uplift_count = len(high_uplift)

    # Base score: up to 60 from count alone (capped at 5 apps)
    count_score = min(60.0, app_count * 12.0)

    # Uplift bonus: up to 40 from high-significance apps
    uplift_bonus = min(40.0, high_uplift_count * 13.0)

    total = min(100.0, count_score + uplift_bonus)

    # Build a readable description
    uplift_types: List[str] = []
    for app in nearby_planning_apps[:5]:
        signals = getattr(app, "uplift_signals", None) or []
        uplift_types.extend(signals)

    unique_signals = list(dict.fromkeys(uplift_types))[:3]
    signal_str = (
        " including " + ", ".join(unique_signals)
        if unique_signals
        else ""
    )

    if app_count > 0:
        drivers.append({
            "label": f"{app_count} planning application(s) within 500m{signal_str}",
            "value": f"{high_uplift_count} high-significance application(s)",
            "impact": total * SCORE_WEIGHTS["planning"],
            "icon": "apartment",
        })

    return total, drivers


def calculate_regeneration_score(
    listing: object,
    regen_zones: list,
) -> Tuple[float, List[dict]]:
    """
    Score based on proximity to active regeneration zones.
    Returns (score 0-100, list_of_drivers).
    """
    drivers: List[dict] = []

    if not regen_zones:
        return 0.0, drivers

    listing_lat = getattr(listing, "latitude", None)
    listing_lng = getattr(listing, "longitude", None)
    listing_postcode = getattr(listing, "postcode", "") or ""

    best_score = 0.0
    best_zone_name = None
    best_distance = None

    for zone in regen_zones:
        zone_status = getattr(zone, "status", "Planning")
        if zone_status == "Complete":
            zone_multiplier = 0.5
        elif zone_status == "Active":
            zone_multiplier = 1.0
        else:  # Planning
            zone_multiplier = 0.7

        zone_lat = getattr(zone, "center_lat", None)
        zone_lng = getattr(zone, "center_lng", None)
        radius_km = getattr(zone, "radius_km", 1.0) or 1.0

        # Try distance-based calculation first
        if listing_lat and listing_lng and zone_lat and zone_lng:
            dist_km = _haversine_km(listing_lat, listing_lng, zone_lat, zone_lng)
            # Score: full marks if within radius, diminishing to 2x radius
            if dist_km <= radius_km:
                proximity_score = 100.0
            elif dist_km <= radius_km * 2:
                proximity_score = 50.0 + (radius_km * 2 - dist_km) / radius_km * 50.0
            elif dist_km <= radius_km * 3:
                proximity_score = 25.0 + (radius_km * 3 - dist_km) / radius_km * 25.0
            else:
                proximity_score = 0.0

            zone_score = proximity_score * zone_multiplier

            if zone_score > best_score:
                best_score = zone_score
                best_zone_name = getattr(zone, "name", "Unknown Zone")
                best_distance = dist_km

        else:
            # Fall back to postcode prefix matching
            zone_postcodes_str = getattr(zone, "postcodes", "") or ""
            zone_postcodes = [p.strip().upper() for p in zone_postcodes_str.split(",") if p.strip()]
            listing_prefix = listing_postcode.split(" ")[0].upper()

            if any(listing_prefix.startswith(zp) or listing_prefix == zp for zp in zone_postcodes):
                zone_score = 70.0 * zone_multiplier
                if zone_score > best_score:
                    best_score = zone_score
                    best_zone_name = getattr(zone, "name", "Unknown Zone")
                    best_distance = None

    total = min(100.0, best_score)

    if total > 0 and best_zone_name:
        dist_text = (
            f" ({best_distance:.1f}km away)" if best_distance is not None else ""
        )
        drivers.append({
            "label": f"Adjacent to {best_zone_name} regeneration zone{dist_text}",
            "value": f"Zone status affects future capital growth",
            "impact": total * SCORE_WEIGHTS["regeneration"],
            "icon": "construction",
        })

    return total, drivers


def calculate_confidence_score(
    comparable_count: int,
    data_completeness: float,  # 0-1
) -> float:
    """
    Score how confident we are in the overall score.
    Based on number of comparables and data completeness.
    """
    if comparable_count == 0:
        comp_score = 0.0
    elif comparable_count == 1:
        comp_score = 30.0
    elif comparable_count <= 3:
        comp_score = 50.0
    elif comparable_count <= 6:
        comp_score = 70.0
    elif comparable_count <= 10:
        comp_score = 85.0
    else:
        comp_score = 95.0

    completeness_score = data_completeness * 100.0 * 0.3
    comp_contribution = comp_score * 0.7

    return min(100.0, comp_contribution + completeness_score)


def get_comparable_estimate(
    comparables: list,
    postcode: str,
    property_type: str,
    bedrooms: Optional[int],
) -> Tuple[Optional[int], Optional[int], float]:
    """
    Estimate fair market value from comparables.
    Returns (estimated_value, avg_price, confidence 0-1).

    Matching priority:
    1. Same postcode + same type + same bedrooms
    2. Same postcode prefix + same type
    3. Same type + similar bedrooms (+-1)
    """
    if not comparables:
        return None, None, 0.0

    postcode_prefix = postcode.split(" ")[0].upper() if postcode else ""

    # Tier 1: Exact postcode + type + bedrooms
    tier1 = [
        c for c in comparables
        if (getattr(c, "postcode", "") or "").upper() == postcode.upper()
        and (getattr(c, "property_type", "") or "") == property_type
        and bedrooms is not None
        and (getattr(c, "bedrooms", None) or 0) == bedrooms
    ]

    # Tier 2: Postcode prefix + type
    tier2 = [
        c for c in comparables
        if (getattr(c, "postcode", "") or "").upper().startswith(postcode_prefix)
        and (getattr(c, "property_type", "") or "") == property_type
    ]

    # Tier 3: Type + +-1 bedroom
    tier3 = [
        c for c in comparables
        if (getattr(c, "property_type", "") or "") == property_type
        and (
            bedrooms is None
            or abs((getattr(c, "bedrooms", None) or bedrooms) - bedrooms) <= 1
        )
    ]

    chosen: list
    confidence: float
    if tier1:
        chosen = tier1
        confidence = 0.9
    elif tier2:
        chosen = tier2
        confidence = 0.7
    elif tier3:
        chosen = tier3
        confidence = 0.5
    else:
        chosen = comparables
        confidence = 0.3

    # Weight more recent sales higher
    today = date.today()
    weighted_prices: List[float] = []
    for c in chosen:
        price = getattr(c, "price", 0) or 0
        sold_date = getattr(c, "date_sold", None)
        if sold_date and price > 0:
            days_ago = (today - sold_date).days
            weight = max(0.1, 1.0 - (days_ago / 1825))  # 5-year decay
            weighted_prices.append(price * weight)
        elif price > 0:
            weighted_prices.append(price * 0.5)

    if not weighted_prices:
        return None, None, 0.0

    avg_raw = sum(getattr(c, "price", 0) or 0 for c in chosen) / len(chosen)
    avg_weighted = sum(weighted_prices) / len(weighted_prices) * (
        len(weighted_prices) / sum(
            max(0.1, 1.0 - ((today - getattr(c, "date_sold", today)).days / 1825))
            for c in chosen
        )
    )

    # Blend raw and weighted
    estimated = int((avg_raw + avg_weighted) / 2)
    avg_price = int(avg_raw)

    return estimated, avg_price, confidence


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_listing(
    listing: object,
    comparables: list,
    planning_apps: list,
    regen_zones: list,
) -> ScoreResult:
    """
    Calculate the full investment score for a listing.

    Parameters
    ----------
    listing       : ORM Listing object (or any object with the expected attributes)
    comparables   : List of ComparableSale ORM objects
    planning_apps : List of PlanningApplication ORM objects within ~500m
    regen_zones   : List of RegenerationZone ORM objects

    Returns
    -------
    ScoreResult dataclass
    """

    # --- Extract listing attributes -----------------------------------------
    asking_price: int = getattr(listing, "asking_price", 0) or 0
    postcode: str = getattr(listing, "postcode", "") or ""
    property_type: str = getattr(listing, "property_type", "") or ""
    bedrooms: Optional[int] = getattr(listing, "bedrooms", None)
    description: Optional[str] = getattr(listing, "description", None)
    title: Optional[str] = getattr(listing, "title", None)
    price_reduction_count: int = getattr(listing, "price_reduction_count", 0) or 0
    days_on_market: Optional[int] = getattr(listing, "days_on_market", None)
    date_listed: Optional[date] = getattr(listing, "date_listed", None)

    # --- Comparables estimate -----------------------------------------------
    estimated_fair_value, avg_comparable_price, comp_confidence = get_comparable_estimate(
        comparables, postcode, property_type, bedrooms
    )

    # --- BMV score ----------------------------------------------------------
    bmv_score, bmv_drivers = calculate_bmv_score(asking_price, estimated_fair_value)

    # --- Distress score -----------------------------------------------------
    distress_score, distress_drivers = calculate_distress_score(
        description, title, price_reduction_count, days_on_market
    )

    # --- Momentum score -----------------------------------------------------
    momentum_score, momentum_drivers = calculate_momentum_score(
        days_on_market, price_reduction_count, date_listed
    )

    # --- Planning score -----------------------------------------------------
    planning_score, planning_drivers = calculate_planning_score(planning_apps)

    # --- Regeneration score -------------------------------------------------
    regen_score, regen_drivers = calculate_regeneration_score(listing, regen_zones)

    # --- Overall weighted score ---------------------------------------------
    overall_score = (
        bmv_score * SCORE_WEIGHTS["bmv"]
        + distress_score * SCORE_WEIGHTS["distress"]
        + momentum_score * SCORE_WEIGHTS["momentum"]
        + planning_score * SCORE_WEIGHTS["planning"]
        + regen_score * SCORE_WEIGHTS["regeneration"]
    )
    overall_score = round(min(100.0, max(0.0, overall_score)), 2)

    # --- Discount % ---------------------------------------------------------
    discount_pct: Optional[float] = None
    if estimated_fair_value and estimated_fair_value > 0:
        discount_pct = round(
            (estimated_fair_value - asking_price) / estimated_fair_value * 100, 2
        )

    # --- Confidence score ---------------------------------------------------
    # Data completeness: count non-None fields
    completeness_fields = [
        description, bedrooms, date_listed, getattr(listing, "latitude", None),
        getattr(listing, "tenure", None), getattr(listing, "agent_name", None),
    ]
    completeness = sum(1 for f in completeness_fields if f is not None) / len(completeness_fields)
    confidence_score = round(
        calculate_confidence_score(len(comparables), completeness), 2
    )

    # --- Combine all drivers, sort by impact, take top 5 -------------------
    all_drivers = (
        bmv_drivers + distress_drivers + momentum_drivers + planning_drivers + regen_drivers
    )
    all_drivers.sort(key=lambda d: d.get("impact", 0), reverse=True)
    top_drivers = all_drivers[:5]

    return ScoreResult(
        overall_score=overall_score,
        bmv_score=round(bmv_score, 2),
        distress_score=round(distress_score, 2),
        momentum_score=round(momentum_score, 2),
        planning_score=round(planning_score, 2),
        regeneration_score=round(regen_score, 2),
        confidence_score=confidence_score,
        estimated_fair_value=estimated_fair_value,
        avg_comparable_price=avg_comparable_price,
        discount_pct=discount_pct,
        score_drivers=top_drivers,
    )
