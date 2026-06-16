"""
scanner.py — Main scanning loop.

Each cycle:
  1. Fetch active crypto Up/Down markets
  2. Fetch reference crypto prices
  3. For each market: fetch order book, compute fair value, evaluate edge
  4. Classify signals: IGNORE / WATCH / PAPER_TRADE
  5. Execute paper trades on qualifying signals
  6. Update open positions (mark to market + exit checks)
  7. Save snapshots to SQLite
"""

from __future__ import annotations
import datetime
import logging
import time
from typing import Optional

import polymarket_client as pm
import crypto_price_client as cpc
import fair_value as fv
import storage
from paper_trader import PaperTrader
from risk import RiskManager

log = logging.getLogger(__name__)

# Cooldown per market: don't re-enter a market we recently traded
_market_cooldowns: dict[str, float] = {}  # condition_id → unix ts of last entry


class Scanner:
    def __init__(self, conn, cfg: dict) -> None:
        self.conn  = conn
        self.cfg   = cfg
        self.risk  = RiskManager(cfg)
        self.paper = PaperTrader(conn, cfg, self.risk)

        self._scan_count = 0
        self._signal_count = 0

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self, once: bool = False) -> None:
        log.info("=" * 65)
        log.info("  POLYMARKET EDGE SCANNER — PAPER MODE")
        log.info(f"  symbols={self.cfg.get('symbols')} interval={self.cfg.get('polling_interval_seconds')}s")
        log.info("=" * 65)

        while True:
            try:
                self._cycle()
            except KeyboardInterrupt:
                log.info("Scan interrupted by user.")
                self.paper.print_stats()
                break
            except Exception as exc:
                log.error(f"Scan cycle error: {exc}", exc_info=True)

            if once:
                break

            interval = self.cfg.get("polling_interval_seconds", 30)
            log.debug(f"Sleeping {interval}s until next cycle...")
            time.sleep(interval)

    # ── Single scan cycle ─────────────────────────────────────────────────────

    def _cycle(self) -> None:
        now        = time.time()
        date_str   = datetime.datetime.utcfromtimestamp(now).strftime("%Y-%m-%d")
        ts_str     = datetime.datetime.utcfromtimestamp(now).strftime("%H:%M:%S")
        self._scan_count += 1

        log.info(f"\n[{ts_str} UTC] SCAN #{self._scan_count}")

        # ── Refresh reference prices ──────────────────────────────────────────
        symbols  = self.cfg.get("symbols", ["BTC", "ETH", "SOL"])
        sources  = self.cfg.get("reference_exchanges", ["kraken", "binance", "coinbase"])
        ref_prices: dict[str, dict] = {}

        for sym in symbols:
            result = cpc.fetch_price(sym, sources)
            if result:
                ref_prices[sym] = result
                log.debug(f"  {sym} = ${result['price']:,.2f} (via {result['source']})")
            else:
                log.warning(f"  {sym}: all price sources failed")

        # ── Fetch active markets ──────────────────────────────────────────────
        raw_markets = pm.get_active_markets(
            limit=self.cfg.get("max_markets_per_scan", 100)
        )
        log.info(f"  Fetched {len(raw_markets)} raw markets from Gamma API")

        parsed: list[dict] = []
        for raw in raw_markets:
            m = pm.parse_market(raw, target_symbols=symbols)
            if m:
                parsed.append(m)
                storage.upsert_market(self.conn, m)

        log.info(f"  {len(parsed)} matching crypto Up/Down markets")
        storage.bump_daily_metric(self.conn, date_str, scans=1, markets_seen=len(parsed))

        # ── Update open paper positions (mark to market + exits) ──────────────
        self._update_positions(ref_prices, now)

        # ── Scan candidates for new signals ───────────────────────────────────
        signals_this_cycle = 0

        # Sort by liquidity descending
        candidates = sorted(parsed, key=lambda m: m.get("liquidity", 0), reverse=True)

        for market in candidates:
            try:
                sig = self._evaluate_market(market, ref_prices, now, date_str)
                if sig and sig.get("action") == "PAPER_TRADE":
                    signals_this_cycle += 1
                    self._signal_count += 1
            except Exception as exc:
                log.debug(f"  Market eval error [{market['condition_id'][:12]}]: {exc}")

        log.info(
            f"  Cycle complete — signals_this_cycle={signals_this_cycle} "
            f"total_signals={self._signal_count} "
            f"open_positions={self.paper.open_count} "
            f"equity=${self.paper.equity:.2f}"
        )

    # ── Evaluate a single market ──────────────────────────────────────────────

    def _evaluate_market(
        self,
        market:     dict,
        ref_prices: dict,
        now:        float,
        date_str:   str,
    ) -> Optional[dict]:
        cid    = market["condition_id"]
        symbol = market.get("symbol")
        q      = market.get("question", "")[:70]

        # Time remaining check
        expiry_ts = market.get("expiry_ts")
        if not expiry_ts:
            return None

        t_min = (expiry_ts - now) / 60
        min_t = self.cfg.get("min_time_to_expiry_minutes", 10)
        max_t = self.cfg.get("max_time_to_expiry_hours", 72) * 60

        if t_min < min_t or t_min > max_t:
            log.debug(f"  SKIP [{q}] — expiry {t_min:.0f}m (allowed {min_t}-{max_t/60:.0f}h)")
            return None

        # Reference price
        ref = ref_prices.get(symbol)
        if not ref:
            log.debug(f"  SKIP [{q}] — no ref price for {symbol}")
            return None

        current_price = ref["price"]
        ref_age       = now - ref["ts"]

        # Volatility and momentum from buffer
        vol_window = self.cfg.get("vol_window_minutes", 15) * 60
        mom_window = self.cfg.get("momentum_window_seconds", 180)

        vol_annual, n_samples = cpc.estimate_realized_vol(symbol, vol_window)
        momentum = cpc.get_momentum(symbol, mom_window)

        # Order book
        if not market.get("order_book_enabled") and \
           not (market.get("yes_token_id") or market.get("no_token_id")):
            log.debug(f"  SKIP [{q}] — order book not enabled and no token IDs")
            return None

        books = pm.get_market_books(market)
        if not books:
            log.debug(f"  SKIP [{q}] — could not fetch order book")
            return None

        ob_age    = books.get("ob_age", 999)
        liquidity = books.get("liquidity_usd", 0)

        # Choose which outcome to trade
        # We evaluate both YES and NO and take the best adjusted edge
        candidates = []

        for outcome, executable_price, fair_val_side in [
            ("YES", books.get("yes_ask"), None),
            ("NO",  books.get("no_ask"),  None),
        ]:
            if not executable_price or executable_price <= 0 or executable_price >= 1.0:
                continue

            # Compute fair value for YES, then derive per-outcome fair value
            fv_result = fv.compute_fair_value(
                market_type        = market.get("market_type", "directional"),
                direction          = market.get("direction"),
                target_price       = market.get("target_price"),
                current_price      = current_price,
                expiry_ts          = expiry_ts,
                now_ts             = now,
                vol_annual         = vol_annual,
                n_vol_samples      = n_samples,
                momentum_pct_per_min = momentum,
                ref_price_age      = ref_age,
                ob_age             = ob_age,
                cfg                = self.cfg,
            )

            if outcome == "YES":
                fair_p = fv_result.yes_prob
            else:
                fair_p = fv_result.no_prob

            spread = books.get(f"spread_{outcome.lower()}") or 0.05
            edge_result = fv.compute_edge(fair_p, executable_price, spread, self.cfg)

            adj_edge = edge_result.get("adjusted_edge")
            raw_edge = edge_result.get("raw_edge")

            if adj_edge is None:
                continue

            candidates.append({
                "outcome":           outcome,
                "executable_price":  executable_price,
                "fair_value":        fair_p,
                "fv_result":         fv_result,
                "raw_edge":          raw_edge,
                "adjusted_edge":     adj_edge,
                "spread":            spread,
            })

        if not candidates:
            return None

        # Best candidate by adjusted edge
        best = max(candidates, key=lambda c: c["adjusted_edge"])
        outcome      = best["outcome"]
        exec_price   = best["executable_price"]
        fair_p       = best["fair_value"]
        fv_result    = best["fv_result"]
        raw_edge     = best["raw_edge"]
        adj_edge     = best["adjusted_edge"]
        spread       = best["spread"]

        # Save snapshot
        snap = {
            "ts":              now,
            "condition_id":    cid,
            "yes_bid":         books.get("yes_bid"),
            "yes_ask":         books.get("yes_ask"),
            "yes_mid":         books.get("yes_mid"),
            "no_bid":          books.get("no_bid"),
            "no_ask":          books.get("no_ask"),
            "no_mid":          books.get("no_mid"),
            "spread":          spread,
            "liquidity":       liquidity,
            "ref_price":       current_price,
            "ref_price_source": ref.get("source"),
            "ref_price_age":   ref_age,
            "vol_annual":      vol_annual,
            "momentum":        momentum,
            "fair_yes":        fv_result.yes_prob,
            "fair_no":         fv_result.no_prob,
            "confidence":      fv_result.confidence,
        }
        storage.save_snapshot(self.conn, snap)

        # ── Classify signal ────────────────────────────────────────────────────
        min_edge = self.cfg.get("min_edge_pct", 0.04)
        min_conf = self.cfg.get("min_fair_value_confidence", 0.55)

        if adj_edge < 0:
            action = "IGNORE"
            reason = f"negative_edge ({adj_edge*100:.2f}%)"
        elif adj_edge < min_edge * 0.5:
            action = "IGNORE"
            reason = f"edge_too_small ({adj_edge*100:.2f}%)"
        elif adj_edge < min_edge:
            action = "WATCH"
            reason = f"edge={adj_edge*100:.2f}% (threshold {min_edge*100:.1f}%)"
        elif fv_result.confidence < min_conf:
            action = "WATCH"
            reason = f"low_confidence={fv_result.confidence:.2f}"
        elif liquidity < self.cfg.get("min_liquidity_usd", 500):
            action = "WATCH"
            reason = f"low_liquidity=${liquidity:.0f}"
        elif spread > self.cfg.get("max_spread", 0.08):
            action = "WATCH"
            reason = f"wide_spread={spread*100:.1f}%"
        elif ob_age > self.cfg.get("max_orderbook_age_seconds", 60):
            action = "WATCH"
            reason = f"stale_ob={ob_age:.0f}s"
        elif ref_age > self.cfg.get("max_ref_price_age_seconds", 30):
            action = "WATCH"
            reason = f"stale_ref={ref_age:.0f}s"
        elif _in_cooldown(cid):
            action = "WATCH"
            reason = "market_cooldown"
        else:
            action = "PAPER_TRADE"
            reason = f"adj_edge={adj_edge*100:.2f}% conf={fv_result.confidence:.2f}"

        # Save signal to DB
        sig = {
            "ts":              now,
            "condition_id":    cid,
            "outcome":         outcome,
            "action":          action,
            "fair_value":      fair_p,
            "executable_price": exec_price,
            "raw_edge":        raw_edge,
            "adjusted_edge":   adj_edge,
            "confidence":      fv_result.confidence,
            "reason":          fv_result.reason,
            "skip_reason":     reason if action != "PAPER_TRADE" else None,
        }
        signal_id = storage.save_signal(self.conn, sig)
        storage.bump_daily_metric(self.conn, date_str, signals=1)

        # ── Log signal ────────────────────────────────────────────────────────
        _log_signal(action, market, best, fv_result, ref, t_min, vol_annual, momentum, liquidity, ob_age, reason)

        # ── Execute paper trade ───────────────────────────────────────────────
        if action == "PAPER_TRADE":
            trade_id = self.paper.open(
                market           = market,
                outcome          = outcome,
                executable_price = exec_price,
                fair_value       = fair_p,
                edge             = adj_edge,
                spread           = spread,
                liquidity        = liquidity,
                signal_id        = signal_id,
            )
            if trade_id:
                _set_cooldown(cid, self.cfg.get("cooldown_after_loss_minutes", 5))
                storage.bump_daily_metric(self.conn, date_str, paper_trades=1)

        return sig

    # ── Update open positions ─────────────────────────────────────────────────

    def _update_positions(self, ref_prices: dict, now: float) -> None:
        if not self.paper._positions:
            return

        for trade_id, pos in list(self.paper._positions.items()):
            cid    = pos["condition_id"]
            outcome = pos["outcome"]

            # We need current mid for the outcome token
            # Re-fetch order book if we have token IDs from our market cache
            current_mid  = None
            current_fair = None

            try:
                row = self.conn.execute(
                    "SELECT * FROM markets WHERE condition_id = ?", (cid,)
                ).fetchone()
                if row:
                    market = dict(row)
                    books  = pm.get_market_books(market)
                    if books:
                        current_mid = books.get(f"{'yes' if outcome == 'YES' else 'no'}_mid")

                    # Quick fair value refresh
                    sym = market.get("symbol")
                    ref = ref_prices.get(sym) if sym else None
                    if ref and market.get("expiry_ts"):
                        vol_annual, n = cpc.estimate_realized_vol(sym or "BTC", 900)
                        momentum = cpc.get_momentum(sym or "BTC", 180)
                        fv_r = fv.compute_fair_value(
                            market_type=market.get("market_type", "directional"),
                            direction=market.get("direction"),
                            target_price=market.get("target_price"),
                            current_price=ref["price"],
                            expiry_ts=market["expiry_ts"],
                            now_ts=now,
                            vol_annual=vol_annual,
                            n_vol_samples=n,
                            momentum_pct_per_min=momentum,
                            ref_price_age=now - ref["ts"],
                            ob_age=books.get("ob_age", 60) if books else 60,
                            cfg=self.cfg,
                        )
                        current_fair = fv_r.yes_prob if outcome == "YES" else fv_r.no_prob
            except Exception as exc:
                log.debug(f"Position update error [{cid[:12]}]: {exc}")

            close = self.paper.update(
                trade_id    = trade_id,
                current_mid = current_mid,
                fair_value  = current_fair,
                now_ts      = now,
            )
            if close:
                pnl = close.get("pnl", 0)
                date_str = datetime.datetime.utcfromtimestamp(now).strftime("%Y-%m-%d")
                if pnl > 0:
                    storage.bump_daily_metric(self.conn, date_str, paper_wins=1, paper_pnl=pnl)
                else:
                    storage.bump_daily_metric(self.conn, date_str, paper_losses=1, paper_pnl=pnl)


