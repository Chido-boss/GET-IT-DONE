"""
crypto_price_client.py — Multi-source BTC/ETH/SOL reference prices.

Tries Kraken, Binance, Coinbase in order. Maintains a rolling price buffer
per symbol for realized volatility and momentum computation.

No auth required. All public endpoints.
"""

from __future__ import annotations
import json
import logging
import math
import time
import urllib.request
import urllib.parse
from collections import deque
from threading import Lock

log = logging.getLogger(__name__)

# Maximum samples to keep per symbol
_MAX_BUFFER = 500

# Per-symbol rolling price buffer: {symbol: deque of (ts, price)}
_price_buffers: dict[str, deque] = {}
_buffer_lock = Lock()

# Most recent successful fetch per symbol
_latest: dict[str, dict] = {}


def _http_get(url: str, timeout: int = 8) -> dict | list | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pm-edge-bot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        log.debug(f"HTTP GET {url} failed: {exc}")
        return None


# ── Per-exchange fetchers ──────────────────────────────────────────────────────

_KRAKEN_PAIRS = {
    "BTC": "XBTUSD",
    "ETH": "ETHUSD",
    "SOL": "SOLUSD",
}

_BINANCE_SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
}

_COINBASE_PAIRS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
}


def _fetch_kraken(symbol: str) -> float | None:
    pair = _KRAKEN_PAIRS.get(symbol.upper())
    if not pair:
        return None
    data = _http_get(f"https://api.kraken.com/0/public/Ticker?pair={pair}")
    if not data or data.get("error"):
        return None
    result = data.get("result", {})
    if not result:
        return None
    pair_data = next(iter(result.values()), {})
    c = pair_data.get("c")  # last trade price
    if c and len(c) > 0:
        try:
            return float(c[0])
        except (ValueError, TypeError):
            pass
    return None


def _fetch_binance(symbol: str) -> float | None:
    sym = _BINANCE_SYMBOLS.get(symbol.upper())
    if not sym:
        return None
    data = _http_get(f"https://api.binance.com/api/v3/ticker/price?symbol={sym}")
    if not data:
        return None
    try:
        return float(data.get("price", 0) or 0) or None
    except (ValueError, TypeError):
        return None


def _fetch_coinbase(symbol: str) -> float | None:
    pair = _COINBASE_PAIRS.get(symbol.upper())
    if not pair:
        return None
    data = _http_get(f"https://api.coinbase.com/v2/prices/{pair}/spot")
    if not data:
        return None
    try:
        return float(data.get("data", {}).get("amount", 0) or 0) or None
    except (ValueError, TypeError):
        return None


_FETCHERS = [
    ("kraken",   _fetch_kraken),
    ("binance",  _fetch_binance),
    ("coinbase", _fetch_coinbase),
]


# ── Public interface ───────────────────────────────────────────────────────────

def fetch_price(symbol: str, sources: list[str] | None = None) -> dict | None:
    """
    Fetch current price from multiple sources in priority order.
    Returns {price, source, ts} or None if all sources fail.
    """
    sym = symbol.upper()
    order = sources or ["kraken", "binance", "coinbase"]

    fetcher_map = {name: fn for name, fn in _FETCHERS}

    for source in order:
        fn = fetcher_map.get(source)
        if fn is None:
            continue
        price = fn(sym)
        if price and price > 0:
            entry = {"price": price, "source": source, "ts": time.time()}
            _record_price(sym, price)
            _latest[sym] = entry
            return entry

    log.warning(f"All price sources failed for {sym}")
    return None


def get_latest_price(symbol: str) -> dict | None:
    """Return the most recently fetched price (may be stale)."""
    return _latest.get(symbol.upper())


def _record_price(symbol: str, price: float) -> None:
    with _buffer_lock:
        if symbol not in _price_buffers:
            _price_buffers[symbol] = deque(maxlen=_MAX_BUFFER)
        _price_buffers[symbol].append((time.time(), price))


def get_price_buffer(symbol: str) -> list[tuple[float, float]]:
    """Return list of (ts, price) sorted oldest-first."""
    with _buffer_lock:
        buf = _price_buffers.get(symbol.upper())
        return list(buf) if buf else []


def estimate_realized_vol(symbol: str, window_seconds: float = 900) -> tuple[float | None, int]:
    """
    Estimate annualized realized volatility from recent price samples.
    Returns (vol_annual, n_samples).
    """
    buf = get_price_buffer(symbol)
    if not buf:
        return None, 0

    cutoff = time.time() - window_seconds
    recent = [(ts, p) for ts, p in buf if ts >= cutoff]

    if len(recent) < 2:
        return None, len(recent)

    # Log returns
    log_rets = []
    for i in range(1, len(recent)):
        ts_prev, p_prev = recent[i - 1]
        ts_cur,  p_cur  = recent[i]
        dt = ts_cur - ts_prev
        if dt > 0 and p_prev > 0:
            lr = math.log(p_cur / p_prev)
            log_rets.append((lr, dt))

    if len(log_rets) < 2:
        return None, len(recent)

    # Variance of returns per second, then annualize
    mean_ret = sum(r for r, _ in log_rets) / len(log_rets)
    variance = sum((r - mean_ret) ** 2 for r, _ in log_rets) / (len(log_rets) - 1)

    # Approximate: assume returns are on ~equal time steps
    avg_dt = sum(dt for _, dt in log_rets) / len(log_rets)
    if avg_dt <= 0:
        return None, len(recent)

    # Annualize: seconds_per_year / avg_dt gives number of periods per year
    variance_annual = variance * (365 * 24 * 3600 / avg_dt)
    vol_annual = math.sqrt(max(0.0, variance_annual))

    return vol_annual, len(recent)


def get_momentum(symbol: str, window_seconds: float = 180) -> float:
    """
    Price momentum as % change per minute over the given window.
    Positive = rising, negative = falling. Returns 0.0 if insufficient data.
    """
    buf = get_price_buffer(symbol)
    if not buf:
        return 0.0

    now = time.time()
    cutoff = now - window_seconds
    recent = [(ts, p) for ts, p in buf if ts >= cutoff]

    if len(recent) < 2:
        return 0.0

    oldest_ts, oldest_p = recent[0]
    newest_ts, newest_p = recent[-1]
    elapsed = newest_ts - oldest_ts

    if elapsed < 5 or oldest_p <= 0:
        return 0.0

    total_change_pct = (newest_p - oldest_p) / oldest_p * 100
    elapsed_min = elapsed / 60.0
    return total_change_pct / elapsed_min  # %/min
