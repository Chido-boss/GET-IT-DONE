"""
polymarket_client.py — Public Polymarket API client. No authentication required.

Data APIs:
  Gamma:  https://gamma-api.polymarket.com  — market metadata, prices, volumes
  CLOB:   https://clob.polymarket.com       — order book, bids/asks

We save raw API samples to data/raw_samples/ on first use to aid debugging.
Defensively parses all responses — missing fields produce warnings, not crashes.
"""

from __future__ import annotations
import json
import logging
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path

log = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE  = "https://clob.polymarket.com"

_RAW_SAMPLE_DIR = Path("data/raw_samples")
_raw_saved: set[str] = set()


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 12, label: str = "") -> dict | list | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pm-edge-bot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            data = json.loads(body)
            _maybe_save_sample(label or url, body)
            return data
    except urllib.request.HTTPError as exc:
        log.warning(f"HTTP {exc.code} from {url}: {exc.reason}")
        return None
    except Exception as exc:
        log.warning(f"Request failed [{url}]: {exc}")
        return None


def _maybe_save_sample(label: str, body: bytes) -> None:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", label)[:60]
    if safe in _raw_saved:
        return
    try:
        _RAW_SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
        path = _RAW_SAMPLE_DIR / f"{safe}.json"
        if not path.exists():
            path.write_bytes(body[:32_768])  # cap at 32KB
            log.debug(f"Saved raw sample → {path}")
            _raw_saved.add(safe)
    except Exception:
        pass


# ── Market discovery (Gamma API) ───────────────────────────────────────────────

def get_active_markets(limit: int = 100, offset: int = 0) -> list[dict]:
    """
    Fetch active markets from Gamma API.
    Returns raw market dicts (not yet parsed). Caller uses parse_market().
    """
    params = urllib.parse.urlencode({
        "active":    "true",
        "closed":    "false",
        "limit":     limit,
        "offset":    offset,
        "order":     "volume",
        "ascending": "false",
    })
    url = f"{GAMMA_BASE}/markets?{params}"
    data = _get(url, label="gamma_markets")
    if not isinstance(data, list):
        # Gamma sometimes wraps in {"markets": [...]}
        if isinstance(data, dict):
            data = data.get("markets", [])
    return data if isinstance(data, list) else []


# ── Market parsing ────────────────────────────────────────────────────────────

_SYMBOL_RE = [
    (re.compile(r'\bBTC\b|\bBitcoin\b', re.I), "BTC"),
    (re.compile(r'\bETH\b|\bEthereum\b|\bEther\b', re.I), "ETH"),
    (re.compile(r'\bSOL\b|\bSolana\b', re.I), "SOL"),
]

_TARGET_RE = [
    re.compile(r'\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)k\b', re.I),  # $100K
    re.compile(r'\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)'),             # $105,000
    re.compile(r'\b([0-9]{3,7}(?:\.[0-9]+)?)\s*(?:dollars?|usd)\b', re.I),
]

_DIRECTION_RE = [
    (re.compile(r'\babove\b|\bhigher\b', re.I), "above"),
    (re.compile(r'\bbelow\b|\blower\b', re.I), "below"),
]


def _parse_symbol(text: str) -> str | None:
    for pattern, sym in _SYMBOL_RE:
        if pattern.search(text):
            return sym
    return None


def _parse_target(text: str) -> float | None:
    for pat in _TARGET_RE:
        m = pat.search(text)
        if m:
            raw = m.group(1).replace(",", "")
            try:
                val = float(raw)
                # Handle K suffix: check if the full match ends with k
                if m.group(0).lower().endswith("k"):
                    val *= 1000
                # Sanity bounds for crypto prices
                if 0.01 <= val <= 10_000_000:
                    return val
            except ValueError:
                pass
    return None


def _parse_direction(text: str) -> str | None:
    for pat, direction in _DIRECTION_RE:
        if pat.search(text):
            return direction
    if re.search(r'\bup or down\b|\bup/down\b|\bhigher or lower\b', text, re.I):
        return "either"  # directional market without fixed target
    return None


def _parse_expiry(raw: dict) -> float | None:
    for field in ("endDate", "end_date", "endDateIso", "expiryDate"):
        val = raw.get(field)
        if val:
            try:
                from datetime import datetime, timezone
                # Handle ISO format with/without milliseconds and Z
                s = str(val).rstrip("Z")
                if "." in s:
                    s = s.split(".")[0]
                dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
                return dt.replace(tzinfo=timezone.utc).timestamp()
            except (ValueError, TypeError):
                pass
    return None


