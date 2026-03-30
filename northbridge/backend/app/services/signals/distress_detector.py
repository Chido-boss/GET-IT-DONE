"""
Distress detector — scores a listing's seller motivation level.
Combines keyword analysis, pricing behaviour, and market time signals.
"""
from dataclasses import dataclass
from .keyword_parser import parse_keywords, ParsedKeywords


@dataclass
class DistressResult:
    score: float              # 0-100
    level: str                # low / moderate / high / severe
    signals: list[str]        # human-readable signal descriptions
    keyword_hits: list[str]   # raw keyword matches


LEVEL_THRESHOLDS = {
    "severe": 70,
    "high": 45,
    "moderate": 20,
    "low": 0,
}


def detect_distress(
    title: str = "",
    description: str = "",
    days_on_market: int = 0,
    price_reduction_count: int = 0,
    previous_price: int | None = None,
    asking_price: int = 0,
) -> DistressResult:
    """
    Full distress assessment for a listing.
    Returns a score, level, and list of human-readable signals.
    """
    parsed = parse_keywords(title, description)
    signals = []
    score = parsed.distress_score  # keyword base

    # Keyword signals
    if parsed.distress_hits:
        high_value = {"chain free", "no chain", "motivated seller",
                      "cash buyers only", "repossession", "probate",
                      "executor sale", "vacant possession"}
        high_hits = [h for h in parsed.distress_hits if h in high_value]
        low_hits = [h for h in parsed.distress_hits if h not in high_value]
        if high_hits:
            signals.append(f"Strong seller signals: {', '.join(high_hits)}")
        if low_hits:
            signals.append(f"Additional indicators: {', '.join(low_hits[:3])}")

    # Days on market signals
    if days_on_market >= 120:
        score += 20
        signals.append(f"{days_on_market} days on market — significantly stale listing")
    elif days_on_market >= 60:
        score += 12
        signals.append(f"{days_on_market} days on market — above average time to sell")
    elif days_on_market >= 30:
        score += 5
        signals.append(f"{days_on_market} days on market")

    # Price reduction signals
    if price_reduction_count >= 3:
        score += 25
        signals.append(f"{price_reduction_count} price reductions — highly motivated seller")
    elif price_reduction_count == 2:
        score += 15
        signals.append(f"2 price reductions on this listing")
    elif price_reduction_count == 1:
        score += 8
        signals.append("1 price reduction — seller willing to negotiate")

    # Reduction magnitude
    if previous_price and asking_price and previous_price > asking_price:
        reduction_pct = ((previous_price - asking_price) / previous_price) * 100
        if reduction_pct >= 10:
            score += 15
            signals.append(f"Price dropped {reduction_pct:.1f}% from original ask")
        elif reduction_pct >= 5:
            score += 8
            signals.append(f"Price dropped {reduction_pct:.1f}%")

    score = min(score, 100.0)

    # Determine level
    level = "low"
    for lvl, threshold in LEVEL_THRESHOLDS.items():
        if score >= threshold:
            level = lvl
            break

    return DistressResult(
        score=round(score, 1),
        level=level,
        signals=signals,
        keyword_hits=parsed.distress_hits,
    )
