"""
fair_value.py — First-principles fair value model for crypto Up/Down markets.

Two model types:
  absolute_strike : P(crypto > fixed_target at expiry) via log-normal approximation
  directional     : P(crypto goes up) via momentum-adjusted 50/50 base

No ML, no black boxes. All formulas are documented inline.
"""

from __future__ import annotations
import math
import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


# ── Normal CDF approximation (no scipy) ───────────────────────────────────────

def _norm_cdf(x: float) -> float:
    """
    Standard normal CDF via Abramowitz & Stegun 26.2.17.
    Maximum error: ~7.5e-8. Accurate enough for probability estimation.
    """
    sign = 1.0 if x >= 0 else -1.0
    ax   = abs(x)
    t    = 1.0 / (1.0 + 0.2316419 * ax)
    poly = t * (0.319381530
           + t * (-0.356563782
           + t * (1.781477937
           + t * (-1.821255978
           + t * 1.330274429))))
    p = 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * ax * ax) * poly
    return p if sign > 0 else 1.0 - p


# ── Fair value result ─────────────────────────────────────────────────────────

@dataclass
class FairValue:
    yes_prob:   float        # 0 – 1
    no_prob:    float        # 0 – 1
    confidence: float        # 0 – 1
    model:      str          # 'lognormal' | 'directional' | 'insufficient_data'
    reason:     str          # human-readable explanation
    penalties:  list[str] = field(default_factory=list)

    def __str__(self) -> str:
        p = f" [penalties: {', '.join(self.penalties)}]" if self.penalties else ""
        return (f"FV(YES={self.yes_prob:.3f} NO={self.no_prob:.3f} "
                f"conf={self.confidence:.2f} model={self.model}){p}")


_NULL_FV = FairValue(0.5, 0.5, 0.0, "insufficient_data", "no model computed")


def compute_fair_value(
    market_type:        str,            # 'absolute_strike' | 'directional'
    direction:          str | None,     # 'above' | 'below' | 'either'
    target_price:       float | None,
    current_price:      float,
    expiry_ts:          float,          # unix timestamp
    now_ts:             float,
    vol_annual:         float | None,   # realised annualised vol (e.g. 0.80 for 80%)
    n_vol_samples:      int,
    momentum_pct_per_min: float,        # signed, %/minute
    ref_price_age:      float,          # seconds
    ob_age:             float,          # seconds
    cfg:                dict,
) -> FairValue:
    """
    Compute the fair probability for YES and NO outcomes.
    """
    penalties: list[str] = []
    confidence = 1.0

    # ── Time to expiry ────────────────────────────────────────────────────────
    t_seconds = expiry_ts - now_ts
    t_minutes = t_seconds / 60.0
    t_years   = t_seconds / (365.25 * 24 * 3600)

    min_t_min = cfg.get("min_time_to_expiry_minutes", 10)
    max_t_hrs = cfg.get("max_time_to_expiry_hours", 72)

    if t_minutes < min_t_min:
        return FairValue(0.5, 0.5, 0.0, "insufficient_data",
                         f"expiry too soon ({t_minutes:.1f}m < {min_t_min}m)")
    if t_minutes > max_t_hrs * 60:
        confidence -= 0.25
        penalties.append(f"long_expiry ({t_minutes/60:.1f}h)")

    # ── Stale data penalties ──────────────────────────────────────────────────
    max_ref_age = cfg.get("max_ref_price_age_seconds", 30)
    if ref_price_age > max_ref_age:
        confidence -= 0.30
        penalties.append(f"stale_ref_price ({ref_price_age:.0f}s)")

    max_ob_age = cfg.get("max_orderbook_age_seconds", 60)
    if ob_age > max_ob_age:
        confidence -= 0.20
        penalties.append(f"stale_orderbook ({ob_age:.0f}s)")

    # ── Volatility checks ─────────────────────────────────────────────────────
    min_vol_samples = cfg.get("vol_min_samples", 8)
    if vol_annual is None or n_vol_samples < min_vol_samples:
        # Fall back to historical crypto vol estimate (BTC ≈ 70% annualised)
        vol_annual = 0.70
        confidence -= 0.20
        penalties.append(f"vol_fallback (only {n_vol_samples} samples)")

    if vol_annual <= 0.01:
        vol_annual = 0.70
        penalties.append("vol_floor_applied")

    if vol_annual > 5.0:
        # Unreasonably high — likely bad data
        vol_annual = 5.0
        confidence -= 0.15
        penalties.append("vol_capped_at_500pct")

    # ── Model dispatch ────────────────────────────────────────────────────────

    if market_type == "absolute_strike" and target_price and current_price > 0:
        fv = _lognormal_model(
            current_price, target_price, direction or "above",
            t_years, vol_annual, momentum_pct_per_min,
            t_minutes,
        )
        model = "lognormal"
        reason = (
            f"spot={current_price:.2f} target={target_price:.2f} "
            f"direction={direction} vol={vol_annual*100:.0f}% "
            f"T={t_minutes:.0f}min mom={momentum_pct_per_min:+.3f}%/min"
        )
    elif market_type == "directional":
        fv = _directional_model(momentum_pct_per_min, t_minutes)
        model = "directional"
        reason = (
            f"directional base=0.50 "
            f"mom={momentum_pct_per_min:+.3f}%/min T={t_minutes:.0f}min"
        )
    else:
        return _NULL_FV

    yes_prob, no_prob = fv

    # Extra penalty if model produces an extreme result
    # (likely error rather than real edge)
    if yes_prob < 0.05 or yes_prob > 0.95:
        confidence -= 0.15
        penalties.append(f"extreme_probability ({yes_prob:.3f})")

    confidence = max(0.0, min(1.0, confidence))

    return FairValue(
        yes_prob   = round(yes_prob, 4),
        no_prob    = round(no_prob, 4),
        confidence = round(confidence, 3),
        model      = model,
        reason     = reason,
        penalties  = penalties,
    )