def _parse_tokens(raw: dict) -> tuple[str | None, str | None]:
    """Extract YES and NO token IDs."""
    tokens = raw.get("tokens", [])
    if isinstance(tokens, str):
        try:
            tokens = json.loads(tokens)
        except Exception:
            tokens = []

    yes_id = no_id = None
    for tok in tokens:
        if not isinstance(tok, dict):
            continue
        outcome = str(tok.get("outcome", "")).lower()
        tid = tok.get("token_id") or tok.get("tokenId")
        if "yes" in outcome:
            yes_id = tid
        elif "no" in outcome:
            no_id = tid

    # Fallback: some markets use clobTokenIds
    if not yes_id:
        clob = raw.get("clobTokenIds")
        if isinstance(clob, list) and len(clob) >= 2:
            yes_id, no_id = str(clob[0]), str(clob[1])

    return yes_id, no_id


def _parse_prices(raw: dict) -> tuple[float | None, float | None]:
    """Parse outcome prices (mid-point from Gamma, not CLOB order book)."""
    prices_raw = raw.get("outcomePrices", "[]")
    if isinstance(prices_raw, str):
        try:
            prices = json.loads(prices_raw)
        except Exception:
            prices = []
    else:
        prices = prices_raw or []

    outcomes_raw = raw.get("outcomes", "[\"Yes\", \"No\"]")
    if isinstance(outcomes_raw, str):
        try:
            outcomes = json.loads(outcomes_raw)
        except Exception:
            outcomes = ["Yes", "No"]
    else:
        outcomes = outcomes_raw or ["Yes", "No"]

    yes_price = no_price = None
    for i, outcome in enumerate(outcomes):
        if i < len(prices):
            try:
                p = float(prices[i])
            except (ValueError, TypeError):
                continue
            if str(outcome).lower() == "yes":
                yes_price = p
            elif str(outcome).lower() == "no":
                no_price = p

    # Fallback: first price = YES, second = NO
    if yes_price is None and len(prices) >= 1:
        try:
            yes_price = float(prices[0])
        except (ValueError, TypeError):
            pass
    if no_price is None and len(prices) >= 2:
        try:
            no_price = float(prices[1])
        except (ValueError, TypeError):
            pass

    return yes_price, no_price


def parse_market(raw: dict, target_symbols: list[str] | None = None) -> dict | None:
    """
    Parse a raw Gamma market dict into a normalised structure.
    Returns None if the market is not a supported crypto Up/Down type.
    """
    question = raw.get("question") or raw.get("title") or ""
    if not question:
        return None

    symbol = _parse_symbol(question)
    if symbol is None:
        return None

    if target_symbols and symbol not in target_symbols:
        return None

    direction = _parse_direction(question)
    if direction is None:
        return None

    target_price = None
    market_type = "directional"
    if direction in ("above", "below"):
        target_price = _parse_target(question)
        if target_price is None:
            # Try description field
            desc = raw.get("description") or ""
            target_price = _parse_target(desc)
        if target_price is None:
            # Can't model this without a strike
            return None
        market_type = "absolute_strike"

    condition_id = raw.get("conditionId") or raw.get("condition_id") or raw.get("id")
    if not condition_id:
        return None

    expiry_ts = _parse_expiry(raw)
    yes_token, no_token = _parse_tokens(raw)
    yes_price, no_price = _parse_prices(raw)

    try:
        liquidity = float(raw.get("liquidity") or 0)
        volume    = float(raw.get("volume") or 0)
    except (ValueError, TypeError):
        liquidity = volume = 0.0

    order_book_enabled = raw.get("orderBookEnabled") or raw.get("enableOrderBook") or False

    return {
        "condition_id":       str(condition_id),
        "question":           question,
        "slug":               raw.get("slug", ""),
        "symbol":             symbol,
        "direction":          direction,
        "target_price":       target_price,
        "market_type":        market_type,
        "expiry_ts":          expiry_ts,
        "yes_token_id":       yes_token,
        "no_token_id":        no_token,
        "yes_mid_gamma":      yes_price,
        "no_mid_gamma":       no_price,
        "liquidity":          liquidity,
        "volume":             volume,
        "order_book_enabled": bool(order_book_enabled),
    }


# ── CLOB order book ───────────────────────────────────────────────────────────

