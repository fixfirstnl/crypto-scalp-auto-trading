"""DatabaseManager: SQLite database management for the trading system.

Provides database initialization, schema management, and connection handling
for all trading data persistence.

Tables:
- candles: OHLCV candle data for backtesting and analysis
- trades: Trade execution records
- signals: Trading signal history
- agent_decisions: Agent decision logs
- errors: System error logs

Usage:
    db = DatabaseManager(db_path='data/trading.db')
    db.init_schema()
    db.save_signal({...})
    db.log_error('trading_loop', 'Connection timeout', context='Bybit API')
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class DatabaseManager:
    """SQLite database manager for trading data.
    
    Parameters
    ----------
    db_path : str
        Path to SQLite database file.
    """

    def __init__(self, db_path: str = "data/trading.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None
        
        logger.info("DatabaseManager initialized | db=%s", db_path)

    def _connect(self) -> None:
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        """Initialize database schema with all tables."""
        if not self.conn:
            self._connect()
        
        cursor = self.conn.cursor()
        
        # Candles table (for historical data and backtesting)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                UNIQUE(symbol, timeframe, timestamp)
            )
        """)
        
        # Trades table (detailed trade records)
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
        
        # Signals table (trading signal history)
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
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf ON candles(symbol, timeframe)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_errors_type ON errors(error_type)")
        
        self.conn.commit()
        logger.info("Database schema initialized")

    def save_signal(self, signal: Dict[str, Any]) -> None:
        """Save a trading signal to the database.
        
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
        logger.debug("Signal saved: %s %s", signal.get('symbol'), signal.get('side'))

    def save_trade(self, trade: Dict[str, Any]) -> None:
        """Save a trade to the database.
        
        Parameters
        ----------
        trade : dict
            Trade data with keys: id, symbol, side, entry_price, etc.
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
            ON CONFLICT(id) DO UPDATE SET
                exit_price=excluded.exit_price,
                pnl=excluded.pnl,
                status=excluded.status,
                exit_time=excluded.exit_time
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
        logger.debug("Trade saved: %s", trade.get('id'))

    def log_error(self, error_type: str, message: str, context: str = "") -> None:
        """Log an error to the database.
        
        Parameters
        ----------
        error_type : str
            Type of error.
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

    def save_candles(self, symbol: str, timeframe: str, candles: List[Dict[str, Any]]) -> None:
        """Save OHLCV candles to the database.
        
        Parameters
        ----------
        symbol : str
            Trading pair.
        timeframe : str
            Candle timeframe.
        candles : list
            List of candle dictionaries with keys: timestamp, open, high, low, close, volume.
        """
        if not self.conn:
            self._connect()
        
        cursor = self.conn.cursor()
        for candle in candles:
            cursor.execute("""
                INSERT OR REPLACE INTO candles (symbol, timeframe, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                timeframe,
                candle.get('timestamp'),
                candle.get('open'),
                candle.get('high'),
                candle.get('low'),
                candle.get('close'),
                candle.get('volume'),
            ))
        self.conn.commit()
        logger.debug("Candles saved: %s %s count=%d", symbol, timeframe, len(candles))

    def get_candles(self, symbol: str, timeframe: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Retrieve candles from the database.
        
        Parameters
        ----------
        symbol : str
            Trading pair.
        timeframe : str
            Candle timeframe.
        limit : int, default 1000
            Maximum number of candles to return.
        
        Returns
        -------
        list
            List of candle dictionaries.
        """
        if not self.conn:
            self._connect()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM candles
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (symbol, timeframe, limit))
        
        return [dict(row) for row in cursor.fetchall()]

    def get_signals(self, symbol: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve trading signals.
        
        Parameters
        ----------
        symbol : str, optional
            Filter by symbol.
        limit : int, default 100
            Maximum number of signals.
        
        Returns
        -------
        list
            List of signal dictionaries.
        """
        if not self.conn:
            self._connect()
        
        cursor = self.conn.cursor()
        if symbol:
            cursor.execute("""
                SELECT * FROM signals
                WHERE symbol = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (symbol, limit))
        else:
            cursor.execute("""
                SELECT * FROM signals
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]

    def get_errors(self, error_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve error logs.
        
        Parameters
        ----------
        error_type : str, optional
            Filter by error type.
        limit : int, default 100
            Maximum number of errors.
        
        Returns
        -------
        list
            List of error dictionaries.
        """
        if not self.conn:
            self._connect()
        
        cursor = self.conn.cursor()
        if error_type:
            cursor.execute("""
                SELECT * FROM errors
                WHERE error_type = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (error_type, limit))
        else:
            cursor.execute("""
                SELECT * FROM errors
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]

    def disconnect(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("DatabaseManager disconnected")
