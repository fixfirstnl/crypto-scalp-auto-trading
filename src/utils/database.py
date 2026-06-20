"""SQLite database manager for trading data (PostgreSQL optional for production)."""

import logging
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Any

import pandas as pd

logger = logging.getLogger(__name__)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS candles (
    time TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    PRIMARY KEY (time, symbol, timeframe)
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL DEFAULT (datetime('now')),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    stop_loss REAL,
    take_profit REAL,
    size REAL NOT NULL,
    pnl REAL,
    pnl_pct REAL,
    status TEXT NOT NULL DEFAULT 'open',
    strategy TEXT,
    confidence INTEGER,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades(symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL DEFAULT (datetime('now')),
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    side TEXT NOT NULL,
    confidence INTEGER NOT NULL,
    strategy TEXT,
    entry_price REAL,
    stop_loss REAL,
    take_profit REAL,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol_time ON signals(symbol, time DESC);

CREATE TABLE IF NOT EXISTS agent_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL DEFAULT (datetime('now')),
    agent_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    decision TEXT NOT NULL,
    confidence INTEGER NOT NULL,
    reasoning TEXT,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_time ON agent_decisions(time DESC);

CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL DEFAULT (datetime('now')),
    component TEXT NOT NULL,
    error_type TEXT NOT NULL,
    message TEXT NOT NULL,
    stack_trace TEXT,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_errors_time ON errors(time DESC);
"""


class DatabaseManager:
    """SQLite database manager for trading data.

    Lightweight, zero-config alternative to PostgreSQL/TimescaleDB.
    For production at scale, upgrade to PostgreSQL by swapping this class.
    """

    def __init__(self, db_path: str = "data/trading.db") -> None:
        """Initialize the database manager.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Create the SQLite connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"SQLite connected: {self.db_path}")

    def disconnect(self) -> None:
        """Close the SQLite connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("SQLite connection closed")

    def init_schema(self) -> None:
        """Initialize database schema."""
        self.connect()
        c = self.conn.cursor()
        c.executescript(SCHEMA_SQL)
        self.conn.commit()
        logger.info("Database schema initialized")

    def save_candles(
        self,
        symbol: str,
        timeframe: str,
        candles: pd.DataFrame,
    ) -> None:
        """Insert or update candles.

        Args:
            symbol: Trading pair symbol (e.g., BTC/USDT:USDT).
            timeframe: Candle timeframe (e.g., 1m, 5m, 1h).
            candles: DataFrame with columns: open, high, low, close, volume.
        """
        if candles.empty:
            return
        self.connect()
        c = self.conn.cursor()
        for ts, row in candles.iterrows():
            c.execute(
                """INSERT OR REPLACE INTO candles (time, symbol, timeframe, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(ts), symbol, timeframe,
                 float(row.get("open", 0)), float(row.get("high", 0)),
                 float(row.get("low", 0)), float(row.get("close", 0)),
                 float(row.get("volume", 0)))
            )
        self.conn.commit()
        logger.debug(f"Saved {len(candles)} candles for {symbol} {timeframe}")

    def save_trade(self, trade: Dict[str, Any]) -> None:
        """Insert a trade record."""
        self.connect()
        c = self.conn.cursor()
        c.execute(
            """INSERT INTO trades (symbol, side, entry_price, exit_price, stop_loss,
                   take_profit, size, pnl, pnl_pct, status, strategy, confidence, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (trade.get("symbol"), trade.get("side"), trade.get("entry_price"),
             trade.get("exit_price"), trade.get("stop_loss"), trade.get("take_profit"),
             trade.get("size"), trade.get("pnl"), trade.get("pnl_pct"),
             trade.get("status", "open"), trade.get("strategy"),
             trade.get("confidence"), str(trade.get("metadata")) if trade.get("metadata") else None)
        )
        self.conn.commit()
        logger.info(f"Trade saved: {trade.get('symbol')} {trade.get('side')}")

    def save_signal(self, signal: Dict[str, Any]) -> None:
        """Insert a trading signal record."""
        self.connect()
        c = self.conn.cursor()
        c.execute(
            """INSERT INTO signals (symbol, timeframe, side, confidence, strategy,
                   entry_price, stop_loss, take_profit, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (signal.get("symbol"), signal.get("timeframe"), signal.get("side"),
             signal.get("confidence"), signal.get("strategy"), signal.get("entry_price"),
             signal.get("stop_loss"), signal.get("take_profit"),
             str(signal.get("metadata")) if signal.get("metadata") else None)
        )
        self.conn.commit()
        logger.info(f"Signal saved: {signal.get('symbol')} {signal.get('side')}")

    def get_trade_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve recent trade history."""
        self.connect()
        c = self.conn.cursor()
        if symbol:
            rows = c.execute(
                "SELECT * FROM trades WHERE symbol = ? ORDER BY time DESC LIMIT ?",
                (symbol, limit)
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM trades ORDER BY time DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_performance_stats(self, days: int = 30) -> Dict[str, Any]:
        """Calculate performance statistics over the last N days."""
        self.connect()
        c = self.conn.cursor()
        row = c.execute(
            f"""SELECT
                COALESCE(SUM(pnl), 0) as total_pnl,
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(AVG(CASE WHEN pnl > 0 THEN pnl END), 0) as avg_profit,
                COALESCE(AVG(CASE WHEN pnl <= 0 THEN pnl END), 0) as avg_loss
            FROM trades
            WHERE time >= datetime('now', '-{days} days') AND status = 'closed'"""
        ).fetchone()
        stats = dict(row) if row else {}
        total = stats.get("total_trades", 0)
        wins = stats.get("wins", 0)
        stats["win_rate"] = (wins / total * 100) if total > 0 else 0
        return stats

    def log_error(
        self,
        component: str,
        error_type: str,
        message: str,
        stack_trace: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Log an error to the database."""
        self.connect()
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO errors (component, error_type, message, stack_trace, metadata) VALUES (?, ?, ?, ?, ?)",
            (component, error_type, message, stack_trace,
             str(metadata) if metadata else None)
        )
        self.conn.commit()
