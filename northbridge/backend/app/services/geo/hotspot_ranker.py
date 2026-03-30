"""
Hotspot ranker — identifies high-opportunity postcodes/areas based on
aggregated deal scores, planning activity, and regen proximity.
"""
from dataclasses import dataclass


@dataclass
class Hotspot:
    area: str               # postcode prefix or council
    avg_score: float
    listing_count: int
    high_score_count: int   # listings scoring 70+
    planning_count: int
    near_regen: bool
    rank: int


def rank_hotspots(listings_with_scores: list[dict], planning_apps: list[dict]) -> list[Hotspot]:
    """
    Given listings with scores and planning apps, identify top opportunity areas.
    Groups by postcode prefix (first segment, e.g. NE8, SR1).
    """
    area_data: dict[str, dict] = {}

    for listing in listings_with_scores:
        postcode = listing.get("postcode", "") or ""
        prefix = postcode.strip().upper().split(" ")[0]
        if not prefix:
            continue
        if prefix not in area_data:
            area_data[prefix] = {
                "scores": [], "listing_count": 0,
                "high_score_count": 0, "near_regen": False
            }
        score = listing.get("overall_score") or listing.get("score", {}).get("overall_score", 0)
        area_data[prefix]["scores"].append(score)
        area_data[prefix]["listing_count"] += 1
        if score >= 70:
            area_data[prefix]["high_score_count"] += 1
        if listing.get("score", {}).get("regeneration_score", 0) > 30:
            area_data[prefix]["near_regen"] = True

    # Count planning apps per area
    planning_counts: dict[str, int] = {}
    for app in planning_apps:
        postcode = app.get("postcode", "") or ""
        prefix = postcode.strip().upper().split(" ")[0]
        if prefix:
            planning_counts[prefix] = planning_counts.get(prefix, 0) + 1

    hotspots = []
    for area, data in area_data.items():
        scores = data["scores"]
        if not scores:
            continue
        avg = sum(scores) / len(scores)
        hotspots.append(Hotspot(
            area=area,
            avg_score=round(avg, 1),
            listing_count=data["listing_count"],
            high_score_count=data["high_score_count"],
            planning_count=planning_counts.get(area, 0),
            near_regen=data["near_regen"],
            rank=0,
        ))

    # Rank: composite of avg score, high score density, planning activity
    def hotspot_rank_key(h: Hotspot) -> float:
        return (h.avg_score * 0.4 +
                (h.high_score_count / max(h.listing_count, 1)) * 100 * 0.35 +
                min(h.planning_count * 5, 25) * 0.25)

    hotspots.sort(key=hotspot_rank_key, reverse=True)
    for i, h in enumerate(hotspots):
        h.rank = i + 1

    return hotspots[:20]  # top 20 hotspots
