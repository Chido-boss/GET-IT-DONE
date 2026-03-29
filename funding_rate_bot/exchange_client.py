"""
Multi-exchange async client for Bybit V5, OKX, and the CoinGlass public API.
In paper mode a PaperSimulator shadows all order calls with virtual accounting.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from config import Config, cfg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class FundingRate:
    exchange: str
    symbol: str
    funding_rate: float          # per 8-hour period (e.g. 0.0003 = 0.03%)
    annualized_rate: float       # funding_rate * 1095
    next_funding_time: str | None = None   # ISO-8601 UTC


@dataclass
class OrderbookLevel:
    price: float
    size: float


@dataclass
class Orderbook:
    symbol: str
    bids: list[OrderbookLevel]
    asks: list[OrderbookLevel]

    @property
    def best_bid(self) -> float:
        return self.bids[0].price if self.bids else 0.0

    @property
    def best_ask(self) -> float:
        return self.asks[0].price if self.asks else 0.0

    @property
    def mid_price(self) -> float:
        if self.bids and self.asks:
            return (self.best_bid + self.best_ask) / 2.0
        return 0.0


@dataclass
class PlacedOrder:
    order_id: str
    symbol: str
    side: str
    size: float
    price: float
    status: str
    exchange: str
    market_type: str  # "spot" | "perp"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_BYBIT_BASE = "https://api.bybit.com"
_OKX_BASE = "https://www.okx.com"
_COINGLASS_BASE = "https://open-api.coinglass.com"

_RECV_WINDOW = "5000"
_MAX_RETRIES = 4
_BACKOFF_BASE = 1.0


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    semaphore: asyncio.Semaphore,
    **kwargs: Any,
) -> dict[str, Any]:
    """Perform an HTTP request respecting the semaphore and retrying on 429/5xx."""
    for attempt in range(_MAX_RETRIES):
        async with semaphore:
            try:
                resp = await client.request(method, url, timeout=10.0, **kwargs)
            except httpx.RequestError as exc:
                logger.warning("Request error (attempt %d): %s", attempt + 1, exc)
                if attempt == _MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(_BACKOFF_BASE * (2 ** attempt))
                continue

        if resp.status_code == 429 or resp.status_code >= 500:
            wait = _BACKOFF_BASE * (2 ** attempt)
            logger.warning(
                "HTTP %s from %s – retrying in %.1fs", resp.status_code, url, wait
            )
            await asyncio.sleep(wait)
            continue

        resp.raise_for_status()
        return resp.json()

    raise RuntimeError(f"All retries exhausted for {url}")


# ---------------------------------------------------------------------------
# Bybit V5 client
# ---------------------------------------------------------------------------


class BybitClient:
    EXCHANGE = "bybit"

    def __init__(self, config: Config) -> None:
        self._key = config.bybit_api_key
        self._secret = config.bybit_api_secret
        self._sem = asyncio.Semaphore(10)
        self._client = httpx.AsyncClient(
            base_url=_BYBIT_BASE,
            headers={"Content-Type": "application/json"},
        )

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _sign(self, params_str: str, timestamp: str) -> str:
        payload = timestamp + self._key + _RECV_WINDOW + params_str
        return hmac.new(
            self._secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

    def _auth_headers(self, params_str: str) -> dict[str, str]:
        ts = str(int(time.time() * 1000))
        sig = self._sign(params_str, ts)
        return {
            "X-BAPI-API-KEY": self._key,
            "X-BAPI-SIGN": sig,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": _RECV_WINDOW,
        }

    # ------------------------------------------------------------------
    # Public endpoints
    # ------------------------------------------------------------------

    async def get_funding_rates(self) -> list[FundingRate]:
        """Fetch current funding rate for all linear perpetuals."""
        data = await _request_with_retry(
            self._client,
            "GET",
            "/v5/market/tickers",
            self._sem,
            params={"category": "linear"},
        )
        results: list[FundingRate] = []
        for item in data.get("result", {}).get("list", []):
            fr_str = item.get("fundingRate", "")
            if not fr_str:
                continue
            try:
                fr = float(fr_str)
            except ValueError:
                continue
            symbol = item["symbol"]
            next_time_ms = item.get("nextFundingTime")
            next_time_iso: str | None = None
            if next_time_ms:
                try:
                    next_time_iso = datetime.fromtimestamp(
                        int(next_time_ms) / 1000, tz=timezone.utc
                    ).isoformat()
                except (ValueError, OverflowError):
                    pass
            results.append(
                FundingRate(
                    exchange=self.EXCHANGE,
                    symbol=symbol,
                    funding_rate=fr,
                    annualized_rate=fr * cfg.funding_periods_per_year,
                    next_funding_time=next_time_iso,
                )
            )
        return results

    async def get_spot_price(self, symbol: str) -> float:
        data = await _request_with_retry(
            self._client,
            "GET",
            "/v5/market/tickers",
            self._sem,
            params={"category": "spot", "symbol": symbol},
        )
        items = data.get("result", {}).get("list", [])
        if not items:
            return 0.0
        return float(items[0].get("lastPrice", 0))

    async def get_perp_price(self, symbol: str) -> float:
        data = await _request_with_retry(
            self._client,
            "GET",
            "/v5/market/tickers",
            self._sem,
            params={"category": "linear", "symbol": symbol},
        )
        items = data.get("result", {}).get("list", [])
        if not items:
            return 0.0
        return float(items[0].get("lastPrice", 0))

    async def get_orderbook(self, symbol: str, category: str = "linear") -> Orderbook:
        data = await _request_with_retry(
            self._client,
            "GET",
            "/v5/market/orderbook",
            self._sem,
            params={"category": category, "symbol": symbol, "limit": 5},
        )
        result = data.get("result", {})
        bids = [OrderbookLevel(float(p), float(s)) for p, s in result.get("b", [])]
        asks = [OrderbookLevel(float(p), float(s)) for p, s in result.get("a", [])]
        return Orderbook(symbol=symbol, bids=bids, asks=asks)

    async def get_24h_volume(self, symbol: str) -> float:
        """Return 24h turnover in USDT for a linear perp."""
        data = await _request_with_retry(
            self._client,
            "GET",
            "/v5/market/tickers",
            self._sem,
            params={"category": "linear", "symbol": symbol},
        )
        items = data.get("result", {}).get("list", [])
        if not items:
            return 0.0
        return float(items[0].get("turnover24h", 0))

    # ------------------------------------------------------------------
    # Authenticated endpoints
    # ------------------------------------------------------------------

    async def get_balance(self) -> float:
        """Return unified USDT/USDC balance."""
        params = {"accountType": "UNIFIED"}
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        headers = self._auth_headers(qs)
        data = await _request_with_retry(
            self._client, "GET", "/v5/account/wallet-balance",
            self._sem, params=params, headers=headers,
        )
        for acct in data.get("result", {}).get("list", []):
            for coin in acct.get("coin", []):
                if coin["coin"] in ("USDT", "USDC"):
                    return float(coin.get("walletBalance", 0))
        return 0.0

    async def place_spot_order(
        self,
        symbol: str,
        side: str,
        size: float,
        order_type: str = "Market",
    ) -> PlacedOrder:
        body = {
            "category": "spot",
            "symbol": symbol,
            "side": side.capitalize(),
            "orderType": order_type,
            "qty": str(round(size, 8)),
            "timeInForce": "IOC",
        }
        body_str = json.dumps(body)
        headers = self._auth_headers(body_str)
        data = await _request_with_retry(
            self._client, "POST", "/v5/order/create",
            self._sem, content=body_str, headers=headers,
        )
        result = data.get("result", {})
        return PlacedOrder(
            order_id=result.get("orderId", ""),
            symbol=symbol,
            side=side,
            size=size,
            price=0.0,
            status="submitted",
            exchange=self.EXCHANGE,
            market_type="spot",
        )

    async def place_perp_order(
        self,
        symbol: str,
        side: str,
        size: float,
        order_type: str = "Market",
    ) -> PlacedOrder:
        body = {
            "category": "linear",
            "symbol": symbol,
            "side": side.capitalize(),
            "orderType": order_type,
            "qty": str(round(size, 4)),
            "timeInForce": "IOC",
            "reduceOnly": False,
        }
        body_str = json.dumps(body)
        headers = self._auth_headers(body_str)
        data = await _request_with_retry(
            self._client, "POST", "/v5/order/create",
            self._sem, content=body_str, headers=headers,
        )
        result = data.get("result", {})
        return PlacedOrder(
            order_id=result.get("orderId", ""),
            symbol=symbol,
            side=side,
            size=size,
            price=0.0,
            status="submitted",
            exchange=self.EXCHANGE,
            market_type="perp",
        )

    async def get_positions(self) -> list[dict[str, Any]]:
        params = {"category": "linear", "settleCoin": "USDT"}
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        headers = self._auth_headers(qs)
        data = await _request_with_retry(
            self._client, "GET", "/v5/position/list",
            self._sem, params=params, headers=headers,
        )
        return data.get("result", {}).get("list", [])

    async def set_leverage(self, symbol: str, leverage: int = 1) -> None:
        body = {
            "category": "linear",
            "symbol": symbol,
            "buyLeverage": str(leverage),
            "sellLeverage": str(leverage),
        }
        body_str = json.dumps(body)
        headers = self._auth_headers(body_str)
        try:
            await _request_with_retry(
                self._client, "POST", "/v5/position/set-leverage",
                self._sem, content=body_str, headers=headers,
            )
        except Exception as exc:
            logger.warning("set_leverage(%s, %d) failed: %s", symbol, leverage, exc)

    async def close(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# OKX client
# ---------------------------------------------------------------------------


class OKXClient:
    EXCHANGE = "okx"

    def __init__(self, config: Config) -> None:
        self._key = config.okx_api_key
        self._secret = config.okx_api_secret
        self._passphrase = config.okx_passphrase
        self._sem = asyncio.Semaphore(10)
        self._client = httpx.AsyncClient(
            base_url=_OKX_BASE,
            headers={"Content-Type": "application/json"},
        )

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        msg = timestamp + method.upper() + path + body
        return hmac.new(self._secret.encode(), msg.encode(), hashlib.sha256).hexdigest()

    def _auth_headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        return {
            "OK-ACCESS-KEY": self._key,
            "OK-ACCESS-SIGN": self._sign(ts, method, path, body),
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self._passphrase,
        }

    # ------------------------------------------------------------------
    # Public endpoints
    # ------------------------------------------------------------------

    async def get_funding_rates(self) -> list[FundingRate]:
        """Fetch current funding rates for all USDT-margined swaps."""
        # First get all instruments
        inst_data = await _request_with_retry(
            self._client, "GET", "/api/v5/public/instruments",
            self._sem, params={"instType": "SWAP"},
        )
        symbols = [
            i["instId"]
            for i in inst_data.get("data", [])
            if i.get("instId", "").endswith("-USDT-SWAP")
        ]

        results: list[FundingRate] = []
        # Batch: OKX allows fetching one at a time for current rate
        # We'll fetch in chunks to stay within rate limits
        chunk_size = 20
        for i in range(0, min(len(symbols), 200), chunk_size):
            chunk = symbols[i : i + chunk_size]
            tasks = [self._get_single_funding_rate(sym) for sym in chunk]
            chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in chunk_results:
                if isinstance(r, FundingRate):
                    results.append(r)
        return results

    async def _get_single_funding_rate(self, inst_id: str) -> FundingRate | None:
        try:
            data = await _request_with_retry(
                self._client, "GET", "/api/v5/public/funding-rate",
                self._sem, params={"instId": inst_id},
            )
            items = data.get("data", [])
            if not items:
                return None
            item = items[0]
            fr = float(item.get("fundingRate", 0))
            next_time_ms = item.get("nextFundingTime", "")
            next_time_iso: str | None = None
            if next_time_ms:
                try:
                    next_time_iso = datetime.fromtimestamp(
                        int(next_time_ms) / 1000, tz=timezone.utc
                    ).isoformat()
                except (ValueError, OverflowError):
                    pass
            return FundingRate(
                exchange=self.EXCHANGE,
                symbol=inst_id,
                funding_rate=fr,
                annualized_rate=fr * cfg.funding_periods_per_year,
                next_funding_time=next_time_iso,
            )
        except Exception as exc:
            logger.debug("OKX funding rate fetch failed for %s: %s", inst_id, exc)
            return None

    async def get_spot_price(self, symbol: str) -> float:
        # OKX spot symbol e.g. "SOL-USDT"
        spot_sym = symbol.replace("-USDT-SWAP", "-USDT")
        data = await _request_with_retry(
            self._client, "GET", "/api/v5/market/ticker",
            self._sem, params={"instId": spot_sym},
        )
        items = data.get("data", [])
        return float(items[0].get("last", 0)) if items else 0.0

    async def get_perp_price(self, symbol: str) -> float:
        data = await _request_with_retry(
            self._client, "GET", "/api/v5/market/ticker",
            self._sem, params={"instId": symbol},
        )
        items = data.get("data", [])
        return float(items[0].get("last", 0)) if items else 0.0

    async def get_orderbook(self, symbol: str, side: str = "both") -> Orderbook:
        data = await _request_with_retry(
            self._client, "GET", "/api/v5/market/books",
            self._sem, params={"instId": symbol, "sz": 5},
        )
        items = data.get("data", [])
        if not items:
            return Orderbook(symbol=symbol, bids=[], asks=[])
        raw = items[0]
        bids = [OrderbookLevel(float(p), float(s)) for p, s, *_ in raw.get("bids", [])]
        asks = [OrderbookLevel(float(p), float(s)) for p, s, *_ in raw.get("asks", [])]
        return Orderbook(symbol=symbol, bids=bids, asks=asks)

    async def get_24h_volume(self, symbol: str) -> float:
        data = await _request_with_retry(
            self._client, "GET", "/api/v5/market/ticker",
            self._sem, params={"instId": symbol},
        )
        items = data.get("data", [])
        return float(items[0].get("volCcy24h", 0)) if items else 0.0

    # ------------------------------------------------------------------
    # Authenticated endpoints
    # ------------------------------------------------------------------

    async def get_balance(self) -> float:
        path = "/api/v5/account/balance"
        headers = self._auth_headers("GET", path)
        data = await _request_with_retry(
            self._client, "GET", path, self._sem,
            params={"ccy": "USDT"}, headers=headers,
        )
        for acct in data.get("data", []):
            for detail in acct.get("details", []):
                if detail.get("ccy") in ("USDT", "USDC"):
                    return float(detail.get("cashBal", 0))
        return 0.0

    async def place_spot_order(
        self,
        symbol: str,
        side: str,
        size: float,
        order_type: str = "market",
    ) -> PlacedOrder:
        spot_sym = symbol.replace("-USDT-SWAP", "-USDT")
        body_dict = {
            "instId": spot_sym,
            "tdMode": "cash",
            "side": side.lower(),
            "ordType": order_type.lower(),
            "sz": str(round(size, 8)),
        }
        body_str = json.dumps(body_dict)
        path = "/api/v5/trade/order"
        headers = self._auth_headers("POST", path, body_str)
        data = await _request_with_retry(
            self._client, "POST", path, self._sem,
            content=body_str, headers=headers,
        )
        result = (data.get("data") or [{}])[0]
        return PlacedOrder(
            order_id=result.get("ordId", ""),
            symbol=spot_sym,
            side=side,
            size=size,
            price=0.0,
            status="submitted",
            exchange=self.EXCHANGE,
            market_type="spot",
        )

    async def place_perp_order(
        self,
        symbol: str,
        side: str,
        size: float,
        order_type: str = "market",
    ) -> PlacedOrder:
        body_dict = {
            "instId": symbol,
            "tdMode": "cross",
            "side": side.lower(),
            "ordType": order_type.lower(),
            "sz": str(round(size, 4)),
            "posSide": "short" if side.lower() == "sell" else "long",
        }
        body_str = json.dumps(body_dict)
        path = "/api/v5/trade/order"
        headers = self._auth_headers("POST", path, body_str)
        data = await _request_with_retry(
            self._client, "POST", path, self._sem,
            content=body_str, headers=headers,
        )
        result = (data.get("data") or [{}])[0]
        return PlacedOrder(
            order_id=result.get("ordId", ""),
            symbol=symbol,
            side=side,
            size=size,
            price=0.0,
            status="submitted",
            exchange=self.EXCHANGE,
            market_type="perp",
        )

    async def get_positions(self) -> list[dict[str, Any]]:
        path = "/api/v5/account/positions"
        headers = self._auth_headers("GET", path)
        data = await _request_with_retry(
            self._client, "GET", path, self._sem,
            params={"instType": "SWAP"}, headers=headers,
        )
        return data.get("data", [])

    async def set_leverage(self, symbol: str, leverage: int = 1) -> None:
        body_dict = {
            "instId": symbol,
            "lever": str(leverage),
            "mgnMode": "cross",
        }
        body_str = json.dumps(body_dict)
        path = "/api/v5/account/set-leverage"
        headers = self._auth_headers("POST", path, body_str)
        try:
            await _request_with_retry(
                self._client, "POST", path, self._sem,
                content=body_str, headers=headers,
            )
        except Exception as exc:
            logger.warning("OKX set_leverage(%s, %d) failed: %s", symbol, leverage, exc)

    async def close(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# CoinGlass public scanner
# ---------------------------------------------------------------------------


class CoinGlassScanner:
    """
    Uses the CoinGlass open API to fetch cross-exchange funding rate comparisons.
    This endpoint is public and does not require authentication.
    """

    def __init__(self) -> None:
        self._sem = asyncio.Semaphore(3)
        self._client = httpx.AsyncClient(
            base_url=_COINGLASS_BASE,
            headers={
                "User-Agent": "FundingRateBot/1.0",
                "Accept": "application/json",
            },
        )

    async def get_all_funding_rates(self) -> list[FundingRate]:
        """
        Fetch funding rates from CoinGlass public API.
        Returns a combined list keyed by (exchange, symbol).
        """
        try:
            data = await _request_with_retry(
                self._client,
                "GET",
                "/public/api/fundingRate/v2/home/list",
                self._sem,
                params={"interval": "8h"},
            )
        except Exception as exc:
            logger.warning("CoinGlass fetch failed: %s", exc)
            return []

        results: list[FundingRate] = []
        for item in data.get("data", []):
            symbol_base = item.get("symbol", "")
            for exchange_data in item.get("uMarginList", []):
                exchange_name = exchange_data.get("exchangeName", "").lower()
                fr_str = exchange_data.get("rate")
                if fr_str is None:
                    continue
                try:
                    fr = float(fr_str)
                except (ValueError, TypeError):
                    continue
                # Normalize exchange names to match our client keys
                if "bybit" in exchange_name:
                    exchange_name = "bybit"
                elif "okx" in exchange_name or "okex" in exchange_name:
                    exchange_name = "okx"
                results.append(
                    FundingRate(
                        exchange=exchange_name,
                        symbol=symbol_base,
                        funding_rate=fr,
                        annualized_rate=fr * cfg.funding_periods_per_year,
                        next_funding_time=None,
                    )
                )
        return results

    async def close(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Paper simulator
# ---------------------------------------------------------------------------


@dataclass
class VirtualPosition:
    symbol: str
    spot_exchange: str
    perp_exchange: str
    spot_size: float       # units of base asset
    perp_size: float       # units of base asset (short)
    entry_spot_price: float
    entry_perp_price: float
    entry_funding_rate: float
    entry_time: float = field(default_factory=time.time)
    total_funding: float = 0.0
    last_funding_payment: float = field(default_factory=time.time)


class PaperSimulator:
    """
    Virtual paper-trading engine.
    Tracks USDC balance and positions, simulates funding payments.
    Does not call any exchange order API.
    """

    FUNDING_INTERVAL = 8 * 3600  # 8 hours in seconds

    def __init__(self, starting_balance: float) -> None:
        self._balance = starting_balance
        self._positions: dict[str, VirtualPosition] = {}   # symbol -> position
        self._trade_log: list[dict[str, Any]] = []

    @property
    def balance(self) -> float:
        return self._balance

    def open_position(
        self,
        symbol: str,
        spot_exchange: str,
        perp_exchange: str,
        size_usdc: float,
        spot_price: float,
        perp_price: float,
        funding_rate: float,
    ) -> None:
        if spot_price <= 0:
            raise ValueError(f"Invalid spot price for {symbol}: {spot_price}")
        # Deduct size from balance (spot leg)
        cost = size_usdc
        if cost > self._balance:
            raise ValueError(
                f"Insufficient paper balance: need {cost:.2f}, have {self._balance:.2f}"
            )
        self._balance -= cost
        base_qty = size_usdc / spot_price
        self._positions[symbol] = VirtualPosition(
            symbol=symbol,
            spot_exchange=spot_exchange,
            perp_exchange=perp_exchange,
            spot_size=base_qty,
            perp_size=base_qty,
            entry_spot_price=spot_price,
            entry_perp_price=perp_price,
            entry_funding_rate=funding_rate,
        )
        self._trade_log.append(
            {
                "action": "open",
                "symbol": symbol,
                "size_usdc": size_usdc,
                "spot_price": spot_price,
                "perp_price": perp_price,
                "time": time.time(),
            }
        )
        logger.info(
            "[PAPER] Opened %s: size=%.2f USDC, spot=%.4f, perp=%.4f",
            symbol, size_usdc, spot_price, perp_price,
        )

    def close_position(
        self,
        symbol: str,
        current_spot_price: float,
        current_perp_price: float,
        reason: str = "",
    ) -> tuple[float, float]:
        """Close position and return (funding_collected, basis_pnl)."""
        pos = self._positions.pop(symbol, None)
        if pos is None:
            return 0.0, 0.0

        funding_collected = pos.total_funding

        # Basis P&L: short perp closed at current_perp_price
        # (entry_perp - exit_perp) * qty — profit if perp fell
        perp_pnl = (pos.entry_perp_price - current_perp_price) * pos.perp_size
        # Spot leg: value recovered
        spot_value = pos.spot_size * current_spot_price
        # Original cost was spot_size * entry_spot_price
        spot_pnl = spot_value - (pos.spot_size * pos.entry_spot_price)

        total_proceeds = (pos.spot_size * current_spot_price) + funding_collected
        self._balance += total_proceeds

        basis_pnl = perp_pnl + spot_pnl
        self._trade_log.append(
            {
                "action": "close",
                "symbol": symbol,
                "funding": funding_collected,
                "basis_pnl": basis_pnl,
                "reason": reason,
                "time": time.time(),
            }
        )
        logger.info(
            "[PAPER] Closed %s: funding=%.4f USDC, basis_pnl=%.4f USDC, reason=%s",
            symbol, funding_collected, basis_pnl, reason,
        )
        return funding_collected, basis_pnl

    def simulate_funding_payments(
        self, symbol_rates: dict[str, float]
    ) -> list[tuple[str, float]]:
        """
        Check which positions are due for a funding payment and credit them.
        Returns list of (symbol, payment_amount) for payments processed.
        """
        now = time.time()
        payments: list[tuple[str, float]] = []
        for symbol, pos in self._positions.items():
            elapsed = now - pos.last_funding_payment
            if elapsed >= self.FUNDING_INTERVAL:
                rate = symbol_rates.get(symbol, pos.entry_funding_rate)
                payment = rate * pos.perp_size * pos.entry_spot_price
                pos.total_funding += payment
                pos.last_funding_payment = now
                self._balance += payment
                payments.append((symbol, payment))
                logger.info(
                    "[PAPER] Funding payment for %s: %.4f USDC (rate=%.6f)",
                    symbol, payment, rate,
                )
        return payments

    def get_position(self, symbol: str) -> VirtualPosition | None:
        return self._positions.get(symbol)

    def get_all_positions(self) -> dict[str, VirtualPosition]:
        return dict(self._positions)

    def get_unrealized_pnl(self, symbol: str, current_price: float) -> float:
        pos = self._positions.get(symbol)
        if pos is None:
            return 0.0
        price_change_pct = (current_price - pos.entry_spot_price) / pos.entry_spot_price
        # Delta neutral: spot gain cancels perp loss (approximately)
        return pos.total_funding  # net P&L is just funding collected


# ---------------------------------------------------------------------------
# Unified multi-exchange client
# ---------------------------------------------------------------------------


class ExchangeClient:
    """
    Aggregates Bybit + OKX + CoinGlass into a single interface.
    In paper mode, order placement is routed to PaperSimulator.
    """

    def __init__(self, config: Config) -> None:
        self._cfg = config
        self.bybit: BybitClient | None = (
            BybitClient(config) if config.bybit_enabled else None
        )
        self.okx: OKXClient | None = (
            OKXClient(config) if config.okx_enabled else None
        )
        self.coinglass = CoinGlassScanner()
        self.paper: PaperSimulator | None = (
            PaperSimulator(config.paper_starting_balance) if config.paper_mode else None
        )

    async def get_all_funding_rates(self) -> list[FundingRate]:
        """Aggregate funding rates from all enabled exchanges."""
        tasks: list[Any] = []
        sources: list[str] = []

        if self.bybit:
            tasks.append(self.bybit.get_funding_rates())
            sources.append("bybit")
        if self.okx:
            tasks.append(self.okx.get_funding_rates())
            sources.append("okx")
        tasks.append(self.coinglass.get_all_funding_rates())
        sources.append("coinglass")

        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        combined: list[FundingRate] = []
        for source, result in zip(sources, gathered):
            if isinstance(result, Exception):
                logger.warning("Failed to get funding rates from %s: %s", source, result)
            else:
                combined.extend(result)
        return combined

    async def get_best_spot_price(self, base_symbol: str) -> tuple[str, float]:
        """
        Return the (exchange_name, price) for the cheapest available spot price.
        base_symbol: e.g. "SOL" – we query SOL-USDT on each exchange.
        """
        prices: list[tuple[str, float]] = []
        bybit_sym = f"{base_symbol}USDT"
        okx_sym = f"{base_symbol}-USDT-SWAP"  # we'll use spot endpoint internally

        if self.bybit:
            try:
                p = await self.bybit.get_spot_price(bybit_sym)
                if p > 0:
                    prices.append(("bybit", p))
            except Exception as exc:
                logger.debug("Bybit spot price failed for %s: %s", base_symbol, exc)

        if self.okx:
            try:
                p = await self.okx.get_spot_price(okx_sym)
                if p > 0:
                    prices.append(("okx", p))
            except Exception as exc:
                logger.debug("OKX spot price failed for %s: %s", base_symbol, exc)

        if not prices:
            return ("none", 0.0)
        return min(prices, key=lambda x: x[1])

    async def get_perp_price(self, exchange: str, symbol: str) -> float:
        if exchange == "bybit" and self.bybit:
            return await self.bybit.get_perp_price(symbol)
        if exchange == "okx" and self.okx:
            return await self.okx.get_perp_price(symbol)
        return 0.0

    async def get_balance(self) -> float:
        if self._cfg.paper_mode and self.paper:
            return self.paper.balance
        if self.bybit:
            try:
                return await self.bybit.get_balance()
            except Exception:
                pass
        if self.okx:
            try:
                return await self.okx.get_balance()
            except Exception:
                pass
        return 0.0

    async def open_position(
        self,
        symbol: str,
        spot_exchange: str,
        perp_exchange: str,
        size_usdc: float,
        spot_price: float,
        perp_price: float,
        funding_rate: float,
        perp_symbol: str,
    ) -> None:
        """Open a delta-neutral position (spot long + perp short)."""
        if self._cfg.paper_mode:
            assert self.paper is not None
            self.paper.open_position(
                symbol=symbol,
                spot_exchange=spot_exchange,
                perp_exchange=perp_exchange,
                size_usdc=size_usdc,
                spot_price=spot_price,
                perp_price=perp_price,
                funding_rate=funding_rate,
            )
            return

        base_qty = size_usdc / spot_price
        spot_client = self._get_client(spot_exchange)
        perp_client = self._get_client(perp_exchange)
        if spot_client is None or perp_client is None:
            raise RuntimeError(f"Exchange client not configured for {spot_exchange}/{perp_exchange}")

        await perp_client.set_leverage(perp_symbol, cfg.perp_leverage)

        spot_sym = self._to_spot_symbol(spot_exchange, symbol)
        spot_task = spot_client.place_spot_order(spot_sym, "Buy", base_qty)
        perp_task = perp_client.place_perp_order(perp_symbol, "Sell", base_qty)
        results = await asyncio.gather(spot_task, perp_task, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                logger.error("Order placement error: %s", r)
                raise r

    async def close_position(
        self,
        symbol: str,
        spot_exchange: str,
        perp_exchange: str,
        spot_size: float,
        perp_symbol: str,
    ) -> tuple[float, float]:
        """Close a delta-neutral position. Returns (spot_price, perp_price)."""
        spot_price = 0.0
        perp_price = 0.0

        if self._cfg.paper_mode:
            assert self.paper is not None
            # Get latest prices for P&L calculation
            _, sp = await self.get_best_spot_price(symbol)
            pp = await self.get_perp_price(perp_exchange, perp_symbol)
            spot_price = sp if sp > 0 else 0.0
            perp_price = pp if pp > 0 else 0.0
            self.paper.close_position(symbol, spot_price or 1.0, perp_price or 1.0)
            return spot_price, perp_price

        spot_client = self._get_client(spot_exchange)
        perp_client = self._get_client(perp_exchange)
        if spot_client is None or perp_client is None:
            raise RuntimeError("Exchange client not configured")

        spot_sym = self._to_spot_symbol(spot_exchange, symbol)
        spot_task = spot_client.place_spot_order(spot_sym, "Sell", spot_size)
        perp_task = perp_client.place_perp_order(perp_symbol, "Buy", spot_size)
        await asyncio.gather(spot_task, perp_task)
        return spot_price, perp_price

    def simulate_funding_payments(
        self, symbol_rates: dict[str, float]
    ) -> list[tuple[str, float]]:
        if self.paper:
            return self.paper.simulate_funding_payments(symbol_rates)
        return []

    def _get_client(self, exchange: str) -> BybitClient | OKXClient | None:
        if exchange == "bybit":
            return self.bybit
        if exchange == "okx":
            return self.okx
        return None

    @staticmethod
    def _to_spot_symbol(exchange: str, base: str) -> str:
        if exchange == "bybit":
            return f"{base}USDT"
        if exchange == "okx":
            return f"{base}-USDT"
        return base

    @staticmethod
    def to_perp_symbol(exchange: str, base: str) -> str:
        if exchange == "bybit":
            return f"{base}USDT"
        if exchange == "okx":
            return f"{base}-USDT-SWAP"
        return base

    async def close(self) -> None:
        tasks = []
        if self.bybit:
            tasks.append(self.bybit.close())
        if self.okx:
            tasks.append(self.okx.close())
        tasks.append(self.coinglass.close())
        await asyncio.gather(*tasks, return_exceptions=True)
