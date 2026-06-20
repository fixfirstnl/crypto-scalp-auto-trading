"""risk_agent.py — Risk Management Agent with Veto Power.

Checks all prop-firm style risk gates before every trade:
  daily loss, weekly loss, max positions, consecutive losses, drawdown,
  spread guard, ATR volatility filter, correlation limit, session filter.

Calculates position size via :meth:`RiskManager.calculate_position_size`.
Has the power to VETO (``approved=False``) any trade that fails a gate.

Expected output schema
----------------------
    {
        "approved": bool,
        "size": float,          # contracts
        "risk_score": 0-100,    # lower = safer
        "max_loss": float,      # $ at risk
        "reason": str,
        "details": { ... },     # optional diagnostics
    }
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from layer1_data import DataCache
from layer3_trading import PositionTracker, RiskManager

logger = logging.getLogger(__name__)


class RiskAgent:
    """Prop-firm risk manager with strict veto power.

    Parameters
    ----------
    risk_manager : RiskManager
        Layer-3 risk gate instance.
    position_tracker : PositionTracker
        Layer-3 SQLite-backed position / PnL tracker.
    data_cache : DataCache
        Layer-1 cache for order book + candles.
    """

    def __init__(
        self,
        risk_manager: RiskManager,
        position_tracker: PositionTracker,
        data_cache: DataCache,
    ) -> None:
        self.risk_manager = risk_manager
        self.position_tracker = position_tracker
        self.data_cache = data_cache

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def evaluate(
        self, signal: Dict[str, Any], symbol: str
    ) -> Dict[str, Any]:
        """Evaluate risk for a proposed trade signal.

        Steps
        -----
        1. Sync risk-manager counters from ``PositionTracker``.
        2. Compute live market metrics (spread, ATR).
        3. Run :meth:`RiskManager.check_entry_allowed`.
        4. If approved → calculate position size and risk score.
        5. If rejected → return veto with reason.

        Parameters
        ----------
        signal : dict
            Output of :meth:`SignalAgent.generate`.
        symbol : str
            CCXT unified symbol.

        Returns
        -------
        dict
            ``approved``, ``size``, ``risk_score``, ``max_loss``, ``reason``.
        """
        try:
            # --- Sync counters from database ---
            self._sync_risk_counters()

            open_positions = self.position_tracker.get_open_positions()
            stats = self.position_tracker.get_stats(days=1)
            daily_pnl = float(stats.get("daily_pnl", 0.0))
            consecutive_losses = self._count_consecutive_losses()

            current_balance = float(self.risk_manager.account_balance)
            peak = float(self.risk_manager._peak_balance)
            current_drawdown = (
                (peak - current_balance) / peak if peak > 0 else 0.0
            )

            # --- Live market metrics ---
            spread, avg_spread = self._get_spread(symbol)
            atr, avg_atr = self._get_atr(symbol)

            # --- Build risk signal ---
            risk_signal = {
                "symbol": symbol,
                "direction": signal.get("signal", "none"),
                "entry_price": float(signal.get("entry", 0.0)),
                "stop_loss": float(signal.get("stop", 0.0)),
            }

            # --- Run entry gate ---
            allowed, reason = self.risk_manager.check_entry_allowed(
                signal=risk_signal,
                open_positions=open_positions,
                daily_pnl=daily_pnl,
                consecutive_losses=consecutive_losses,
                current_drawdown=current_drawdown,
                spread=spread,
                avg_spread=avg_spread,
                atr=atr,
                avg_atr=avg_atr,
            )

            if not allowed:
                logger.warning(
                    "RiskAgent: VETO %s — %s", symbol, reason
                )
                return {
                    "approved": False,
                    "size": 0.0,
                    "risk_score": 100.0,
                    "max_loss": 0.0,
                    "reason": reason,
                }

            # --- Position sizing ---
            size = self.risk_manager.calculate_position_size(
                account_balance=current_balance,
                risk_percent=self.risk_manager.risk_per_trade,
                entry_price=risk_signal["entry_price"],
                stop_loss=risk_signal["stop_loss"],
                symbol=symbol,
            )

            if size <= 0:
                logger.warning(
                    "RiskAgent: zero size computed for %s (entry=%.2f sl=%.2f)",
                    symbol,
                    risk_signal["entry_price"],
                    risk_signal["stop_loss"],
                )
                return {
                    "approved": False,
                    "size": 0.0,
                    "risk_score": 100.0,
                    "max_loss": 0.0,
                    "reason": "Position sizing returned zero",
                }

            # --- Risk score (0-100, lower = safer) ---
            risk_score = self._compute_risk_score(
                signal, spread, avg_spread, atr, avg_atr, open_positions
            )
            max_loss = current_balance * self.risk_manager.risk_per_trade

            result = {
                "approved": True,
                "size": size,
                "risk_score": round(risk_score, 2),
                "max_loss": round(max_loss, 4),
                "reason": "All risk checks passed",
                "details": {
                    "daily_pnl": round(daily_pnl, 4),
                    "drawdown": round(current_drawdown, 4),
                    "consecutive_losses": consecutive_losses,
                    "open_positions": len(open_positions),
                    "spread": round(spread, 4),
                    "atr": round(atr, 4),
                    "size": size,
                },
            }
            logger.info(
                "RiskAgent: APPROVED %s size=%.4f risk_score=%.1f max_loss=%.2f",
                symbol,
                size,
                risk_score,
                max_loss,
            )
            return result

        except Exception as exc:
            logger.error("RiskAgent evaluate failed for %s: %s", symbol, exc)
            return {
                "approved": False,
                "size": 0.0,
                "risk_score": 100.0,
                "max_loss": 0.0,
                "reason": f"Evaluation error: {exc}",
            }

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _sync_risk_counters(self) -> None:
        """Sync ``RiskManager`` internal counters from ``PositionTracker``."""
        try:
            # Weekly PnL from last 7 days of closed trades
            history = self.position_tracker.get_trade_history(limit=200)
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            weekly_pnl = 0.0
            for trade in history:
                closed = trade.get("closed_at")
                if closed and datetime.fromisoformat(closed) >= week_ago:
                    pnl = trade.get("pnl")
                    if pnl is not None:
                        weekly_pnl += float(pnl)
            self.risk_manager._weekly_pnl = weekly_pnl  # type: ignore

            # Consecutive losses already computed in _count_consecutive_losses
        except Exception as exc:
            logger.warning("Risk counter sync failed: %s", exc)

    def _count_consecutive_losses(self) -> int:
        """Count consecutive losses from most recent closed trades."""
        try:
            history = self.position_tracker.get_trade_history(limit=50)
            consecutive = 0
            for trade in history:
                pnl = trade.get("pnl")
                if pnl is not None and float(pnl) < 0:
                    consecutive += 1
                else:
                    break
            return consecutive
        except Exception as exc:
            logger.warning("Consecutive-loss count failed: %s", exc)
            return 0

    def _get_spread(self, symbol: str) -> Tuple[float, float]:
        """Return (current_spread, estimated_avg_spread) from order book."""
        try:
            orderbook = self.data_cache.get_orderbook(symbol)
            if (
                orderbook
                and "bids" in orderbook
                and "asks" in orderbook
                and orderbook["bids"]
                and orderbook["asks"]
            ):
                best_bid = float(orderbook["bids"][0][0])
                best_ask = float(orderbook["asks"][0][0])
                if best_bid > 0 and best_ask > 0:
                    spread = best_ask - best_bid
                    return spread, spread * 0.8
        except Exception as exc:
            logger.debug("Spread read failed for %s: %s", symbol, exc)
        return 0.0, 0.0

    def _get_atr(self, symbol: str) -> Tuple[float, float]:
        """Return (current_atr, 20-period avg_atr) from 1m candles."""
        try:
            candles = self.data_cache.get_candles(symbol, "1m")
            if candles.empty or len(candles) < 20:
                return 0.0, 0.0

            high_low = candles["high"] - candles["low"]
            high_close = (candles["high"] - candles["close"].shift()).abs()
            low_close = (candles["low"] - candles["close"].shift()).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr_series = tr.ewm(span=14, adjust=False).mean()
            atr = float(atr_series.iloc[-1]) if not atr_series.empty else 0.0
            avg_atr = (
                float(atr_series.rolling(20).mean().iloc[-1])
                if len(atr_series) >= 20
                else atr
            )
            return atr, avg_atr
        except Exception as exc:
            logger.debug("ATR calculation failed for %s: %s", symbol, exc)
        return 0.0, 0.0

    def _compute_risk_score(
        self,
        signal: Dict[str, Any],
        spread: float,
        avg_spread: float,
        atr: float,
        avg_atr: float,
        open_positions: List[Dict[str, Any]],
    ) -> float:
        """Composite risk score (0-100, lower = safer)."""
        risk_score = 0.0

        # Signal confidence (inverse)
        confidence = float(signal.get("confidence", 50.0))
        risk_score += max(0.0, 50.0 - confidence * 0.5)

        # Spread penalty
        if avg_spread > 0:
            spread_ratio = spread / avg_spread
            risk_score += min(spread_ratio * 10.0, 20.0)

        # ATR volatility penalty
        if avg_atr > 0:
            atr_ratio = atr / avg_atr
            risk_score += min(atr_ratio * 10.0, 20.0)

        # Open-position penalty
        risk_score += len(open_positions) * 5.0

        return min(risk_score, 100.0)
