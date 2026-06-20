"""Layer 3: Trading Execution Layer

This module handles the live trading execution: order placement, position tracking,
risk management, and trade lifecycle management. All operations are designed for
high-frequency, low-latency scalping on Bybit perpetual futures.

Components:
- ExecutionEngine: Direct Bybit API v5 order execution (market, limit, bracket)
- OrderManager: Trade lifecycle management (pending → filled → partial → closed)
- PositionTracker: SQLite-backed trade logging, PnL analytics, and performance metrics
- RiskManager: Kill switches, risk gates, and prop-firm discipline enforcement

Usage:
    from src.layer3_trading import ExecutionEngine, OrderManager, PositionTracker, RiskManager
    
    engine = ExecutionEngine(api_key, api_secret, testnet=True)
    manager = OrderManager(engine)
    tracker = PositionTracker(db_path="data/trades.db")
    risk = RiskManager(account_balance=1000.0, risk_per_trade=0.005)
"""

from .execution_engine import ExecutionEngine
from .order_manager import OrderManager
from .position_tracker import PositionTracker
from .risk_manager import RiskManager

__all__ = ['ExecutionEngine', 'OrderManager', 'PositionTracker', 'RiskManager']
