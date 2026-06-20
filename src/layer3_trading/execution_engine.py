"""
execution_engine.py — Direct Bybit API v5 execution engine via CCXT.

Handles all direct exchange interaction: market/limit orders, bracket orders,
cancellations, position queries, and leverage setting. Uses CCXT unified API
with Bybit-specific category handling (linear=USDT perp, inverse=coin-m).
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import ccxt
import ccxt.async_support as ccxt_async

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Async execution engine for Bybit API v5 (testnet + live).

    Parameters
    ----------
    api_key : str
        Bybit API key.
    api_secret : str
        Bybit API secret.
    testnet : bool, default True
        Use Bybit testnet (paper trading) if True.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.exchange: Optional[ccxt_async.bybit] = None
        self._connected: bool = False

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    async def _ensure_connection(self) -> ccxt_async.bybit:
        """Lazy-connect and return the CCXT exchange instance."""
        if self.exchange is not None:
            return self.exchange

        config = {
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap",  # unified swap/perp
                "adjustForTimeDifference": True,
            },
        }
        if self.testnet:
            config["urls"] = {"api": {"public": "https://api-testnet.bybit.com", "private": "https://api-testnet.bybit.com"}}

        self.exchange = ccxt_async.bybit(config)
        if self.testnet:
            self.exchange.set_sandbox_mode(True)

        await self.exchange.load_markets()
        self._connected = True
        logger.info("ExecutionEngine connected to Bybit %s", "testnet" if self.testnet else "live")
        return self.exchange

    def _category(self, symbol: str) -> str:
        """Return Bybit category for the symbol."""
        # Unified CCXT symbol: BTC/USDT:USDT → USDT perp (linear)
        # BTC/USDT:BTC → coin-margined (inverse)
        if ":USDC" in symbol or ":USDT" in symbol:
            return "linear"
        if ":BTC" in symbol or ":ETH" in symbol:
            return "inverse"
        # Default heuristic: if USDT/USDC in base → linear, else inverse
        return "linear"

    def _bybit_symbol(self, symbol: str) -> str:
        """Convert CCXT unified symbol to Bybit market symbol if needed."""
        # CCXT unified symbols already work with Bybit v5
        return symbol

    # ------------------------------------------------------------------
    # Public / read-only
    # ------------------------------------------------------------------

    async def get_account_balance(self) -> dict:
        """Fetch wallet balance for unified margin account."""
        ex = await self._ensure_connection()
        try:
            # Bybit v5 unified account
            balance = await ex.fetch_balance({"type": "swap"})
            return {
                "success": True,
                "balance": balance,
                "total_usdt": balance.get("USDT", {}).get("total", 0.0),
                "free_usdt": balance.get("USDT", {}).get("free", 0.0),
                "used_usdt": balance.get("USDT", {}).get("used", 0.0),
            }
        except Exception as e:
            logger.error("get_account_balance failed: %s", e)
            return {"success": False, "error": str(e)}

    async def get_position(self, symbol: str) -> dict:
        """Fetch current open position for a symbol."""
        ex = await self._ensure_connection()
        category = self._category(symbol)
        try:
            positions = await ex.fetch_positions([symbol])
            # Filter for open position (non-zero contracts)
            open_pos = [p for p in positions if p.get("contracts") and float(p.get("contracts", 0)) != 0]
            if not open_pos:
                return {
                    "success": True,
                    "symbol": symbol,
                    "open": False,
                    "contracts": 0.0,
                    "side": None,
                    "entry_price": None,
                    "unrealized_pnl": 0.0,
                }
            pos = open_pos[0]
            return {
                "success": True,
                "symbol": symbol,
                "open": True,
                "contracts": float(pos.get("contracts", 0)),
                "side": pos.get("side"),  # "long" or "short"
                "entry_price": float(pos.get("entryPrice", 0)),
                "mark_price": float(pos.get("markPrice", 0)),
                "unrealized_pnl": float(pos.get("unrealizedPnl", 0)),
                "leverage": float(pos.get("leverage", 1)),
                "liquidation_price": float(pos.get("liquidationPrice", 0)) if pos.get("liquidationPrice") else None,
                "raw": pos,
            }
        except Exception as e:
            logger.error("get_position failed: %s", e)
            return {"success": False, "error": str(e)}

    async def get_open_orders(self, symbol: str) -> List[dict]:
        """Fetch all open orders for a symbol."""
        ex = await self._ensure_connection()
        try:
            orders = await ex.fetch_open_orders(symbol)
            return [
                {
                    "order_id": o.get("id"),
                    "symbol": o.get("symbol"),
                    "side": o.get("side"),
                    "type": o.get("type"),
                    "price": float(o.get("price", 0)),
                    "amount": float(o.get("amount", 0)),
                    "filled": float(o.get("filled", 0)),
                    "remaining": float(o.get("remaining", 0)),
                    "status": o.get("status"),
                    "reduce_only": o.get("reduceOnly", False),
                }
                for o in orders
            ]
        except Exception as e:
            logger.error("get_open_orders failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        reduce_only: bool = False,
    ) -> dict:
        """
        Place a market order.

        Parameters
        ----------
        symbol : str
            CCXT unified symbol (e.g., BTC/USDT:USDT).
        side : str
            "buy" or "sell".
        amount : float
            Order size in contracts (base coin qty).
        reduce_only : bool, default False
            Close-only order flag.
        """
        ex = await self._ensure_connection()
        try:
            order = await ex.create_market_buy_order(symbol, amount) if side.lower() == "buy" else await ex.create_market_sell_order(symbol, amount)
            # CCXT doesn't expose reduceOnly via simple helpers; we use create_order for full control
            # Re-create with explicit params if reduce_only is needed
            if reduce_only:
                order = await ex.create_order(
                    symbol,
                    "Market",
                    side.capitalize(),
                    amount,
                    None,
                    {"reduceOnly": True},
                )
            logger.info("Market order placed: %s %s %.4f %s", side, symbol, amount, order.get("id"))
            return {
                "success": True,
                "order_id": order.get("id"),
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "type": order.get("type"),
                "amount": float(order.get("amount", 0)),
                "filled": float(order.get("filled", 0)),
                "remaining": float(order.get("remaining", 0)),
                "price": float(order.get("average", 0)) or float(order.get("price", 0)),
                "status": order.get("status"),
                "raw": order,
            }
        except Exception as e:
            logger.error("place_market_order failed: %s", e)
            return {"success": False, "error": str(e)}

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        reduce_only: bool = False,
    ) -> dict:
        """
        Place a limit order.

        Parameters
        ----------
        symbol : str
            CCXT unified symbol.
        side : str
            "buy" or "sell".
        amount : float
            Order size in contracts.
        price : float
            Limit price.
        reduce_only : bool, default False
            Close-only order flag.
        """
        ex = await self._ensure_connection()
        try:
            params = {}
            if reduce_only:
                params["reduceOnly"] = True
            order = await ex.create_limit_order(symbol, side.capitalize(), amount, price, params)
            logger.info("Limit order placed: %s %s %.4f @ %.2f %s", side, symbol, amount, price, order.get("id"))
            return {
                "success": True,
                "order_id": order.get("id"),
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "type": order.get("type"),
                "amount": float(order.get("amount", 0)),
                "filled": float(order.get("filled", 0)),
                "remaining": float(order.get("remaining", 0)),
                "price": float(order.get("price", 0)),
                "status": order.get("status"),
                "raw": order,
            }
        except Exception as e:
            logger.error("place_limit_order failed: %s", e)
            return {"success": False, "error": str(e)}

    async def place_bracket_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: float,
        take_profit_3: float,
    ) -> dict:
        """
        Place an entry order + SL + TP1 + TP2 + TP3 as an OCO-like bracket.

        Bybit v5 does not support native multi-leg OCO for swap, so we:
        1. Place the entry limit order.
        2. Attach TP/SL via Bybit ``tpslMode=Full`` parameters (or place separate orders after fill).
        3. Place separate TP limit orders and a SL stop order.

        Parameters
        ----------
        symbol : str
            CCXT unified symbol.
        side : str
            "buy" (long) or "sell" (short).
        amount : float
            Total position size in contracts.
        entry_price : float
            Desired entry limit price (use 0 for market entry).
        stop_loss : float
            Stop-loss trigger price.
        take_profit_1 : float
            TP1 limit price.
        take_profit_2 : float
            TP2 limit price.
        take_profit_3 : float
            TP3 limit price (or trailing-stop activation level).
        """
        ex = await self._ensure_connection()
        results = {}

        try:
            # 1. Entry order
            is_market = entry_price <= 0
            entry_type = "Market" if is_market else "Limit"
            entry_params = {}

            # Bybit v5 unified margin: attach TP/SL on entry
            # 'tpslMode': 'Full' means TP and SL are both present
            entry_params["tpslMode"] = "Full"
            entry_params["tpOrderType"] = "Limit"
            entry_params["slOrderType"] = "Market"
            # Bybit expects TP/SL as strings in params
            entry_params["takeProfit"] = str(take_profit_1)
            entry_params["stopLoss"] = str(stop_loss)
            # Position idx: 0=one-way, 1=buy hedge, 2=sell hedge
            entry_params["positionIdx"] = 0

            if is_market:
                entry_order = await ex.create_order(
                    symbol, entry_type, side.capitalize(), amount, None, entry_params
                )
            else:
                entry_order = await ex.create_order(
                    symbol, entry_type, side.capitalize(), amount, entry_price, entry_params
                )

            results["entry"] = {
                "success": True,
                "order_id": entry_order.get("id"),
                "type": entry_order.get("type"),
                "amount": float(entry_order.get("amount", 0)),
                "status": entry_order.get("status"),
            }
            logger.info("Bracket entry placed: %s %s %.4f @ %s", side, symbol, amount, entry_price)

            # 2. Place additional TP orders (TP2, TP3) as separate limit orders with reduceOnly
            # Note: reduceOnly is required for TP/SL on existing positions in unified margin
            for tp_label, tp_price in [("tp2", take_profit_2), ("tp3", take_profit_3)]:
                tp_params = {"reduceOnly": True, "positionIdx": 0}
                tp_side = "Sell" if side.lower() == "buy" else "Buy"
                tp_order = await ex.create_order(
                    symbol, "Limit", tp_side, amount, tp_price, tp_params
                )
                results[tp_label] = {
                    "success": True,
                    "order_id": tp_order.get("id"),
                    "price": tp_price,
                }

            # 3. For TP1, we already attached via entry params. But if we want granular sizing,
            #    we can cancel the auto-TP1 and replace with manual limit orders.
            #    For simplicity, we keep the auto-TP1 attached and add TP2/TP3 manually.

            return {"success": True, "bracket": results}

        except Exception as e:
            logger.error("place_bracket_order failed: %s", e)
            # Attempt to cancel any placed orders on partial failure
            await self._cleanup_bracket(results, symbol)
            return {"success": False, "error": str(e), "partial": results}

    async def _cleanup_bracket(self, results: dict, symbol: str):
        """Cancel any orders placed during a failed bracket attempt."""
        for key, val in results.items():
            if isinstance(val, dict) and val.get("success") and val.get("order_id"):
                try:
                    await self.cancel_order(symbol, val["order_id"])
                except Exception as e:
                    logger.warning("Cleanup cancel failed for %s: %s", val["order_id"], e)

    # ------------------------------------------------------------------
    # Order / position management
    # ------------------------------------------------------------------

    async def cancel_order(self, symbol: str, order_id: str) -> dict:
        """Cancel a single order by ID."""
        ex = await self._ensure_connection()
        try:
            result = await ex.cancel_order(order_id, symbol)
            logger.info("Order cancelled: %s %s", symbol, order_id)
            return {"success": True, "order_id": order_id, "raw": result}
        except Exception as e:
            logger.error("cancel_order failed: %s", e)
            return {"success": False, "error": str(e)}

    async def cancel_all_orders(self, symbol: str) -> dict:
        """Cancel all open orders for a symbol."""
        ex = await self._ensure_connection()
        try:
            # CCXT unified cancel_all_orders
            result = await ex.cancel_all_orders(symbol)
            logger.info("All orders cancelled for %s", symbol)
            return {"success": True, "symbol": symbol, "raw": result}
        except Exception as e:
            logger.error("cancel_all_orders failed: %s", e)
            return {"success": False, "error": str(e)}

    async def close_position(self, symbol: str) -> dict:
        """
        Market-close any open position on the symbol.

        Determines the required closing side automatically.
        """
        pos = await self.get_position(symbol)
        if not pos.get("open"):
            return {"success": True, "message": "No open position to close"}

        side = pos.get("side")  # "long" or "short"
        amount = pos.get("contracts", 0)
        close_side = "sell" if side == "long" else "buy"

        return await self.place_market_order(symbol, close_side, amount, reduce_only=True)

    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        """Set leverage for a symbol."""
        ex = await self._ensure_connection()
        try:
            # CCXT setLeverage (if supported) or fallback to manual
            result = await ex.set_leverage(leverage, symbol)
            logger.info("Leverage set: %s %dx", symbol, leverage)
            return {"success": True, "symbol": symbol, "leverage": leverage, "raw": result}
        except Exception as e:
            logger.error("set_leverage failed: %s", e)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def shutdown(self):
        """Close the exchange connection gracefully."""
        if self.exchange is not None:
            await self.exchange.close()
            self.exchange = None
            self._connected = False
            logger.info("ExecutionEngine disconnected.")
