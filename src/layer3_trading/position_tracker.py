"""PositionTracker: SQLite-backed trade logging and PnL analytics.

Provides persistent storage for all trades, signals, and agent decisions.
Tracks performance metrics including win rate, profit factor, max drawdown,
and Sharpe ratio.

Features:
- Trade logging with full lifecycle tracking
- Daily/weekly PnL summaries
- Performance metrics (win rate, profit factor, max drawdown)
- Open position tracking
- Trade history with filtering

Database Schema:
- trades: id, symbol, side, entry_price, exit_price, size, pnl, status, timestamps
- signals: id, symbol, timeframe, side, confidence, strategy, timestamps
- agent_decisions: id, agent_type, symbol, decision, confidence, timestamp
- errors: id, error_type, message, timestamp

Example:
    tracker = PositionTracker(db_path="data/trades.db")
    tracker.init_schema()
    tracker.log_trade({...})
    stats = tracker.get_stats()
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class PositionTracker:
    """SQLite-backed trade and performance tracker.
    
    Parameters
    ----------
    db_path : str
        Path to SQLite database file.
    """

    def __init__(self, db_path: str = "data/trades.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
        
        logger.info("PositionTracker initialized | db=%s", db_path)

    def _connect(self) -> None:
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        """Create database tables if they don't exist."""
        if not self.conn:
            self._connect()
        
        cursor = self.conn.cursor()
        
        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL,
                exit_price REAL,
                stop_loss REAL,
                take_profit_1 REAL,
                take_profit_2 REAL,
                take_profit_3 REAL,
                size REAL NOT NULL,
                pnl REAL DEFAULT 0,
                status TEXT NOT NULL,
                entry_time TEXT,
                exit_time TEXT,
                order_type TEXT,
                strategy TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Signals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                side TEXT NOT NULL,
                confidence REAL,
                strategy TEXT,
                entry_price REAL,
                stop_loss REAL,
                take_profit REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Agent decisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_type TEXT NOT NULL,
                symbol TEXT NOT NULL,
                decision TEXT NOT NULL,
                confidence REAL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Errors table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT NOT NULL,
                message TEXT NOT NULL,
                context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()
        logger.info("Database schema initialized")

    # ------------------------------------------------------------------
    # Trade Operations
    # ------------------------------------------------------------------

    def log_trade(self, trade: Dict[str, Any]) -> None:
        """Log a new trade.
        
        Parameters
        ----------
        trade : dict
            Trade data with keys: id, symbol, side, entry_price, size, status, etc.
        """
        if not self.conn:
            self._connect()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO trades (
                id, symbol, side, entry_price, exit_price, stop_loss,
                take_profit_1, take_profit_2, take_profit_3, size, pnl,
                status, entry_time, exit_time, order_type, strategy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.get('id'),
            trade.get('symbol'),
            trade.get('side'),
            trade.get('entry_price'),
            trade.get('exit_price'),
            trade.get('stop_loss'),
            trade.get('take_profit_1'),
            trade.get('take_profit_2'),
            trade.get('take_profit_3'),
            trade.get('size'),
            trade.get('pnl', 0),
            trade.get('status', 'pending'),
            trade.get('entry_time'),
            trade.get('exit_time'),
            trade.get('order_type'),
            trade.get('strategy', 'ICT/SMC'),
        ))
        self.conn.commit()
        logger.info("Trade logged: %s", trade.get('id'))

    def update_trade(self, trade_id: str, updates: Dict[str, Any]) -> None:
        """Update an existing trade.
        
        Parameters
        ----------
        trade_id : str
            Trade ID.
        updates : dict
            Fields to update.
        """
        if not self.conn:
            self._connect()
        
        allowed_fields = {'exit_price', 'pnl', 'status', 'exit_time', 'exit_price'}
        fields = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not fields:
            return
        
        set_clause = ', '.join(f"{k} = ?" for k in fields.keys())
        values = list(fields.values()) + [trade_id]
        
        cursor = self.conn.cursor()
        cursor.execute(f"UPDATE trades SET {set_clause} WHERE id = ?", values)
        self.conn.commit()
        logger.debug("Trade updated: %s", trade_id)

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        if not self.conn:
            self._connect()
        
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM trades WHERE status IN ('pending', 'filled', 'partial_tp1', 'partial_tp2', 'trailing')"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_trade_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get closed trade history.
        
        Parameters
        ----------
        limit : int, default 100
            Maximum number of trades to return.
        
        Returns
        -------
        list
            List of trade dictionaries.
        """
        if not self.conn:
            self._connect()
        
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM trades WHERE status = 'closed' ORDER BY exit_time DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Signal & Decision Logging
    # ------------------------------------------------------------------

    def save_signal(self, signal: Dict[str, Any]) -> None:
        """Log a trading signal.
        
        Parameters
        ----------
        signal : dict
            Signal data with keys: symbol, timeframe, side, confidence, etc.
        """
        if not self.conn:
            self._connect()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO signals (symbol, timeframe, side, confidence, strategy, entry_price, stop_loss, take_profit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal.get('symbol'),
            signal.get('timeframe'),
            signal.get('side'),
            signal.get('confidence'),
            signal.get('strategy', 'ICT/SMC'),
            signal.get('entry_price'),
            signal.get('stop_loss'),
            signal.get('take_profit'),
        ))
        self.conn.commit()
        logger.debug("Signal logged: %s %s", signal.get('symbol'), signal.get('side'))

    def save_agent_decision(self, decision: Dict[str, Any]) -> None:
        """Log an agent decision.
        
        Parameters
        ----------
        decision : dict
            Decision data with keys: agent_type, symbol, decision, confidence.
        """
        if not self.conn:
            self._connect()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO agent_decisions (agent_type, symbol, decision, confidence, details)
            VALUES (?, ?, ?, ?, ?)
        """, (
            decision.get('agent_type'),
            decision.get('symbol'),
            decision.get('decision'),
            decision.get('confidence'),
            str(decision.get('details', '')),
        ))
        self.conn.commit()
        logger.debug("Agent decision logged: %s", decision.get('agent_type'))

    def log_error(self, error_type: str, message: str, context: str = "") -> None:
        """Log an error.
        
        Parameters
        ----------
        error_type : str
            Type of error (e.g., 'trading_loop', 'api', 'data').
        message : str
            Error message.
        context : str, optional
            Additional context.
        """
        if not self.conn:
            self._connect()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO errors (error_type, message, context)
            VALUES (?, ?, ?)
        """, (error_type, message, context))
        self.conn.commit()
        logger.error("Error logged: %s - %s", error_type, message)

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def get_daily_pnl(self) -> float:
        """Get today's PnL."""
        if not self.conn:
            self._connect()
        
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(pnl), 0) as pnl FROM trades WHERE status = 'closed' AND DATE(exit_time) = ?",
            (today,)
        )
        row = cursor.fetchone()
        return float(row['pnl']) if row else 0.0

    def get_total_pnl(self) -> float:
        """Get total PnL across all trades."""
        if not self.conn:
            self._connect()
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(pnl), 0) as pnl FROM trades WHERE status = 'closed'")
        row = cursor.fetchone()
        return float(row['pnl']) if row else 0.0

    def get_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get performance statistics.
        
        Parameters
        ----------
        days : int, default 30
            Lookback period in days.
        
        Returns
        -------
        dict
            Performance metrics.
        """
        if not self.conn:
            self._connect()
        
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
        cursor = self.conn.cursor()
        
        # All closed trades in period
        cursor.execute(
            "SELECT * FROM trades WHERE status = 'closed' AND DATE(exit_time) >= ?",
            (since,)
        )
        trades = [dict(row) for row in cursor.fetchall()]
        
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'profit_factor': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'daily_pnl': self.get_daily_pnl(),
            }
        
        pnls = [t['pnl'] for t in trades if t['pnl'] is not None]
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p < 0]
        
        total_pnl = sum(pnls)
        avg_pnl = total_pnl / len(pnls) if pnls else 0
        win_rate = len(winning) / len(pnls) * 100 if pnls else 0
        
        gross_profit = sum(winning) if winning else 0
        gross_loss = abs(sum(losing)) if losing else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
        
        # Max drawdown calculation
        cumulative = 0
        peak = 0
        max_dd = 0
        for pnl in pnls:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        
        # Sharpe ratio (simplified, using daily returns)
        if len(pnls) > 1:
            returns = pd.Series(pnls)
            sharpe = (returns.mean() / returns.std()) * (252 ** 0.5) if returns.std() > 0 else 0
        else:
            sharpe = 0
        
        return {
            'total_trades': len(trades),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 4),
            'avg_pnl': round(avg_pnl, 4),
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 'inf',
            'max_drawdown': round(max_dd, 4),
            'sharpe_ratio': round(sharpe, 2),
            'daily_pnl': self.get_daily_pnl(),
        }

    def get_open_position_count(self) -> int:
        """Get number of open positions."""
        return len(self.get_open_positions())

    def disconnect(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("PositionTracker disconnected")
