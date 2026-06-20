"""OrderManager: Trade lifecycle management.

Handles the full lifecycle of a trade:
- Pending entry (limit order placed)
- Entry filled (position opened)
- Partial TP1 hit (33% closed)
- Partial TP2 hit (33% closed)
- TP3/SL hit (full close or trailing stop)

Manages:
- Entry order placement and monitoring
- Partial take-profit orders (3 tiers)
- Stop-loss order management
- Trailing stop activation after TP2
- Order status tracking and reconciliation

Example:
    manager = OrderManager(execution_engine)
    await manager.enter_position(
        symbol="BTC/USDT:USDT",
        side="buy",
        entry_price=65000,
        stop_loss=64000,
        take_profit_1=66000,
        take_profit_2=67000,
        take_profit_3=68000,
        size=0.1,
        order_type="limit",
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from .execution_engine import ExecutionEngine

logger = logging.getLogger(__name__)


class TradeStatus(Enum):
    """Trade lifecycle states."""
    PENDING = "pending"           # Entry order placed, not filled
    FILLED = "filled"             # Entry filled, position active
    PARTIAL_TP1 = "partial_tp1"   # 33% closed at TP1
    PARTIAL_TP2 = "partial_tp2"   # 66% closed (33% at TP1 + 33% at TP2)
    TRAILING = "trailing"         # TP2 hit, trailing stop active for remainder
    CLOSED = "closed"             # Fully closed (TP3 or SL)
    CANCELLED = "cancelled"       # Cancelled before fill


@dataclass
class Trade:
    """Represents a single trade from entry to close."""
    id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    status: TradeStatus = TradeStatus.PENDING
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: float = 0.0
    take_profit_3: float = 0.0
    size: float = 0.0
    filled_size: float = 0.0
    remaining_size: float = 0.0
    partial_1_closed: float = 0.0
    partial_2_closed: float = 0.0
    partial_3_closed: float = 0.0
    pnl: float = 0.0
    entry_time: Optional[str] = None
    close_time: Optional[str] = None
    order_type: str = "limit"
    entry_order_id: Optional[str] = None
    sl_order_id: Optional[str] = None
    tp1_order_id: Optional[str] = None
    tp2_order_id: Optional[str] = None
    tp3_order_id: Optional[str] = None
    trailing_active: bool = False
    trailing_stop_price: Optional[float] = None
    trailing_callback: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary for serialization."""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side,
            'status': self.status.value,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit_1': self.take_profit_1,
            'take_profit_2': self.take_profit_2,
            'take_profit_3': self.take_profit_3,
            'size': self.size,
            'filled_size': self.filled_size,
            'remaining_size': self.remaining_size,
            'partial_1_closed': self.partial_1_closed,
            'partial_2_closed': self.partial_2_closed,
            'partial_3_closed': self.partial_3_closed,
            'pnl': self.pnl,
            'entry_time': self.entry_time,
            'close_time': self.close_time,
            'order_type': self.order_type,
            'entry_order_id': self.entry_order_id,
            'sl_order_id': self.sl_order_id,
            'tp1_order_id': self.tp1_order_id,
            'tp2_order_id': self.tp2_order_id,
            'tp3_order_id': self.tp3_order_id,
            'trailing_active': self.trailing_active,
            'trailing_stop_price': self.trailing_stop_price,
            'trailing_callback': self.trailing_callback,
        }