# ── Cooldown helpers ──────────────────────────────────────────────────────────

def _set_cooldown(condition_id: str, minutes: float) -> None:
    _market_cooldowns[condition_id] = time.time() + minutes * 60


def _in_cooldown(condition_id: str) -> bool:
    expiry = _market_cooldowns.get(condition_id, 0)
    return time.time() < expiry


# ── Signal logging ────────────────────────────────────────────────────────────

def _log_signal(
    action:    str,
    market:    dict,
    best:      dict,
    fv_result,
    ref:       dict,
    t_min:     float,
    vol:       Optional[float],
    momentum:  float,
    liquidity: float,
    ob_age:    float,
    reason:    str,
) -> None:
    q        = market.get("question", "")[:65]
    outcome  = best["outcome"]
    exec_p   = best["executable_price"]
    fair_p   = best["fair_value"]
    raw_e    = best["raw_edge"]
    adj_e    = best["adjusted_edge"]

    if action == "IGNORE":
        log.debug(f"  IGNORE   | {q} | {reason}")
        return

    sep = "-" * 65
    if action == "PAPER_TRADE":
        log.info(sep)
        log.info(f"  *** SIGNAL: {action} ***")
    else:
        log.info(f"  {action:8s} | {q}")

    if action in ("WATCH", "PAPER_TRADE"):
        log.info(f"  Question : {market.get('question', '')}")
        log.info(
            f"  Market   : {market['symbol']} {market.get('market_type')} "
            f"direction={market.get('direction')} target={market.get('target_price')}"
        )
        log.info(
            f"  Expiry   : {_fmt_ts(market.get('expiry_ts'))} "
            f"(in {t_min:.0f}m)"
        )
        log.info(
            f"  Outcome  : {outcome} @ ${exec_p:.4f} ask "
            f"| fair={fair_p:.4f} "
            f"| raw_edge={raw_e*100:+.2f}% adj_edge={adj_e*100:+.2f}%"
        )
        log.info(
            f"  Ref price: ${ref['price']:,.2f} ({ref['source']}, "
            f"{now_minus(ref['ts']):.0f}s old)"
        )
        if vol:
            log.info(
                f"  Vol      : {vol*100:.0f}% ann  "
                f"| momentum={momentum:+.4f}%/min"
            )
        log.info(
            f"  Liquidity: ${liquidity:,.0f}  "
            f"| ob_age={ob_age:.0f}s "
            f"| confidence={fv_result.confidence:.2f}"
        )
        if fv_result.penalties:
            log.info(f"  Penalties: {', '.join(fv_result.penalties)}")
        if action == "WATCH":
            log.info(f"  (not trading: {reason})")
        log.info(sep)


def _fmt_ts(ts: Optional[float]) -> str:
    if not ts:
        return "unknown"
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M UTC")


def now_minus(ts: float) -> float:
    return time.time() - ts
