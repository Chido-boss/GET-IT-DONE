"""
Polymarket CLOB API client using httpx (async HTTP).

Handles authentication, market fetching, orderbook queries, and order placement.
In paper mode, all order placements are simulated with realistic slippage.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx

from config import cfg

logger = logging.getLogger(__name__)


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class OrderbookLevel:
    price: float
    size: float


@dataclass
class Orderbook:
    market_id: str
    bids: List[OrderbookLevel]  # sorted best-first (highest price first)
    asks: List[OrderbookLevel]  # sorted best-first (lowest price first)
    timestamp: float = field(default_factory=time.time)

    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return None

    def available_at_levels(self, side: str, n_levels: int = 3) -> float:
        """Return total USDC available at the top n price levels."""
        levels = self.asks if side.upper() == "BUY" else self.bids
        return sum(lv.price * lv.size for lv in levels[:n_levels])

    def imbalance(self) -> float:
        """
        Orderbook imbalance: positive means more bid pressure.
        imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)
        Uses top 5 levels.
        """
        bid_vol = sum(lv.size for lv in self.bids[:5])
        ask_vol = sum(lv.size for lv in self.asks[:5])
        total = bid_vol + ask_vol
        if total == 0:
            return 0.0
        return (bid_vol - ask_vol) / total


@dataclass
class MarketInfo:
    market_id: str          # condition_id or token_id
    question: str
    asset: str              # "BTC" or "ETH"
    contract_type: str      # "5min_up", "5min_down", "15min_up", "15min_down"
    yes_token_id: str
    no_token_id: str
    end_date_iso: str
    active: bool
    closed: bool
    liquidity: float        # estimated total USDC
    volume: float
    # Current prices (updated live)
    yes_price: float = 0.0
    no_price: float = 0.0


@dataclass
class OrderResult:
    order_id: str
    market_id: str
    side: str
    size: float
    price: float
    filled_price: float     # actual fill price after slippage
    paper: bool
    timestamp: float = field(default_factory=time.time)


@dataclass
class PaperPortfolio:
    usdc_balance: float
    positions: Dict[str, float] = field(default_factory=dict)  # token_id -> shares held
    total_pnl: float = 0.0
    trade_count: int = 0


# ── Paper trading simulator ────────────────────────────────────────────────────

class PaperSimulator:
    """Simulates order execution with slippage and virtual portfolio tracking."""

    def __init__(self, starting_balance: float = cfg.PAPER_STARTING_BALANCE) -> None:
        self._portfolio = PaperPortfolio(usdc_balance=starting_balance)
        self._order_counter = 0
        self._lock = asyncio.Lock()

    @property
    def portfolio(self) -> PaperPortfolio:
        return self._portfolio

    async def place_order(
        self,
        market_id: str,
        token_id: str,
        side: str,
        size_usdc: float,
        price: float,
    ) -> Optional[OrderResult]:
        """
        Simulate order with slippage.
        side: "BUY" or "SELL"
        price: target price (0-1 for binary outcomes)
        size_usdc: USDC amount to spend (BUY) or receive (SELL)
        """
        async with self._lock:
            slippage = cfg.PAPER_SLIPPAGE_PCT
            if side.upper() == "BUY":
                filled_price = min(price * (1 + slippage), 1.0)
                shares = size_usdc / filled_price
                cost = size_usdc

                if cost > self._portfolio.usdc_balance:
                    logger.warning(
                        "Paper: insufficient balance (need %.2f, have %.2f)",
                        cost, self._portfolio.usdc_balance,
                    )
                    return None

                self._portfolio.usdc_balance -= cost
                self._portfolio.positions[token_id] = (
                    self._portfolio.positions.get(token_id, 0.0) + shares
                )
            else:  # SELL
                filled_price = max(price * (1 - slippage), 0.0)
                shares_held = self._portfolio.positions.get(token_id, 0.0)
                shares_to_sell = size_usdc / price if price > 0 else 0.0
                shares_to_sell = min(shares_to_sell, shares_held)

                if shares_to_sell <= 0:
                    logger.warning("Paper: no shares to sell for %s", token_id)
                    return None

                proceeds = shares_to_sell * filled_price
                self._portfolio.usdc_balance += proceeds
                self._portfolio.positions[token_id] = shares_held - shares_to_sell

            self._order_counter += 1
            self._portfolio.trade_count += 1
            order_id = f"PAPER-{market_id[:8]}-{self._order_counter}"

            logger.info(
                "Paper order %s: %s %s size=%.2f USDC @ %.4f (fill=%.4f) balance=%.2f",
                order_id, side, market_id[:12], size_usdc, price, filled_price,
                self._portfolio.usdc_balance,
            )

            return OrderResult(
                order_id=order_id,
                market_id=market_id,
                side=side,
                size=size_usdc,
                price=price,
                filled_price=filled_price,
                paper=True,
            )

    async def resolve_position(
        self,
        token_id: str,
        outcome_price: float,
    ) -> float:
        """Settle a position at outcome_price (1.0 if YES wins, 0.0 if NO wins)."""
        async with self._lock:
            shares = self._portfolio.positions.pop(token_id, 0.0)
            if shares == 0:
                return 0.0
            proceeds = shares * outcome_price
            self._portfolio.usdc_balance += proceeds
            return proceeds

    def get_balance(self) -> float:
        return self._portfolio.usdc_balance


# ── API client ────────────────────────────────────────────────────────────────

class PolymarketClient:
    """
    Async Polymarket CLOB client.

    Authentication uses L1 HMAC-SHA256 signing when credentials are present.
    All order placements route through PaperSimulator in paper mode.
    """

    _MAX_RPS = 10
    _RETRY_CODES = {429, 500, 502, 503, 504}
    _MAX_RETRIES = 4
    _BACKOFF_BASE = 1.0  # seconds

    def __init__(self) -> None:
        self._base_url = cfg.POLYMARKET_CLOB_URL.rstrip("/")
        self._gamma_url = cfg.POLYMARKET_GAMMA_URL.rstrip("/")
        self._semaphore = asyncio.Semaphore(self._MAX_RPS)
        self._paper = cfg.PAPER_MODE
        self._simulator = PaperSimulator() if self._paper else None
        self._http: Optional[httpx.AsyncClient] = None
        self._known_markets: Dict[str, MarketInfo] = {}

    async def __aenter__(self) -> PolymarketClient:
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"Content-Type": "application/json"},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._http:
            await self._http.aclose()

    # ── Auth helpers ──────────────────────────────────────────────────────────

    def _sign_request(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """Generate L1 authentication headers (HMAC-SHA256)."""
        if not cfg.POLYMARKET_API_KEY:
            return {}

        timestamp = str(int(time.time() * 1000))
        message = timestamp + method.upper() + path + (body or "")
        try:
            secret_bytes = base64.b64decode(cfg.POLYMARKET_API_SECRET)
        except Exception:
            secret_bytes = cfg.POLYMARKET_API_SECRET.encode()

        signature = hmac.new(secret_bytes, message.encode(), hashlib.sha256)
        sig_b64 = base64.b64encode(signature.digest()).decode()

        return {
            "POLY-API-KEY": cfg.POLYMARKET_API_KEY,
            "POLY-SIGNATURE": sig_b64,
            "POLY-TIMESTAMP": timestamp,
            "POLY-PASSPHRASE": cfg.POLYMARKET_API_PASSPHRASE,
        }

    # ── HTTP layer ────────────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict] = None,
        json_body: Optional[Dict] = None,
        auth: bool = False,
    ) -> Any:
        """Make an authenticated HTTP request with retry logic."""
        if self._http is None:
            raise RuntimeError("Client not initialised — use async with")

        path = url.replace(self._base_url, "").replace(self._gamma_url, "")
        body_str = json.dumps(json_body) if json_body else ""
        extra_headers = self._sign_request(method, path, body_str) if auth else {}

        for attempt in range(self._MAX_RETRIES):
            async with self._semaphore:
                try:
                    resp = await self._http.request(
                        method,
                        url,
                        params=params,
                        json=json_body,
                        headers=extra_headers,
                    )
                    if resp.status_code in self._RETRY_CODES:
                        wait = self._BACKOFF_BASE * (2 ** attempt)
                        logger.warning(
                            "HTTP %d from %s — retry %d in %.1fs",
                            resp.status_code, url, attempt + 1, wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    return resp.json()
                except httpx.HTTPStatusError as exc:
                    if attempt == self._MAX_RETRIES - 1:
                        logger.error("HTTP error after %d retries: %s", self._MAX_RETRIES, exc)
                        raise
                    await asyncio.sleep(self._BACKOFF_BASE * (2 ** attempt))
                except httpx.RequestError as exc:
                    if attempt == self._MAX_RETRIES - 1:
                        logger.error("Request error after %d retries: %s", self._MAX_RETRIES, exc)
                        raise
                    await asyncio.sleep(self._BACKOFF_BASE * (2 ** attempt))
        raise RuntimeError(f"Request failed after {self._MAX_RETRIES} attempts: {url}")

    # ── Market discovery ──────────────────────────────────────────────────────

    async def get_markets(self) -> List[MarketInfo]:
        """
        Fetch all active BTC/ETH up/down markets (5-min and 15-min).
        Uses Gamma API for market metadata and CLOB for pricing.
        """
        markets: List[MarketInfo] = []

        try:
            # Query Gamma API for crypto price prediction markets
            for keyword in ["BTC", "ETH"]:
                data = await self._request(
                    "GET",
                    f"{self._gamma_url}/markets",
                    params={
                        "active": "true",
                        "closed": "false",
                        "tag_slug": "crypto",
                        "limit": 100,
                    },
                )

                raw_markets = data if isinstance(data, list) else data.get("markets", [])
                for m in raw_markets:
                    info = self._parse_market(m, keyword)
                    if info:
                        markets.append(info)

        except Exception as exc:
            logger.warning("Failed to fetch live markets (%s); using cached.", exc)
            return list(self._known_markets.values())

        # Update cache
        for m in markets:
            self._known_markets[m.market_id] = m

        logger.debug("Fetched %d BTC/ETH markets", len(markets))
        return markets

    def _parse_market(self, raw: Dict, asset_keyword: str) -> Optional[MarketInfo]:
        """Parse a Gamma API market dict into MarketInfo."""
        question: str = raw.get("question", "") or raw.get("title", "") or ""
        if asset_keyword.upper() not in question.upper():
            return None

        # Detect contract type from question text
        q_lower = question.lower()
        if "15" in q_lower and ("up" in q_lower or "higher" in q_lower or "above" in q_lower):
            contract_type = "15min_up"
        elif "15" in q_lower and ("down" in q_lower or "lower" in q_lower or "below" in q_lower):
            contract_type = "15min_down"
        elif "5" in q_lower and ("up" in q_lower or "higher" in q_lower or "above" in q_lower):
            contract_type = "5min_up"
        elif "5" in q_lower and ("down" in q_lower or "lower" in q_lower or "below" in q_lower):
            contract_type = "5min_down"
        else:
            return None  # Not a short-duration up/down contract

        tokens = raw.get("tokens", []) or raw.get("outcomes", [])
        if len(tokens) < 2:
            return None

        yes_token = next((t for t in tokens if t.get("outcome", "").upper() == "YES"), tokens[0])
        no_token = next((t for t in tokens if t.get("outcome", "").upper() == "NO"), tokens[-1])

        return MarketInfo(
            market_id=raw.get("conditionId") or raw.get("id", ""),
            question=question,
            asset=asset_keyword.upper(),
            contract_type=contract_type,
            yes_token_id=yes_token.get("token_id", yes_token.get("id", "")),
            no_token_id=no_token.get("token_id", no_token.get("id", "")),
            end_date_iso=raw.get("endDate", raw.get("end_date_iso", "")),
            active=raw.get("active", True),
            closed=raw.get("closed", False),
            liquidity=float(raw.get("liquidity", 0)),
            volume=float(raw.get("volume", 0)),
            yes_price=float(yes_token.get("price", 0.5)),
            no_price=float(no_token.get("price", 0.5)),
        )

    # ── Orderbook ─────────────────────────────────────────────────────────────

    async def get_orderbook(self, token_id: str) -> Optional[Orderbook]:
        """Fetch L2 orderbook for a token from CLOB API."""
        try:
            data = await self._request(
                "GET",
                f"{self._base_url}/book",
                params={"token_id": token_id},
            )
            return self._parse_orderbook(token_id, data)
        except Exception as exc:
            logger.debug("Orderbook fetch failed for %s: %s", token_id[:12], exc)
            return None

    def _parse_orderbook(self, token_id: str, raw: Dict) -> Orderbook:
        def _levels(lst: List) -> List[OrderbookLevel]:
            out = []
            for item in lst or []:
                try:
                    out.append(OrderbookLevel(
                        price=float(item.get("price", 0)),
                        size=float(item.get("size", 0)),
                    ))
                except (ValueError, TypeError):
                    pass
            return out

        bids = sorted(_levels(raw.get("bids", [])), key=lambda x: x.price, reverse=True)
        asks = sorted(_levels(raw.get("asks", [])), key=lambda x: x.price)
        return Orderbook(market_id=token_id, bids=bids, asks=asks)

    async def get_market_price(self, token_id: str) -> Tuple[Optional[float], Optional[float]]:
        """Return (best_bid, best_ask) for a token. Returns (None, None) on failure."""
        ob = await self.get_orderbook(token_id)
        if ob is None:
            return None, None
        return ob.best_bid, ob.best_ask

    # ── Portfolio / balance ───────────────────────────────────────────────────

    async def get_portfolio_balance(self) -> float:
        """Return available USDC balance."""
        if self._paper:
            return self._simulator.get_balance()

        if not cfg.POLYMARKET_API_KEY:
            logger.warning("No API credentials configured; returning 0 balance.")
            return 0.0

        try:
            data = await self._request(
                "GET",
                f"{self._base_url}/balance-allowance",
                params={"asset_type": "USDC"},
                auth=True,
            )
            return float(data.get("balance", 0))
        except Exception as exc:
            logger.error("Balance fetch failed: %s", exc)
            return 0.0

    # ── Order management ──────────────────────────────────────────────────────

    async def place_order(
        self,
        market_id: str,
        token_id: str,
        side: str,
        size_usdc: float,
        price: float,
        order_type: str = "GTC",
    ) -> Optional[OrderResult]:
        """
        Place a limit order on Polymarket.
        In paper mode, routes to PaperSimulator.

        side: "BUY" or "SELL"
        size_usdc: USDC amount
        price: limit price (0.0 to 1.0)
        order_type: "GTC" (good-till-cancel) or "FOK" (fill-or-kill)
        """
        if self._paper:
            return await self._simulator.place_order(
                market_id=market_id,
                token_id=token_id,
                side=side,
                size_usdc=size_usdc,
                price=price,
            )

        if not cfg.POLYMARKET_API_KEY:
            logger.error("Cannot place live order: no API credentials.")
            return None

        # Build CLOB order payload
        shares = size_usdc / price if price > 0 else 0
        body = {
            "orderType": order_type,
            "tokenId": token_id,
            "side": side.upper(),
            "price": str(round(price, 4)),
            "size": str(round(shares, 2)),
            "feeRateBps": "0",
            "nonce": str(int(time.time() * 1000)),
            "expiration": "0",
            "makerAddress": cfg.WALLET_ADDRESS,
        }

        try:
            resp = await self._request(
                "POST",
                f"{self._base_url}/order",
                json_body=body,
                auth=True,
            )
            order_id = resp.get("orderID") or resp.get("order_id", "unknown")
            fill_price = float(resp.get("fillPrice", price))
            logger.info(
                "Live order placed: %s %s %s size=%.2f @ %.4f (fill=%.4f)",
                order_id, side, token_id[:12], size_usdc, price, fill_price,
            )
            return OrderResult(
                order_id=order_id,
                market_id=market_id,
                side=side,
                size=size_usdc,
                price=price,
                filled_price=fill_price,
                paper=False,
            )
        except Exception as exc:
            logger.error("Order placement failed: %s", exc)
            return None

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True on success."""
        if self._paper:
            logger.debug("Paper: cancel order %s (no-op)", order_id)
            return True

        try:
            await self._request(
                "DELETE",
                f"{self._base_url}/order/{order_id}",
                auth=True,
            )
            return True
        except Exception as exc:
            logger.warning("Cancel order %s failed: %s", order_id, exc)
            return False

    async def get_open_orders(self) -> List[Dict]:
        """Return list of open orders."""
        if self._paper:
            return []

        try:
            data = await self._request(
                "GET",
                f"{self._base_url}/orders",
                params={"status": "LIVE"},
                auth=True,
            )
            return data if isinstance(data, list) else data.get("orders", [])
        except Exception as exc:
            logger.error("get_open_orders failed: %s", exc)
            return []

    async def get_positions(self) -> List[Dict]:
        """Return list of current on-chain positions."""
        if self._paper:
            pos = self._simulator.portfolio.positions
            return [
                {"token_id": tid, "shares": shares}
                for tid, shares in pos.items()
                if shares > 0
            ]

        try:
            data = await self._request(
                "GET",
                f"{self._base_url}/positions",
                auth=True,
            )
            return data if isinstance(data, list) else data.get("positions", [])
        except Exception as exc:
            logger.error("get_positions failed: %s", exc)
            return []

    # ── Convenience ───────────────────────────────────────────────────────────

    @property
    def paper_simulator(self) -> Optional[PaperSimulator]:
        return self._simulator

    def get_cached_markets(self) -> Dict[str, MarketInfo]:
        return dict(self._known_markets)