class OrderManager:
    """Manages trade lifecycle from entry to full close.
    
    Parameters
    ----------
    execution_engine : ExecutionEngine
        Initialized execution engine for order placement.
    """

    def __init__(self, execution_engine: ExecutionEngine) -> None:
        self.engine = execution_engine
        self.active_trades: Dict[str, Trade] = {}
        self.trade_history: List[Trade] = []
        
        logger.info("OrderManager initialized")

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
    ) -> Trade:
        """Enter a new position with bracket orders.
        
        Parameters
        ----------
        symbol : str
            Trading pair.
        side : str
            'buy' or 'sell'.
        entry_price : float
            Entry price (for limit orders).
        stop_loss : float
            Stop-loss price.
        take_profit_1 : float
            First take-profit (33% of position).
        take_profit_2 : float
            Second take-profit (33% of position).
        take_profit_3 : float
            Third take-profit (34% of position, trailing stop after TP2).
        size : float
            Total position size in contracts.
        order_type : str, default 'limit'
            'market' or 'limit'.
        
        Returns
        -------
        Trade
            Trade object tracking the position.
        """
        trade_id = f"{symbol}_{side}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        trade = Trade(
            id=trade_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            take_profit_3=take_profit_3,
            size=size,
            remaining_size=size,
            order_type=order_type,
        )
        
        try:
            # Place bracket order (entry + SL + TP1)
            order = await self.engine.place_bracket_order(
                symbol=symbol,
                side=side,
                amount=size,
                entry_price=entry_price if order_type == 'limit' else None,
                stop_loss=stop_loss,
                take_profit=take_profit_1,
                order_type=order_type,
            )
            
            trade.entry_order_id = order.get('id')
            trade.status = TradeStatus.PENDING
            trade.entry_time = datetime.now(timezone.utc).isoformat()
            
            self.active_trades[trade_id] = trade
            
            logger.info(
                f"Trade entered: {trade_id} | {side} {size} {symbol} @ {entry_price} "
                f"SL={stop_loss} TP1={take_profit_1}"
            )
            return trade
            
        except Exception as e:
            logger.error(f"Failed to enter position: {e}")
            trade.status = TradeStatus.CANCELLED
            raise

    # ------------------------------------------------------------------
    # Partial Management
    # ------------------------------------------------------------------

    async def manage_partials(self, symbol: str, trade_dict: Dict[str, Any]) -> None:
        """Manage partial profit-taking and trailing stop for a trade.
        
        This is called periodically to check if TP levels have been hit
        and to manage the trailing stop after TP2.
        
        Parameters
        ----------
        symbol : str
            Trading pair.
        trade_dict : dict
            Trade data from position tracker.
        """
        trade_id = trade_dict.get('id')
        if trade_id not in self.active_trades:
            return
        
        trade = self.active_trades[trade_id]
        current_status = trade.status
        
        # Check if TP1 hit (33% close)
        if current_status == TradeStatus.FILLED and trade.partial_1_closed == 0:
            # Place TP1 limit order for 33% of position
            tp1_size = trade.size * 0.33
            try:
                order = await self.engine.place_limit_order(
                    symbol=trade.symbol,
                    side='sell' if trade.side == 'buy' else 'buy',
                    amount=tp1_size,
                    price=trade.take_profit_1,
                )
                trade.tp1_order_id = order.get('id')
                trade.partial_1_closed = tp1_size
                trade.remaining_size -= tp1_size
                trade.status = TradeStatus.PARTIAL_TP1
                logger.info(f"TP1 order placed: {trade_id} @ {trade.take_profit_1}")
            except Exception as e:
                logger.error(f"TP1 order failed: {e}")
        
        # Check if TP2 hit (another 33% close)
        elif current_status == TradeStatus.PARTIAL_TP1 and trade.partial_2_closed == 0:
            tp2_size = trade.size * 0.33
            try:
                order = await self.engine.place_limit_order(
                    symbol=trade.symbol,
                    side='sell' if trade.side == 'buy' else 'buy',
                    amount=tp2_size,
                    price=trade.take_profit_2,
                )
                trade.tp2_order_id = order.get('id')
                trade.partial_2_closed = tp2_size
                trade.remaining_size -= tp2_size
                trade.status = TradeStatus.PARTIAL_TP2
                
                # Activate trailing stop for remaining 34%
                trade.trailing_active = True
                trade.trailing_stop_price = trade.stop_loss  # Start at original SL
                trade.trailing_callback = abs(trade.entry_price - trade.stop_loss) * 0.5
                
                logger.info(f"TP2 order placed, trailing stop activated: {trade_id}")
            except Exception as e:
                logger.error(f"TP2 order failed: {e}")
        
        # Manage trailing stop
        elif current_status in (TradeStatus.PARTIAL_TP2, TradeStatus.TRAILING):
            await self._update_trailing_stop(trade)

    async def _update_trailing_stop(self, trade: Trade) -> None:
        """Update trailing stop price based on favorable price movement."""
        if not trade.trailing_active:
            return
        
        try:
            # Get current position/price
            positions = await self.engine.get_positions(trade.symbol)
            if not positions:
                return
            
            current_price = float(positions[0].get('markPrice', 0))
            if current_price == 0:
                return
            
            # Calculate new trailing stop
            if trade.side == 'buy':
                # For longs: raise SL as price goes up
                new_stop = current_price - trade.trailing_callback
                if new_stop > (trade.trailing_stop_price or 0):
                    trade.trailing_stop_price = new_stop
                    # Update SL order
                    await self.engine.cancel_order(trade.sl_order_id, trade.symbol)
                    sl_order = await self.engine.place_bracket_order(
                        symbol=trade.symbol,
                        side='sell',
                        amount=trade.remaining_size,
                        stop_loss=new_stop,
                        order_type='market',
                    )
                    trade.sl_order_id = sl_order.get('id')
                    logger.info(f"Trailing stop updated: {trade.id} → {new_stop}")
            else:
                # For shorts: lower SL as price goes down
                new_stop = current_price + trade.trailing_callback
                if new_stop < (trade.trailing_stop_price or float('inf')):
                    trade.trailing_stop_price = new_stop
                    await self.engine.cancel_order(trade.sl_order_id, trade.symbol)
                    sl_order = await self.engine.place_bracket_order(
                        symbol=trade.symbol,
                        side='buy',
                        amount=trade.remaining_size,
                        stop_loss=new_stop,
                        order_type='market',
                    )
                    trade.sl_order_id = sl_order.get('id')
                    logger.info(f"Trailing stop updated: {trade.id} → {new_stop}")
        
        except Exception as e:
            logger.error(f"Trailing stop update failed: {e}")

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    async def close_position(self, trade_id: str, reason: str = "manual") -> None:
        """Close a position immediately (market order).
        
        Parameters
        ----------
        trade_id : str
            Trade ID.
        reason : str, default 'manual'
            Reason for closing.
        """
        if trade_id not in self.active_trades:
            logger.warning(f"Trade not found: {trade_id}")
            return
        
        trade = self.active_trades[trade_id]
        
        try:
            # Cancel all pending orders for this trade
            if trade.tp1_order_id:
                await self.engine.cancel_order(trade.tp1_order_id, trade.symbol)
            if trade.tp2_order_id:
                await self.engine.cancel_order(trade.tp2_order_id, trade.symbol)
            if trade.tp3_order_id:
                await self.engine.cancel_order(trade.tp3_order_id, trade.symbol)
            if trade.sl_order_id:
                await self.engine.cancel_order(trade.sl_order_id, trade.symbol)
            
            # Close remaining position with market order
            if trade.remaining_size > 0:
                close_side = 'sell' if trade.side == 'buy' else 'buy'
                await self.engine.place_market_order(
                    symbol=trade.symbol,
                    side=close_side,
                    amount=trade.remaining_size,
                )
            
            trade.status = TradeStatus.CLOSED
            trade.close_time = datetime.now(timezone.utc).isoformat()
            
            # Calculate PnL (simplified - actual PnL from exchange data)
            trade.pnl = self._calculate_pnl(trade)
            
            # Move to history
            self.trade_history.append(trade)
            del self.active_trades[trade_id]
            
            logger.info(f"Position closed: {trade_id} | reason={reason} | PnL={trade.pnl:.2f}")
            
        except Exception as e:
            logger.error(f"Close position failed: {e}")
            raise

    def _calculate_pnl(self, trade: Trade) -> float:
        """Calculate simplified PnL for a trade.
        
        Note: In production, use actual fill prices from exchange.
        """
        if trade.status != TradeStatus.CLOSED:
            return 0.0
        
        # Simplified calculation using planned prices
        if trade.side == 'buy':
            entry = trade.entry_price
            exit_price = trade.take_profit_3 if trade.partial_3_closed > 0 else trade.stop_loss
        else:
            entry = trade.entry_price
            exit_price = trade.take_profit_3 if trade.partial_3_closed > 0 else trade.stop_loss
        
        price_diff = exit_price - entry if trade.side == 'buy' else entry - exit_price
        return price_diff * trade.size

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_active_trades(self) -> List[Dict[str, Any]]:
        """Get all active trades."""
        return [t.to_dict() for t in self.active_trades.values()]

    def get_trade_history(self) -> List[Dict[str, Any]]:
        """Get closed trade history."""
        return [t.to_dict() for t in self.trade_history]
