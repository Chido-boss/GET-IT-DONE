"""
live_trader.py — PLACEHOLDER. Live trading is NOT implemented in V1.

This file exists to define the interface that a live execution module
would need to implement. Do not add real logic here until:

  1. You have 2+ weeks of paper trading data showing consistent positive EV
  2. You have verified Polymarket's terms of service allow automated trading
     in your jurisdiction (UK residents — check current ToS)
  3. You have tested with the smallest possible position sizes
  4. You have independent review of the risk logic

When live trading is added:
  - Requires env var LIVE_TRADING=true (never hardcode)
  - Requires POLYMARKET_API_KEY and POLYMARKET_API_SECRET from environment
  - Never print private keys or secrets to logs
  - Must enforce all risk limits from risk.py
  - Must use limit orders, not market orders
  - Must implement order cancellation on timeout
  - Must implement position reconciliation on startup
  - Start with max_position_size_usd of $10 and scale up only with evidence
"""

import os
import logging

log = logging.getLogger(__name__)

LIVE_ENABLED = os.environ.get("LIVE_TRADING", "").lower() == "true"


class LiveTrader:
    def __init__(self, cfg: dict) -> None:
        if LIVE_ENABLED:
            raise NotImplementedError(
                "Live trading is not implemented in V1. "
                "Run in paper mode until you have evidence of edge."
            )
        log.info("LiveTrader: not enabled (paper mode only in V1)")

    def place_order(self, *args, **kwargs):
        raise NotImplementedError("Live trading not implemented in V1.")

    def cancel_order(self, *args, **kwargs):
        raise NotImplementedError("Live trading not implemented in V1.")

    def get_positions(self):
        raise NotImplementedError("Live trading not implemented in V1.")
