"""
Comparables matching service.
Finds comparable sales for a given postcode/property_type/bedrooms combination.
"""

from __future__ import annotations

import math
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in km between two lat/lng points."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _postcode_prefix(postcode: str) -> str:
    """Return the outward code portion of a postcode (e.g. 'NE8' from 'NE8 1AA')."""
    return postcode.strip().split(" ")[0].upper()


async def match_comparables(
    db: AsyncSession,
    postcode: str,
    property_type: str,
    bedrooms: Optional[int],
    listing_lat: Optional[float] = None,
    listing_lng: Optional[float] = None,
    max_radius_km: float = 1.0,
) -> List:
    """
    Find comparable sales ordered by recency and proximity.

    Matching tiers:
    1. If lat/lng provided: distance-based filter within max_radius_km (expanded if few results)
    2. Postcode prefix match + property type
    3. Broader postcode area (first 2 chars) + property type

    Returns list of ComparableSale ORM objects sorted by (distance, recency).
    """
    from app.models.comparable import ComparableSale

    prefix = _postcode_prefix(postcode)

    # Fetch all comparables matching property type for postcode area
    # We fetch a broader set first, then filter in Python for flexibility
    area_prefix = prefix[:2]  # e.g. "NE" or "SR" or "TS"

    stmt = (
        select(ComparableSale)
        .where(ComparableSale.property_type == property_type)
        .where(ComparableSale.postcode.ilike(f"{area_prefix}%"))
        .order_by(ComparableSale.date_sold.desc())
        .limit(200)
    )
    result = await db.execute(stmt)
    all_area_comps = result.scalars().all()

    if not all_area_comps:
        # Broaden to all property type matches
        stmt2 = (
            select(ComparableSale)
            .where(ComparableSale.property_type == property_type)
            .order_by(ComparableSale.date_sold.desc())
            .limit(50)
        )
        r2 = await db.execute(stmt2)
        all_area_comps = r2.scalars().all()

    if not all_area_comps:
        return []

    # Score and rank each comparable
    scored: List[tuple] = []
    for comp in all_area_comps:
        comp_postcode = (getattr(comp, "postcode", "") or "").upper()
        comp_prefix = _postcode_prefix(comp_postcode)
        comp_bedrooms = getattr(comp, "bedrooms", None)

        # Distance scoring
        distance_km: Optional[float] = None
        if listing_lat and listing_lng:
            # We don't store lat/lng on comparables directly — use postcode prefix heuristic
            # Postcode-exact match gets distance 0, prefix match gets distance 0.5
            if comp_postcode == postcode.upper():
                distance_km = 0.0
            elif comp_prefix == prefix:
                distance_km = 0.3
            else:
                distance_km = max_radius_km * 0.8  # assume within area
        else:
            if comp_postcode == postcode.upper():
                distance_km = 0.0
            elif comp_prefix == prefix:
                distance_km = 0.5
            else:
                distance_km = 2.0

        # Bedroom match bonus (lower = better sort key)
        bedroom_penalty = 0
        if bedrooms is not None and comp_bedrooms is not None:
            bedroom_penalty = abs(comp_bedrooms - bedrooms)
        elif bedrooms is not None and comp_bedrooms is None:
            bedroom_penalty = 1

        # Recency: days since sale (lower = more recent)
        from datetime import date
        sold_date = getattr(comp, "date_sold", None)
        days_ago = (date.today() - sold_date).days if sold_date else 9999

        sort_key = (distance_km or 99, bedroom_penalty, days_ago)
        scored.append((sort_key, comp))

    scored.sort(key=lambda x: x[0])

    # Return top 20 comparables
    return [comp for _, comp in scored[:20]]


async def get_nearby_planning(
    db: AsyncSession,
    postcode: str,
    listing_lat: Optional[float] = None,
    listing_lng: Optional[float] = None,
    radius_km: float = 0.5,
) -> List:
    """
    Return planning applications near a listing.
    Uses postcode prefix match if no lat/lng available.
    """
    from app.models.planning import PlanningApplication

    prefix = _postcode_prefix(postcode)

    stmt = (
        select(PlanningApplication)
        .where(PlanningApplication.postcode.ilike(f"{prefix}%"))
        .order_by(PlanningApplication.date_received.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    apps = result.scalars().all()

    if listing_lat and listing_lng:
        # Filter by distance if we have coordinates
        filtered = []
        for app in apps:
            app_lat = getattr(app, "latitude", None)
            app_lng = getattr(app, "longitude", None)
            if app_lat and app_lng:
                dist = _haversine_km(listing_lat, listing_lng, app_lat, app_lng)
                if dist <= radius_km * 2:  # Generous radius
                    filtered.append(app)
            else:
                filtered.append(app)  # Include if no coords (postcode matched)
        return filtered

    return apps