def _lognormal_model(
    spot:         float,
    target:       float,
    direction:    str,    # 'above' | 'below'
    t_years:      float,
    vol_annual:   float,
    momentum_ppm: float,  # %/min
    t_minutes:    float,
) -> tuple[float, float]:
    """
    P(S_T > target) for log-normal random walk with zero drift.

    Formula:
      d = ln(S / K) / (σ * √T)
      P(S_T > K) = Φ(d)

    Momentum adjustment: the expected drift from recent momentum is
    added as a small shift. Dampened by 0.3 to avoid overclaiming.
    """
    sigma_t = vol_annual * math.sqrt(t_years)
    if sigma_t <= 0:
        return (1.0, 0.0) if spot > target else (0.0, 1.0)

    d = math.log(spot / target) / sigma_t

    # Momentum: expected % move over remaining time → z-score shift
    expected_move_pct = momentum_ppm * t_minutes  # total expected % move
    momentum_z = (expected_move_pct / 100.0) / sigma_t * 0.30  # 0.3 dampening
    momentum_z = max(-0.50, min(0.50, momentum_z))

    p_above = _norm_cdf(d + momentum_z)
    p_above = max(0.02, min(0.98, p_above))

    if direction == "above":
        # YES = price ends above target
        return (p_above, 1.0 - p_above)
    else:
        # YES = price ends below target
        p_below = 1.0 - p_above
        return (p_below, 1.0 - p_below)


def _directional_model(
    momentum_ppm: float,
    t_minutes: float,
) -> tuple[float, float]:
    """
    P(price goes up) = 0.50 + momentum_bias.
    Bias is proportional to expected move scaled by a sensitivity constant.
    Sensitivity = 0.05 per 1% expected move (very conservative).
    """
    expected_move_pct = momentum_ppm * t_minutes
    sensitivity = 0.05 / 1.0  # 5 percentage points per 1% expected move
    bias = expected_move_pct * sensitivity
    bias = max(-0.15, min(0.15, bias))

    p_up = max(0.10, min(0.90, 0.50 + bias))
    return (p_up, 1.0 - p_up)


# ── Edge calculation ──────────────────────────────────────────────────────────

def compute_edge(
    fair_value:      float,    # P(YES) or P(NO)
    executable_price: float,   # best ask to buy the outcome
    spread:          float,
    cfg:             dict,
) -> dict:
    """
    Compute raw and adjusted edge.

    adjusted_edge = fair_value - executable_price
                    - delay_penalty
                    - slippage
                    - safety_margin
    """
    if not (0.0 < executable_price < 1.0):
        return {"raw_edge": None, "adjusted_edge": None}

    raw_edge = fair_value - executable_price

    delay_penalty  = cfg.get("delay_penalty_pct", 0.010)
    slippage       = cfg.get("slippage_pct", 0.005)
    safety_margin  = cfg.get("safety_margin_pct", 0.010)

    cost = delay_penalty + slippage + safety_margin
    adjusted_edge = raw_edge - cost

    return {
        "raw_edge":      round(raw_edge, 4),
        "adjusted_edge": round(adjusted_edge, 4),
        "cost_estimate": round(cost, 4),
        "delay_penalty": delay_penalty,
        "slippage":      slippage,
        "safety_margin": safety_margin,
    }
