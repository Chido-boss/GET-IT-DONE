"""
Deal explainer — generates human-readable explanation of why a deal scored the way it did.
Every score must be explainable. No black boxes.
"""
from dataclasses import dataclass


@dataclass
class ScoreDriver:
    label: str
    impact: float      # 0-100, how much this contributed to overall score
    icon: str
    category: str      # bmv / distress / momentum / planning / regen / confidence


def explain_score(
    bmv_score: float,
    distress_score: float,
    momentum_score: float,
    planning_score: float,
    regeneration_score: float,
    confidence_score: float,
    discount_pct: float | None,
    avg_comparable_price: int | None,
    asking_price: int,
    distress_signals: list[str] | None,
    days_on_market: int | None,
    price_reduction_count: int,
    planning_signals: list[str] | None,
    regen_zone_name: str | None,
    regen_distance_km: float | None,
) -> list[ScoreDriver]:
    """
    Generate a ranked list of score drivers explaining the deal's score.
    Returns top 5, sorted by impact.
    """
    drivers: list[ScoreDriver] = []

    # BMV driver
    if bmv_score >= 20 and discount_pct and avg_comparable_price:
        if discount_pct >= 20:
            label = f"Asking price is {discount_pct:.0f}% below Land Registry average of £{avg_comparable_price:,}"
            icon = "🔻"
        elif discount_pct >= 10:
            label = f"{discount_pct:.1f}% below estimated market value (avg: £{avg_comparable_price:,})"
            icon = "📉"
        else:
            label = f"Slightly below market average (£{avg_comparable_price:,})"
            icon = "📊"
        drivers.append(ScoreDriver(label=label, impact=bmv_score, icon=icon, category="bmv"))

    # Distress driver
    if distress_score >= 15:
        if distress_signals:
            top_signals = ", ".join(distress_signals[:2])
            label = f"Distress signals: {top_signals}"
        else:
            label = "Seller motivation indicators detected in listing"
        icon = "⚠️" if distress_score >= 40 else "🔔"
        drivers.append(ScoreDriver(label=label, impact=distress_score, icon=icon, category="distress"))

    # Momentum driver
    if momentum_score >= 15:
        if (days_on_market or 0) >= 60 and price_reduction_count >= 1:
            label = f"{days_on_market} days on market with {price_reduction_count} price reduction{'s' if price_reduction_count > 1 else ''}"
        elif (days_on_market or 0) >= 60:
            label = f"{days_on_market} days on market — negotiation leverage likely"
        elif price_reduction_count >= 2:
            label = f"{price_reduction_count} price reductions — seller under pressure"
        else:
            label = "Listing momentum suggests negotiable position"
        drivers.append(ScoreDriver(label=label, impact=momentum_score, icon="📅", category="momentum"))

    # Planning driver
    if planning_score >= 20:
        if planning_signals:
            sigs = ", ".join(planning_signals[:2])
            label = f"Planning activity nearby: {sigs}"
        else:
            label = "Planning applications detected in vicinity"
        drivers.append(ScoreDriver(label=label, impact=planning_score, icon="🏗️", category="planning"))

    # Regeneration driver
    if regeneration_score >= 15:
        if regen_zone_name and regen_distance_km is not None:
            if regen_distance_km <= 0.5:
                label = f"Inside {regen_zone_name} regeneration zone"
            else:
                label = f"{regen_distance_km:.1f}km from {regen_zone_name} — regeneration uplift potential"
        else:
            label = "Property near active regeneration zone"
        icon = "🔄" if regeneration_score >= 60 else "📍"
        drivers.append(ScoreDriver(label=label, impact=regeneration_score, icon=icon, category="regen"))

    # Low confidence warning
    if confidence_score < 40:
        drivers.append(ScoreDriver(
            label=f"Limited comparables data — score confidence {confidence_score:.0f}%",
            impact=0,
            icon="⚡",
            category="confidence",
        ))

    # Sort by impact descending, take top 5
    drivers.sort(key=lambda d: d.impact, reverse=True)
    return drivers[:5]


def format_drivers_for_api(drivers: list[ScoreDriver]) -> list[dict]:
    return [
        {"label": d.label, "impact": round(d.impact, 1), "icon": d.icon, "category": d.category}
        for d in drivers
    ]
