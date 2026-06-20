"""exec_agent.py — Execution Optimizer Agent.

Decides order type (limit vs market), partial-profit structure, and
SL/trailing-stop configuration based on live order book and signal confidence.

Expected output schema
----------------------
    {
        "order_type": "limit" | "market" | "none",
        "entry_price": float,    # 0.0 for market
        "partials": [
            {"tp": float, "pct": 0.33, "label": "TP1"},
            {"tp": float, "pct": 0.33, "label": "TP2"},
            {"tp": float, "pct": 0.34, "label": "TP3"},
        ],
        "sl_order": {"trigger_price": float, "order_type": "stop_market", "reduce_only": True},
        "trailing_after_tp2": True,
        "spread": float,
        "spread_pct": float,
        "timestamp": str,
    }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from layer1_data import DataCache
from layer3_trading import OrderManager

logger = logging.getLogger(__name__)


class ExecAgent:
    """Low-latency execution specialist.

    Parameters
    ----------
    order_manager : OrderManager
        Layer-3 order manager (used for order book reads, not direct placement).
    data_cache : DataCache
        Layer-1 cache for live order book + candles.
    """

    def __init__(self, order_manager: OrderManager, data_cache: DataCache) -> None:
        self.order_manager = order_manager
        self.data_cache = data_cache

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def optimize(
        self, signal: Dict[str, Any], risk_decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build an execution plan for an approved trade.

        Decisions
        ---------
        - **Order type**: limit if spread is tight; market if momentum is strong
          (confidence > 85).
        - **Partials**: TP1=33%, TP2=33%, TP3=34% runner.
        - **SL**: stop-market, reduce-only.
        - **Trailing**: activate after TP2 hit.

        Parameters
        ----------
        signal : dict
            Output of :meth:`SignalAgent.generate`.
        risk_decision : dict
            Output of :meth:`RiskAgent.evaluate` (must have ``approved=True``).

        Returns
        -------
        dict
            Execution plan with order type, partials, SL, trailing config.
        """
        try:
            if not risk_decision.get("approved", False):
                return self._empty_result("Risk not approved")

            symbol = signal.get("symbol", "")
            entry_price = float(signal.get("entry", 0.0))
            stop_loss = float(signal.get("stop", 0.0))
            tp1 = float(signal.get("tp1", 0.0))
            tp2 = float(signal.get("tp2", 0.0))
            tp3 = float(signal.get("tp3", 0.0))
            confidence = float(signal.get("confidence", 0.0))

            # --- Live order book analysis ---
            spread, spread_pct = self._compute_spread(symbol)

            # --- Order type decision ---
            order_type = self._decide_order_type(
                spread_pct=spread_pct, confidence=confidence
            )

            # --- Partials (33/33/34) ---
            partials: List[Dict[str, Any]] = [
                {"tp": round(tp1, 2), "pct": 0.33, "label": "TP1"},
                {"tp": round(tp2, 2), "pct": 0.33, "label": "TP2"},
                {"tp": round(tp3, 2), "pct": 0.34, "label": "TP3"},
            ]

            # --- SL order config ---
            sl_order = {
                "trigger_price": round(stop_loss, 2),
                "order_type": "stop_market",
                "reduce_only": True,
            }

            result = {
                "order_type": order_type,
                "entry_price": round(entry_price, 2) if order_type == "limit" else 0.0,
                "partials": partials,
                "sl_order": sl_order,
                "trailing_after_tp2": True,
                "spread": round(spread, 4),
                "spread_pct": round(spread_pct, 6),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(
                "ExecAgent: %s order_type=%s entry=%.2f partials=%d spread_pct=%.4f%%",
                symbol,
                order_type,
                entry_price,
                len(partials),
                spread_pct * 100,
            )
            return result

        except Exception as exc:
            logger.error("ExecAgent optimize failed: %s", exc)
            return self._empty_result(f"Optimization error: {exc}")

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _compute_spread(self, symbol: str) -> tuple[float, float]:
        """Return (spread, spread_pct) from live order book."""
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
                    mid = (best_ask + best_bid) / 2.0
                    spread_pct = spread / mid if mid > 0 else 0.0
                    return spread, spread_pct
        except Exception as exc:
            logger.debug("Orderbook read failed for %s: %s", symbol, exc)
        return 0.0, 0.0

    @staticmethod
    def _decide_order_type(spread_pct: float, confidence: float) -> str:
        """Choose limit or market based on spread and momentum.

        Rules
        -----
        - Spread > 0.03 % (wide) → market if confidence > 85, else limit.
        - Confidence > 85 (strong momentum) → market for quick fill.
        - Otherwise → limit for better price.
        """
        if spread_pct > 0.0003 and confidence > 85.0:  # noqa: PLR2004
            logger.info("ExecAgent: wide spread + high confidence → market order")
            return "market"
        if confidence > 85.0:  # noqa: PLR2004
            logger.info("ExecAgent: high confidence momentum → market order")
            return "market"
        return "limit"

    @staticmethod
    def _empty_result(reason: str) -> Dict[str, Any]:
        return {
            "order_type": "none",
            "reason": reason,
            "partials": [],
            "sl_order": {},
            "trailing_after_tp2": False,
        }
