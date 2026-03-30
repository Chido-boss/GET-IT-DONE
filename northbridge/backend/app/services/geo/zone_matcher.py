"""
Regeneration zone matcher — finds nearest zone and scores proximity.
"""
from dataclasses import dataclass
from .distance_calculator import calculate_distance, postcode_to_approximate_coords


@dataclass
class ZoneMatch:
    zone_id: str
    zone_name: str
    distance_km: float
    within_zone: bool
    regen_score: float
    signal: str


def match_to_regen_zones(
    lat: float | None,
    lng: float | None,
    postcode: str | None,
    zones: list[dict],
) -> ZoneMatch | None:
    """
    Find the nearest regeneration zone to a listing.
    Returns None if no zones provided or no coordinates available.
    """
    # Try to get coordinates
    eff_lat, eff_lng = lat, lng
    if (eff_lat is None or eff_lng is None) and postcode:
        coords = postcode_to_approximate_coords(postcode)
        if coords:
            eff_lat, eff_lng = coords

    if eff_lat is None or eff_lng is None:
        return None

    best: ZoneMatch | None = None
    best_dist = float("inf")

    for zone in zones:
        zlat = zone.get("center_lat")
        zlng = zone.get("center_lng")
        radius = zone.get("radius_km", 1.0) or 1.0

        if zlat is None or zlng is None:
            continue

        dist = calculate_distance(eff_lat, eff_lng, zlat, zlng, radius)
        if dist is None:
            continue

        if dist.distance_km < best_dist:
            best_dist = dist.distance_km
            regen_score = _score_proximity(dist.distance_km, radius)
            if dist.within_zone:
                signal = f"Inside {zone['name']} regeneration zone"
            elif dist.distance_km <= radius * 2:
                signal = f"{dist.distance_km:.1f}km from {zone['name']} — adjacent zone"
            elif dist.distance_km <= radius * 5:
                signal = f"{dist.distance_km:.1f}km from {zone['name']}"
            else:
                signal = f"{dist.distance_km:.1f}km from nearest regen zone ({zone['name']})"

            best = ZoneMatch(
                zone_id=str(zone.get("id", "")),
                zone_name=zone["name"],
                distance_km=dist.distance_km,
                within_zone=dist.within_zone,
                regen_score=regen_score,
                signal=signal,
            )

    return best


def _score_proximity(distance_km: float, zone_radius_km: float) -> float:
    """Score 0-100 based on proximity to zone center."""
    if distance_km <= zone_radius_km:
        return 90.0
    elif distance_km <= zone_radius_km * 1.5:
        return 70.0
    elif distance_km <= zone_radius_km * 3:
        return 45.0
    elif distance_km <= zone_radius_km * 5:
        return 20.0
    elif distance_km <= 10:
        return 8.0
    return 0.0
