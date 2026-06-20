"""
order_manager.py — Order lifecycle, OCO brackets, partial profit-taking, and trailing stops.

State machine: pending → filled → partial_tp1 → partial_tp2 → closed
- TP1 (1R): close 33 % of original position, move SL to breakeven
- TP2 (2R): close 33 % of original position, activate trailing stop on remainder
- TP3 (3R+): runner with trailing stop (or manual TP3)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .execution_engine import ExecutionEngine
from .position_tracker import PositionTracker

logger = logging.getLogger(__name__)


class OrderManager:
    """
    High-level order manager that wraps the ExecutionEngine.

    Parameters
    ----------
    execution_engine : ExecutionEngine
        Initialized CCXT execution engine.
    """

    def __init__(self, execution_engine: ExecutionEngine):
        self.engine = execution_engine
        self._state: Dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Entry
    # ------------------------------------------------------------------

    async def enter_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: float,
        take_profit_3: float,
        size: float,
        order_type: str = "limit",
    ) -> dict:
        """
        Place entry order + OCO bracket (SL + TP1 + TP2 + TP3).

        Parameters
        ----------
        symbol : str
            CCXT unified symbol.
        side : str
            "buy" (long) or "sell" (short).
        entry_price : float
            Limit price (ignored if ``order_type="market"``).
        stop_loss : float
            Stop-loss trigger price.
        take_profit_1 : float
            TP1 price (1R, ~33 % scale-out).
        take_profit_2 : float
            TP2 price (2R, ~33 % scale-out).
        take_profit_3 : float
            TP3 price (3R+, runner).
        size : float
            Position size in contracts.
        order_type : str, default "limit"
            "limit" or "market".

        Returns
        -------
        dict
            Bracket result with ``trade_id`` and order IDs.
        """
        if size <= 0:
            return {"success": False, "error": "Invalid size <= 0"}

        entry = entry_price if order_type.lower() == "limit" else 0.0

        result = await self.engine.place_bracket_order(
            symbol=symbol,
            side=side,
            amount=size,
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            take_profit_3=take_profit_3,
        )

        if not result.get("success"):
            return result

        # Generate a simple trade ID (caller may override with UUID)
        import uuid
        trade_id = str(uuid.uuid4())[:8]

        bracket = result.get("bracket", {})
        self._state[trade_id] = {
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "initial_size": size,
            "remaining_size": size,
            "stop_loss": stop_loss,
            "tp1": take_profit_1,
            "tp2": take_profit_2,
            "tp3": take_profit_3,
            "tp1_hit": False,
            "tp2_hit": False,
            "sl_moved_breakeven": False,
            "trailing_active": False,
            "trailing_stop_price": None,
            "trail_distance": None,
            "status": "pending",
            "orders": {
                "entry_id": bracket.get("entry", {}).get("order_id"),
                "tp2_id": bracket.get("tp2", {}).get("order_id"),
                "tp3_id": bracket.get("tp3", {}).get("order_id"),
                # TP1 and SL are attached to entry via Bybit params; we don't have separate IDs
            },
        }

        logger.info(
            "Enter position: %s %s %.4f @ %.2f (SL=%.2f TP1=%.2f TP2=%.2f TP3=%.2f)",
            side, symbol, size, entry_price, stop_loss, take_profit_1, take_profit_2, take_profit_3,
        )
        return {
            "success": True,
            "trade_id": trade_id,
            "bracket": bracket,
        }

    # ------------------------------------------------------------------
    # Partial management
    # ------------------------------------------------------------------

    async def manage_partials(self, symbol: str, position: dict):
        """
        Monitor fills and apply partial-profit logic.

        Must be called periodically (e.g., every 1–5 s) while position is open.

        Parameters
        ----------
        symbol : str
            CCXT unified symbol.
        position : dict
            Position dict from ``ExecutionEngine.get_position()``.
        """
        if not position.get("open"):
            return

        # Find active trade record for this symbol
        trade = self._find_active_trade(symbol)
        if trade is None:
            return

        current_size = float(position.get("contracts", 0))
        initial_size = trade["initial_size"]

        # Detect TP1 fill: size reduced by ~33 %
        if not trade["tp1_hit"] and current_size < initial_size * 0.95:
            trade["tp1_hit"] = True
            trade["remaining_size"] = current_size
            trade["status"] = "partial_tp1"
            logger.info("TP1 hit for %s: size reduced %.4f → %.4f", symbol, initial_size, current_size)

            # Move SL to breakeven
            await self.move_stop_to_breakeven(symbol, position, trade["entry_price"])

            # Cancel old TP2/TP3 and re-size for remainder
            await self._cancel_remaining_tps(trade)
            await self._place_resized_tps(trade, current_size)

        # Detect TP2 fill: size reduced again by ~33 % of original
        elif trade["tp1_hit"] and not trade["tp2_hit"] and current_size < initial_size * 0.60:
            trade["tp2_hit"] = True
            trade["remaining_size"] = current_size
            trade["status"] = "partial_tp2"
            logger.info("TP2 hit for %s: size reduced → %.4f", symbol, current_size)

            # Cancel remaining TP orders, activate trailing stop on runner
            await self._cancel_remaining_tps(trade)
            await self.apply_trailing_stop(
                symbol, position, trail_distance=trade.get("trail_distance", 0.0)
            )

        # Update trailing stop if active
        if trade["trailing_active"]:
            await self._update_trailing_stop(trade, position)

    async def _cancel_remaining_tps(self, trade: dict):
        """Cancel TP2/TP3 orders for a trade."""
        symbol = trade["symbol"]
        for key in ("tp2_id", "tp3_id"):
            oid = trade["orders"].get(key)
            if oid:
                await self.engine.cancel_order(symbol, oid)
                trade["orders"][key] = None

    async def _place_resized_tps(self, trade: dict, remaining_size: float):
        """Re-place TP2 and TP3 sized for the remaining position."""
        symbol = trade["symbol"]
        side = trade["side"]
        # Close side is opposite of entry side
        close_side = "sell" if side == "buy" else "buy"

        # TP2 = 50 % of remaining (≈ 33 % of original)
        tp2_size = round(remaining_size * 0.5, 3)
        tp3_size = round(remaining_size - tp2_size, 3)

        if tp2_size > 0:
            tp2_order = await self.engine.place_limit_order(
                symbol, close_side, tp2_size, trade["tp2"], reduce_only=True
            )
            if tp2_order.get("success"):
                trade["orders"]["tp2_id"] = tp2_order["order_id"]

        if tp3_size > 0:
            tp3_order = await self.engine.place_limit_order(
                symbol, close_side, tp3_size, trade["tp3"], reduce_only=True
            )
            if tp3_order.get("success"):
                trade["orders"]["tp3_id"] = tp3_order["order_id"]

    # ------------------------------------------------------------------
    # Trailing stop
    # ------------------------------------------------------------------

    async def apply_trailing_stop(
        self,
        symbol: str,
        position: dict,
        trail_distance: float,
    ) -> dict:
        """
        Activate a trailing stop on the current open position.

        Parameters
        ----------
        symbol : str
            CCXT unified symbol.
        position : dict
            Current position dict.
        trail_distance : float
            Absolute price distance for the trailing stop (e.g., 1.5 × ATR).

        Returns
        -------
        dict
            Result of the internal state update.
        """
        trade = self._find_active_trade(symbol)
        if trade is None:
            return {"success": False, "error": "No active trade found"}

        side = position.get("side")  # "long" or "short"
        entry_price = trade["entry_price"]

        # Initialize trailing stop price
        if side == "long":
            initial_sl = entry_price - trail_distance
        else:
            initial_sl = entry_price + trail_distance

        trade["trailing_active"] = True
        trade["trailing_stop_price"] = initial_sl
        trade["trail_distance"] = trail_distance
        trade["status"] = "trailing"

        logger.info(
            "Trailing stop activated for %s: entry=%.2f trail=%.2f initial_sl=%.2f",
            symbol, entry_price, trail_distance, initial_sl,
        )
        return {"success": True, "trailing_stop_price": initial_sl}

    async def _update_trailing_stop(self, trade: dict, position: dict):
        """Internal periodic update of trailing stop price."""
        symbol = trade["symbol"]
        side = position.get("side")
        mark_price = float(position.get("mark_price", 0))
        if mark_price <= 0:
            return

        distance = trade["trail_distance"]
        current_sl = trade["trailing_stop_price"]

        if side == "long":
            new_sl = mark_price - distance
            if new_sl > current_sl:
                trade["trailing_stop_price"] = new_sl
                logger.info("Trailing stop updated for %s: %.2f → %.2f", symbol, current_sl, new_sl)
                # Cancel old SL and place new one
                await self._replace_sl(symbol, new_sl, "buy" if side == "short" else "sell")
        else:
            new_sl = mark_price + distance
            if new_sl < current_sl:
                trade["trailing_stop_price"] = new_sl
                logger.info("Trailing stop updated for %s: %.2f → %.2f", symbol, current_sl, new_sl)
                await self._replace_sl(symbol, new_sl, "buy")

    async def _replace_sl(self, symbol: str, new_sl: float, sl_side: str):
        """Cancel all existing SL orders and place a new stop-market SL."""
        # Cancel all open orders that look like stop-loss (we approximate by cancelling all)
        # In production, track SL order IDs separately.
        await self.engine.cancel_all_orders(symbol)
        # Place stop-market order (CCXT create_order with type "StopMarket")
        # This is a simplified approach; Bybit v5 requires specific stopOrderType
        try:
            ex = await self.engine._ensure_connection()
            # For Bybit v5, stop-market is "Market" with triggerPrice
            await ex.create_order(
                symbol,
                "Market",
                sl_side.capitalize(),
                0,  # amount determined by position
                None,
                {
                    "triggerPrice": str(new_sl),
                    "reduceOnly": True,
                    "positionIdx": 0,
                },
            )
        except Exception as e:
            logger.error("Failed to replace SL for %s: %s", symbol, e)

    # ------------------------------------------------------------------
    # Breakeven
    # ------------------------------------------------------------------

    async def move_stop_to_breakeven(
        self,
        symbol: str,
        position: dict,
        entry_price: float,
    ) -> dict:
        """
        Move stop-loss to the entry price (breakeven).

        Parameters
        ----------
        symbol : str
            CCXT unified symbol.
        position : dict
            Current position.
        entry_price : float
            The entry price to set as new SL.

        Returns
        -------
        dict
            Result of SL replacement.
        """
        trade = self._find_active_trade(symbol)
        if trade is None:
            return {"success": False, "error": "No active trade"}

        side = position.get("side")
        sl_side = "sell" if side == "long" else "buy"

        # Cancel existing SL orders and place new one at breakeven
        await self._replace_sl(symbol, entry_price, sl_side)
        trade["sl_moved_breakeven"] = True
        trade["stop_loss"] = entry_price

        logger.info("SL moved to breakeven for %s: %.2f", symbol, entry_price)
        return {"success": True, "new_sl": entry_price}

    # ------------------------------------------------------------------
    # Emergency close
    # ------------------------------------------------------------------

    async def emergency_close(self, symbol: str):
        """
        Market-close all positions on ``symbol`` immediately and cancel all orders.

        Parameters
        ----------
        symbol : str
            CCXT unified symbol.
        """
        logger.critical("EMERGENCY CLOSE triggered for %s", symbol)
        await self.engine.cancel_all_orders(symbol)
        await self.engine.close_position(symbol)

        trade = self._find_active_trade(symbol)
        if trade:
            trade["status"] = "emergency_closed"
            trade["remaining_size"] = 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_active_trade(self, symbol: str) -> Optional[dict]:
        """Return the first active (non-closed) trade record for a symbol."""
        for trade in self._state.values():
            if trade["symbol"] == symbol and trade["status"] not in ("closed", "emergency_closed"):
                return trade
        return None

    def get_trade_state(self, trade_id: str) -> Optional[dict]:
        """Return internal state dict for a trade ID."""
        return self._state.get(trade_id)

    def list_active_trades(self) -> List[dict]:
        """Return all active trade state records."""
        return [t for t in self._state.values() if t["status"] not in ("closed", "emergency_closed")]
