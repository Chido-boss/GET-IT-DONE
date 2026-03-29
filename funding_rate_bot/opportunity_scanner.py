"""
Opportunity scanner: filters and ranks funding rate arbitrage opportunities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from config import cfg
from exchange_client import ExchangeClient, FundingRate

if TYPE_CHECKING:
    from risk_manager import RiskManager

logger = logging.getLogger(__name__)

# Volume threshold for considering a market liquid enough (USD)
MIN_24H_VOLUME_USD = 1_000_000.0


@dataclass
class FundingOpportunity:
    symbol: str                    # Base asset, e.g. "SOL"
    perp_exchange: str             # Exchange where we short the perp
    spot_exchange: str             # Exchange where we buy spot (cheapest)
    perp_symbol: str               # Exchange-native perp symbol
    funding_rate: float            # Current 8h funding rate
    annualized_rate: float         # Annualized equivalent
    next_funding_time: str | None  # ISO-8601 next payment time
    spot_price: float
    perp_price: float
    basis_pct: float               # (perp - spot) / spot × 100
    estimated_8h_yield: float      # USD per $1000 notional every 8 hours
    estimated_annual_yield: float  # USD per $1000 notional per year
    liquidity_score: float         # 0–1
    confidence_score: float        # 0–1
    composite_score: float         # Ranking score
    recommended_size_usdc: float   # Suggested trade size in USDC


def _score_opportunity(
    funding_rate: float,
    liquidity_score: float,
    basis_pct: float,
) -> float:
    """
    Composite score for ranking opportunities.

    Weights:
      50% – funding rate (higher = better)
      30% – liquidity score
      20% – basis score (lower basis = better, i.e. less slippage eating yield)
    """
    # Normalise funding rate: treat 0.5% per 8h as ceiling (score 1.0)
    rate_score = min(funding_rate / 0.005, 1.0)

    # Basis score: penalise if perp trades at big premium over spot
    # Negative basis (perp below spot) is ideal
    raw_basis = max(0.0, basis_pct)  # Only penalise positive basis
    basis_score = max(0.0, 1.0 - raw_basis / cfg.basis_max_pct)

    return 0.5 * rate_score + 0.3 * liquidity_score + 0.2 * basis_score


def _liquidity_score(volume_24h: float) -> float:
    """Map 24h volume to a 0-1 score. $1M → 0.1, $10M → 0.5, $100M → 1.0."""
    if volume_24h <= 0:
        return 0.0
    import math
    # Log-linear scale: log10($1M)=6, log10($100M)=8
    log_vol = math.log10(volume_24h)
    score = (log_vol - 6.0) / 2.0  # 6 → 0, 8 → 1
    return max(0.0, min(1.0, score))


async def scan_opportunities(
    exchange_client: ExchangeClient,
    risk_manager: "RiskManager",
    open_symbols: set[str] | None = None,
) -> list[FundingOpportunity]:
    """
    Main scanner entry point.

    1. Fetch funding rates from all exchanges.
    2. Apply filters (rate threshold, basis, volume, already-open).
    3. Score and rank remaining candidates.
    4. Return sorted list of FundingOpportunity.
    """
    if open_symbols is None:
        open_symbols = set()

    all_rates = await exchange_client.get_all_funding_rates()
    logger.info("Fetched %d funding rate records", len(all_rates))

    # --- Step 1: Pre-filter by minimum rate ---
    candidates = [r for r in all_rates if r.funding_rate >= cfg.min_funding_rate]
    logger.info("%d rates above minimum threshold (%.4f%%)", len(candidates), cfg.min_funding_rate * 100)

    # --- Step 2: Resolve base symbols and filter already-open ---
    filtered: list[tuple[FundingRate, str]] = []
    for rate in candidates:
        base = _extract_base_symbol(rate.exchange, rate.symbol)
        logger.info("  Candidate: %s %s -> base=%s rate=%.6f", rate.exchange, rate.symbol, base, rate.funding_rate)
        if not base:
            logger.info("  SKIP: could not extract base symbol from %s %s", rate.exchange, rate.symbol)
            continue
        if base in open_symbols:
            continue
        filtered.append((rate, base))
    logger.info("After symbol extraction: %d candidates pass to enrichment", len(filtered))

    # --- Step 3: Fetch spot prices, perp prices, and volumes concurrently ---
    import asyncio

    async def _enrich(rate: FundingRate, base: str) -> FundingOpportunity | None:
        try:
            # Get prices — use public API fallbacks, never hard-fail
            spot_exchange, spot_price = await exchange_client.get_best_spot_price(base)
            if spot_price <= 0:
                # Try public perp price as proxy for spot
                perp_sym = rate.symbol if rate.symbol.endswith("USDT") else f"{base}USDT"
                spot_price = await exchange_client.coinglass.get_public_perp_price(perp_sym)
                spot_exchange = "bybit-public"

            perp_price = await exchange_client.get_perp_price(rate.exchange, rate.symbol)
            if perp_price <= 0:
                perp_sym = rate.symbol if rate.symbol.endswith("USDT") else f"{base}USDT"
                perp_price = await exchange_client.coinglass.get_public_perp_price(perp_sym)
            if perp_price <= 0:
                perp_price = spot_price  # last resort fallback

            # If still no price, use a placeholder so we can at least show the rate
            if spot_price <= 0:
                spot_price = 1.0
                perp_price = 1.0
                spot_exchange = "unknown"

            basis_pct = ((perp_price - spot_price) / spot_price) * 100.0 if spot_price > 0 else 0.0

            # Skip only if basis is wildly high (data error)
            if basis_pct > cfg.basis_max_pct * 10:
                return None

            # Get volume — never block on this
            vol = 0.0
            try:
                perp_sym = rate.symbol if rate.symbol.endswith("USDT") else f"{base}USDT"
                vol = await exchange_client.coinglass.get_public_volume(perp_sym)
            except Exception:
                vol = 0.0

            liq_score = _liquidity_score(vol) if vol > 0 else 0.5
            comp_score = _score_opportunity(rate.funding_rate, liq_score, basis_pct)

            est_8h = rate.funding_rate * 1000.0
            est_annual = est_8h * cfg.funding_periods_per_year

            portfolio_value = await exchange_client.get_balance()
            rec_size = risk_manager.compute_position_size_from_portfolio(
                funding_rate=rate.funding_rate,
                portfolio_value=portfolio_value,
            )

            logger.info("  OPPORTUNITY: %s rate=%.6f APY=%.1f%% basis=%.3f%%",
                       base, rate.funding_rate, rate.annualized_rate * 100, basis_pct)

            return FundingOpportunity(
                symbol=base,
                perp_exchange=rate.exchange,
                spot_exchange=spot_exchange,
                perp_symbol=rate.symbol,
                funding_rate=rate.funding_rate,
                annualized_rate=rate.annualized_rate,
                next_funding_time=rate.next_funding_time,
                spot_price=spot_price,
                perp_price=perp_price,
                basis_pct=basis_pct,
                estimated_8h_yield=est_8h,
                estimated_annual_yield=est_annual,
                liquidity_score=liq_score,
                confidence_score=1.0,
                composite_score=comp_score,
                recommended_size_usdc=rec_size,
            )
        except Exception as exc:
            logger.info("Enrichment failed for %s %s: %s", rate.exchange, base, exc)
            return None

    tasks = [_enrich(rate, base) for rate, base in filtered]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    opportunities: list[FundingOpportunity] = []
    for r in raw_results:
        if isinstance(r, FundingOpportunity):
            opportunities.append(r)

    # Sort by composite score descending
    opportunities.sort(key=lambda o: o.composite_score, reverse=True)
    logger.info(
        "scan_opportunities: %d qualifying opportunities found", len(opportunities)
    )
    return opportunities


def check_exit_conditions(
    position: dict,
    current_funding_rate: float,
    below_threshold_count: int,
) -> tuple[bool, str]:
    """
    Determine whether an open position should be closed.

    Returns (should_exit, reason).
    """
    # --- Rule 1: Funding rate has stayed below exit threshold long enough ---
    if current_funding_rate < cfg.exit_funding_rate:
        if below_threshold_count >= cfg.exit_consecutive_cycles:
            return (
                True,
                f"Funding rate {current_funding_rate:.6f} below exit threshold "
                f"for {below_threshold_count} consecutive cycles",
            )

    # --- Rule 2: Basis inversion risk ---
    # Computed live by the monitor; passed in via current_funding_rate context
    # We check basis separately in the monitor task using latest prices.

    # --- Rule 3: Maximum position age ---
    entry_time_str = position.get("entry_time", "")
    if entry_time_str:
        try:
            entry_dt = datetime.fromisoformat(entry_time_str)
            age_days = (datetime.now(timezone.utc) - entry_dt).total_seconds() / 86400.0
            if age_days > cfg.max_position_age_days:
                return (
                    True,
                    f"Position age {age_days:.1f} days exceeds maximum {cfg.max_position_age_days} days",
                )
        except (ValueError, TypeError):
            pass

    return (False, "")


def check_basis_exit(
    entry_spot_price: float,
    entry_perp_price: float,
    current_spot_price: float,
    current_perp_price: float,
) -> tuple[bool, str]:
    """
    Check whether basis has inverted beyond the exit threshold.
    A large basis inversion means the perp has moved far below spot,
    creating directional risk that outweighs funding income.
    """
    if current_spot_price <= 0 or entry_spot_price <= 0:
        return (False, "")

    entry_basis = (entry_perp_price - entry_spot_price) / entry_spot_price * 100.0
    current_basis = (current_perp_price - current_spot_price) / current_spot_price * 100.0
    basis_change = current_basis - entry_basis

    # Negative basis change means perp fell relative to spot (bad for our short)
    if basis_change < -cfg.basis_exit_pct:
        return (
            True,
            f"Basis inverted by {abs(basis_change):.3f}% (threshold {cfg.basis_exit_pct}%)",
        )
    return (False, "")


def _extract_base_symbol(exchange: str, symbol: str) -> str | None:
    """
    Convert exchange-native symbol to base asset name.

    Bybit: "SOLUSDT" -> "SOL"
    OKX:   "SOL-USDT-SWAP" -> "SOL"
    CoinGlass: "SOL" -> "SOL"
    """
    if exchange == "bybit":
        for quote in ("USDT", "USDC", "USD", "BUSD"):
            if symbol.endswith(quote):
                base = symbol[: -len(quote)]
                if base:
                    return base
        # Symbol already stripped of quote currency (e.g. "SOL" not "SOLUSDT")
        return symbol if symbol else None
    if exchange == "okx":
        parts = symbol.split("-")
        if parts:
            return parts[0]
        return None
    # CoinGlass and others: assume symbol is already the base
    return symbol if symbol else None