def get_order_book(token_id: str) -> dict | None:
    """
    Fetch order book for a single outcome token.
    Returns {bids, asks, best_bid, best_ask, mid, spread, ts, age_seconds}
    or None if the book is empty/unavailable.
    """
    url = f"{CLOB_BASE}/book?token_id={token_id}"
    data = _get(url, label=f"clob_book_{token_id[:12]}")
    if not isinstance(data, dict):
        return None

    raw_bids = data.get("bids") or []
    raw_asks = data.get("asks") or []

    def _parse_levels(levels: list) -> list[tuple[float, float]]:
        result = []
        for lv in levels:
            if not isinstance(lv, dict):
                continue
            try:
                p = float(lv.get("price", 0) or lv.get("p", 0))
                s = float(lv.get("size", 0)  or lv.get("s", 0))
                if p > 0 and s > 0:
                    result.append((p, s))
            except (ValueError, TypeError):
                pass
        return result

    bids = sorted(_parse_levels(raw_bids), key=lambda x: x[0], reverse=True)
    asks = sorted(_parse_levels(raw_asks), key=lambda x: x[0])

    if not bids and not asks:
        return None

    best_bid = bids[0][0] if bids else None
    best_ask = asks[0][0] if asks else None

    if best_bid and best_ask:
        mid    = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
    elif best_ask:
        mid    = best_ask
        spread = None
    elif best_bid:
        mid    = best_bid
        spread = None
    else:
        return None

    # Timestamp from response (Kraken-style unix or ISO)
    raw_ts = data.get("timestamp") or data.get("hash_ts")
    ob_ts  = time.time()
    if raw_ts:
        try:
            ob_ts = float(raw_ts)
        except (ValueError, TypeError):
            pass

    return {
        "bids":       bids,
        "asks":       asks,
        "best_bid":   best_bid,
        "best_ask":   best_ask,
        "mid":        mid,
        "spread":     spread,
        "ob_ts":      ob_ts,
        "age_seconds": time.time() - ob_ts,
        "token_id":   token_id,
    }


def get_market_books(market: dict) -> dict | None:
    """
    Fetch YES and NO order books for a parsed market dict.
    Returns {yes_book, no_book, yes_bid, yes_ask, yes_mid, no_bid, no_ask, no_mid,
             spread_yes, spread_no, combined_spread, liquidity_usd, ob_age}
    or None if books are unavailable.
    """
    yes_id = market.get("yes_token_id")
    no_id  = market.get("no_token_id")

    if not yes_id and not no_id:
        log.debug(f"No token IDs for {market['condition_id'][:12]}")
        return None

    yes_book = get_order_book(yes_id) if yes_id else None
    no_book  = get_order_book(no_id)  if no_id  else None

    if not yes_book and not no_book:
        return None

    # Best executable prices for buying YES or NO
    yes_ask = yes_book["best_ask"] if yes_book else None
    yes_bid = yes_book["best_bid"] if yes_book else None
    yes_mid = yes_book["mid"]      if yes_book else None

    no_ask  = no_book["best_ask"]  if no_book  else None
    no_bid  = no_book["best_bid"]  if no_book  else None
    no_mid  = no_book["mid"]       if no_book  else None

    spread_yes = yes_book.get("spread") if yes_book else None
    spread_no  = no_book.get("spread")  if no_book  else None

    # Combined spread across both books — sanity check: YES + NO asks should ≈ 1
    combined_gap = None
    if yes_ask and no_ask:
        combined_gap = yes_ask + no_ask - 1.0  # >0 means house edge / spread

    # Estimate liquidity from depth at best levels
    def _depth(book: dict | None, n: int = 5) -> float:
        if not book:
            return 0.0
        total = 0.0
        for price, size in (book.get("bids") or [])[:n]:
            total += price * size
        for price, size in (book.get("asks") or [])[:n]:
            total += price * size
        return total

    liquidity_usd = _depth(yes_book) + _depth(no_book)

    # Age: use the older of the two books
    ages = []
    if yes_book:
        ages.append(yes_book.get("age_seconds", 0))
    if no_book:
        ages.append(no_book.get("age_seconds", 0))
    ob_age = max(ages) if ages else 999

    return {
        "yes_book":       yes_book,
        "no_book":        no_book,
        "yes_bid":        yes_bid,
        "yes_ask":        yes_ask,
        "yes_mid":        yes_mid,
        "no_bid":         no_bid,
        "no_ask":         no_ask,
        "no_mid":         no_mid,
        "spread_yes":     spread_yes,
        "spread_no":      spread_no,
        "combined_gap":   combined_gap,
        "liquidity_usd":  liquidity_usd,
        "ob_age":         ob_age,
    }
