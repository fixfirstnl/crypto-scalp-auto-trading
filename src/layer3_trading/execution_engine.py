"""ExecutionEngine: Direct Bybit API v5 order execution.

Handles all order placement, modification, and cancellation for the trading bot.
Supports:
- Market orders (immediate execution)
- Limit orders (with optional post-only)
- Bracket orders (entry + SL + TP)
- OCO orders (stop-limit + take-profit)
- Position queries and leverage setting

Uses CCXT Pro for async, rate-limited API access.

Example:
    engine = ExecutionEngine("api_key", "api_secret", testnet=True)
    order = await engine.place_market_order("BTC/USDT:USDT", "buy", 0.01)
    await engine.close()
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

import ccxt.pro as ccxt_pro

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Async execution engine for Bybit v5 API.
    
    Parameters
    ----------
    api_key : str
        Bybit API key (needs Trade permissions for live orders).
    api_secret : str
        Bybit API secret.
    testnet : bool, default True
        Use Bybit testnet (paper trading).
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.exchange: Optional[ccxt_pro.bybit] = None
        self._initialized = False

        logger.info("ExecutionEngine configured | testnet=%s", testnet)

    async def _ensure_initialized(self) -> None:
        """Lazy-initialize CCXT Pro exchange."""
        if self._initialized:
            return
        
        self.exchange = ccxt_pro.bybit({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # USDT perpetual
            }
        })
        
        if self.testnet:
            self.exchange.set_sandbox_mode(True)
        
        await self.exchange.load_markets()
        self._initialized = True
        logger.info("ExecutionEngine initialized")

    async def close(self) -> None:
        """Close all connections."""
        if self.exchange:
            await self.exchange.close()
            self._initialized = False
            logger.info("ExecutionEngine closed")

    # ------------------------------------------------------------------
    # Order Placement
    # ------------------------------------------------------------------

    async def place_market_order(
        self,
        symbol: str,
        side: str,  # 'buy' or 'sell'
        amount: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Place a market order.
        
        Parameters
        ----------
        symbol : str
            Trading pair (e.g., 'BTC/USDT:USDT').
        side : str
            'buy' or 'sell'.
        amount : float
            Order size in contracts.
        params : dict, optional
            Additional CCXT parameters.
        
        Returns
        -------
        dict
            Order result from CCXT.
        """
        await self._ensure_initialized()
        params = params or {}
        
        try:
            order = await self.exchange.create_market_buy_order(
                symbol, amount, params
            ) if side == 'buy' else await self.exchange.create_market_sell_order(
                symbol, amount, params
            )
            logger.info(f"Market order placed: {side} {amount} {symbol}")
            return order
        except Exception as e:
            logger.error(f"Market order failed: {e}")
            raise

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        post_only: bool = True,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Place a limit order.
        
        Parameters
        ----------
        symbol : str
            Trading pair.
        side : str
            'buy' or 'sell'.
        amount : float
            Order size in contracts.
        price : float
            Limit price.
        post_only : bool, default True
            Ensure the order is maker-only (no taker fees).
        params : dict, optional
            Additional CCXT parameters.
        
        Returns
        -------
        dict
            Order result from CCXT.
        """
        await self._ensure_initialized()
        params = params or {}
        
        if post_only:
            params['timeInForce'] = 'PostOnly'
        
        try:
            order = await self.exchange.create_limit_buy_order(
                symbol, amount, price, params
            ) if side == 'buy' else await self.exchange.create_limit_sell_order(
                symbol, amount, price, params
            )
            logger.info(f"Limit order placed: {side} {amount} @ {price} {symbol}")
            return order
        except Exception as e:
            logger.error(f"Limit order failed: {e}")
            raise

    async def place_bracket_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_type: str = 'limit',
    ) -> Dict[str, Any]:
        """Place a bracket order (entry + SL + TP).
        
        Parameters
        ----------
        symbol : str
            Trading pair.
        side : str
            'buy' or 'sell'.
        amount : float
            Order size.
        entry_price : float, optional
            Entry price (for limit orders). None for market orders.
        stop_loss : float, optional
            Stop-loss price.
        take_profit : float, optional
            Take-profit price.
        order_type : str, default 'limit'
            'market' or 'limit'.
        
        Returns
        -------
        dict
            Order result with linked SL/TP orders.
        """
        await self._ensure_initialized()
        
        params: Dict[str, Any] = {}
        
        if stop_loss:
            params['stopLoss'] = {
                'triggerPrice': stop_loss,
                'type': 'market',
            }
        if take_profit:
            params['takeProfit'] = {
                'triggerPrice': take_profit,
                'type': 'market',
            }
        
        try:
            if order_type == 'market':
                order = await self.place_market_order(symbol, side, amount, params)
            else:
                if entry_price is None:
                    raise ValueError("Entry price required for limit orders")
                order = await self.place_limit_order(symbol, side, amount, entry_price, params=params)
            
            logger.info(f"Bracket order placed: {side} {amount} {symbol} SL={stop_loss} TP={take_profit}")
            return order
        except Exception as e:
            logger.error(f"Bracket order failed: {e}")
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an existing order.
        
        Parameters
        ----------
        order_id : str
            Order ID from exchange.
        symbol : str
            Trading pair.
        
        Returns
        -------
        dict
            Cancellation result.
        """
        await self._ensure_initialized()
        
        try:
            result = await self.exchange.cancel_order(order_id, symbol)
            logger.info(f"Order cancelled: {order_id}")
            return result
        except Exception as e:
            logger.error(f"Cancel order failed: {e}")
            raise

    async def cancel_all_orders(self, symbol: str) -> Dict[str, Any]:
        """Cancel all open orders for a symbol.
        
        Parameters
        ----------
        symbol : str
            Trading pair.
        
        Returns
        -------
        dict
            Cancellation results.
        """
        await self._ensure_initialized()
        
        try:
            result = await self.exchange.cancel_all_orders(symbol)
            logger.info(f"All orders cancelled for {symbol}")
            return result
        except Exception as e:
            logger.error(f"Cancel all orders failed: {e}")
            raise

    # ------------------------------------------------------------------
    # Position Queries
    # ------------------------------------------------------------------

    async def get_positions(self, symbol: Optional[str] = None) -> list[Dict[str, Any]]:
        """Get current positions.
        
        Parameters
        ----------
        symbol : str, optional
            Filter by symbol. If None, returns all positions.
        
        Returns
        -------
        list
            List of position dictionaries.
        """
        await self._ensure_initialized()
        
        try:
            positions = await self.exchange.fetch_positions([symbol] if symbol else None)
            logger.debug(f"Fetched positions: {len(positions)}")
            return positions
        except Exception as e:
            logger.error(f"Get positions failed: {e}")
            raise

    async def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Set leverage for a symbol.
        
        Parameters
        ----------
        symbol : str
            Trading pair.
        leverage : int
            Leverage multiplier (1-100).
        
        Returns
        -------
        dict
            Leverage setting result.
        """
        await self._ensure_initialized()
        
        try:
            result = await self.exchange.set_leverage(leverage, symbol)
            logger.info(f"Leverage set: {symbol} {leverage}x")
            return result
        except Exception as e:
            logger.error(f"Set leverage failed: {e}")
            raise

    # ------------------------------------------------------------------
    # Order Query
    # ------------------------------------------------------------------

    async def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Get status of a specific order.
        
        Parameters
        ----------
        order_id : str
            Order ID.
        symbol : str
            Trading pair.
        
        Returns
        -------
        dict
            Order status.
        """
        await self._ensure_initialized()
        
        try:
            order = await self.exchange.fetch_order(order_id, symbol)
            logger.debug(f"Order status: {order_id} = {order.get('status')}")
            return order
        except Exception as e:
            logger.error(f"Get order status failed: {e}")
            raise

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[Dict[str, Any]]:
        """Get all open orders.
        
        Parameters
        ----------
        symbol : str, optional
            Filter by symbol.
        
        Returns
        -------
        list
            List of open orders.
        """
        await self._ensure_initialized()
        
        try:
            orders = await self.exchange.fetch_open_orders(symbol)
            logger.debug(f"Open orders: {len(orders)}")
            return orders
        except Exception as e:
            logger.error(f"Get open orders failed: {e}")
            raise
