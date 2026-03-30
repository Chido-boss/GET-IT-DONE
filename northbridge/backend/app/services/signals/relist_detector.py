"""
Relist detector — identifies when a property has previously been listed and withdrawn.
High relist count = motivated seller + potential negotiation leverage.
"""
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class RelistResult:
    relist_count: int
    score_boost: float
    signal: str | None


def detect_relist(
    price_reduction_count: int,
    days_on_market: int,
    date_listed: date | None,
    status_history: list[dict] | None = None,
) -> RelistResult:
    """
    Estimate relist behaviour from available signals.
    In a full implementation, status_history would contain previous listings.
    """
    # Without full listing history, infer from available signals
    relist_count = 0
    score_boost = 0.0
    signal = None

    # Heuristic: long DOM + multiple reductions suggests likely relisted
    if days_on_market >= 180 and price_reduction_count >= 2:
        relist_count = 1
        score_boost = 15.0
        signal = f"Pattern suggests relisting: {days_on_market} DOM with {price_reduction_count} reductions"
    elif days_on_market >= 365:
        relist_count = 1
        score_boost = 20.0
        signal = f"Over 12 months on market — likely relisted or previously withdrawn"

    # If we have actual history
    if status_history:
        withdrawn_count = sum(1 for h in status_history if h.get("status") == "withdrawn")
        if withdrawn_count > 0:
            relist_count = withdrawn_count
            score_boost = min(withdrawn_count * 12.0, 35.0)
            signal = f"Relisted {withdrawn_count} time(s) — seller struggling to sell at asking price"

    return RelistResult(
        relist_count=relist_count,
        score_boost=score_boost,
        signal=signal,
    )
