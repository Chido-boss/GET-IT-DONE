"""
data.py — Market data ingestion from Binance public REST API.
No API key required. Returns standardised OHLCV dicts.
"""

from __future__ import annotations
import time
from typing import Optional
import urllib.request
import urllib.parse
import json

BINANCE_BASE = "https://api.binance.com"


def _get(url: str, params: dict) -> list:
    full_url = url + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                full_url,
                headers={"User-Agent": "quant-engine/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            if attempt == 3:
                raise RuntimeError(f"Binance API failed after 4 attempts: {exc}") from exc
            time.sleep(2 ** attempt)
    return []


def fetch_candles(
    symbol: str,
    interval: str,
    limit: int = 200,
    start_time_ms: Optional[int] = None,
) -> list[dict]:
    """
    Fetch OHLCV candles from Binance.

    Returns list of dicts with keys:
        timestamp (int ms), open, high, low, close, volume (all float)
    """
    params: dict = {"symbol": symbol, "interval": interval, "limit": limit}
    if start_time_ms is not None:
        params["startTime"] = start_time_ms

    raw = _get(f"{BINANCE_BASE}/api/v3/klines", params)

    candles = []
    for k in raw:
        candles.append({
            "timestamp": int(k[0]),
            "open":   float(k[1]),
            "high":   float(k[2]),
            "low":    float(k[3]),
            "close":  float(k[4]),
            "volume": float(k[5]),
        })
    return candles


def fetch_candles_since(
    symbol: str,
    interval: str,
    n_candles: int,
) -> list[dict]:
    """
    Fetch up to n_candles by paginating backwards from now.
    Binance caps each call at 1000 candles.
    """
    all_candles: list[dict] = []
    batch = 1000
    end_ts: Optional[int] = None

    while len(all_candles) < n_candles:
        params: dict = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(batch, n_candles - len(all_candles)),
        }
        if end_ts is not None:
            params["endTime"] = end_ts

        raw = _get(f"{BINANCE_BASE}/api/v3/klines", params)
        if not raw:
            break

        batch_candles = [{
            "timestamp": int(k[0]),
            "open":   float(k[1]),
            "high":   float(k[2]),
            "low":    float(k[3]),
            "close":  float(k[4]),
            "volume": float(k[5]),
        } for k in raw]

        all_candles = batch_candles + all_candles
        end_ts = batch_candles[0]["timestamp"] - 1

        if len(raw) < batch:
            break

    return all_candles[-n_candles:]


def latest_price(symbol: str) -> float:
    """Current best-bid/ask mid from Binance ticker."""
    raw = _get(f"{BINANCE_BASE}/api/v3/ticker/price", {"symbol": symbol})
    return float(raw.get("price", 0))


# ── Kraken ─────────────────────────────────────────────────────────────────────

KRAKEN_BASE = "https://api.kraken.com"

_BINANCE_TO_KRAKEN: dict[str, str] = {
    "BTCUSDT":  "XBTUSD",
    "ETHUSDT":  "ETHUSD",
    "SOLUSDT":  "SOLUSD",
    "ADAUSDT":  "ADAUSD",
    "XRPUSDT":  "XRPUSD",
    "DOTUSDT":  "DOTUSD",
    "LTCUSDT":  "LTCUSD",
    "LINKUSDT": "LINKUSD",
    "AVAXUSDT": "AVAXUSD",
    "MATICUSDT":"MATICUSD",
}


def binance_to_kraken(symbol: str) -> str:
    return _BINANCE_TO_KRAKEN.get(symbol.upper(), symbol)


def fetch_kraken_candles(symbol: str, interval_minutes: int = 240, limit: int = 200) -> list:
    """
    Fetch OHLCV candles from Kraken public OHLC endpoint.
    interval_minutes: 1 5 15 30 60 240 1440 10080 21600
    Returns same dict schema as fetch_candles (timestamp in ms).
    """
    pair = binance_to_kraken(symbol)
    full_url = (
        KRAKEN_BASE + "/0/public/OHLC?"
        + urllib.parse.urlencode({"pair": pair, "interval": interval_minutes})
    )
    for attempt in range(4):
        try:
            req = urllib.request.Request(full_url, headers={"User-Agent": "quant-engine/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            if data.get("error"):
                raise RuntimeError(f"Kraken error: {data['error']}")
            result = data["result"]
            pair_key = next(k for k in result if k != "last")
            raw = result[pair_key][-limit:]
            return [{
                "timestamp": int(k[0]) * 1000,
                "open":      float(k[1]),
                "high":      float(k[2]),
                "low":       float(k[3]),
                "close":     float(k[4]),
                "volume":    float(k[6]),
            } for k in raw]
        except Exception as exc:
            if attempt == 3:
                raise RuntimeError(f"Kraken API failed after 4 attempts: {exc}") from exc
            time.sleep(2 ** attempt)
    return []
