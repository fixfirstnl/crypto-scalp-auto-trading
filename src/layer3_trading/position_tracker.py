"""
position_tracker.py — SQLite-backed position state, PnL tracking, and trade analytics.

Tracks every trade from open → update → close, storing realized/unrealized PnL,
R-multiples, and exit reasons. Provides daily/weekly statistics for the risk layer.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class PositionTracker:
    """
    Track open and closed trades via local SQLite.

    Parameters
    ----------
    db_path : str
        Path to SQLite database file (default: ``trades.db`` in CWD).
    """

    def __init__(self, db_path: str = "trades.db"):
        self.db_path = Path(db_path)
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        """Create tables if they do not exist."""
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id    TEXT NOT NULL UNIQUE,
                    symbol      TEXT NOT NULL,
                    side        TEXT NOT NULL CHECK(side IN ('long', 'short')),
                    entry_price REAL NOT NULL,
                    exit_price  REAL,
                    size        REAL NOT NULL,
                    stop_loss   REAL NOT NULL,
                    take_profit_1 REAL,
                    take_profit_2 REAL,
                    take_profit_3 REAL,
                    pnl         REAL,
                    r_multiple  REAL,
                    exit_reason TEXT CHECK(exit_reason IN ('tp1', 'tp2', 'tp3', 'sl', 'breakeven', 'trailing_stop', 'manual', 'time_exit', 'emergency')),
                    opened_at   TEXT NOT NULL,
                    closed_at   TEXT,
                    updated_at  TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_trades_closed_at ON trades(closed_at)
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Trade lifecycle
    # ------------------------------------------------------------------

    def open_position(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        size: float,
        stop_loss: float,
        take_profits: List[float],
    ) -> dict:
        """
        Record a new open position.

        Parameters
        ----------
        trade_id : str
            Unique identifier for the trade (e.g., UUID).
        symbol : str
            CCXT unified symbol.
        side : str
            "long" or "short".
        entry_price : float
            Average fill price.
        size : float
            Position size in contracts.
        stop_loss : float
            Initial stop-loss price.
        take_profits : List[float]
            Up to 3 take-profit levels. Pad with ``None`` if fewer.

        Returns
        -------
        dict
            Trade record summary.
        """
        now = datetime.now(timezone.utc).isoformat()
        tps = (take_profits + [None, None, None])[:3]
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO trades
                (trade_id, symbol, side, entry_price, size, stop_loss,
                 take_profit_1, take_profit_2, take_profit_3,
                 opened_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (trade_id, symbol, side, entry_price, size, stop_loss,
                 tps[0], tps[1], tps[2], now, now),
            )
            conn.commit()
        logger.info("Position opened: %s %s %.4f @ %.2f", side, symbol, size, entry_price)
        return self._get_trade(trade_id)

    def update_position(
        self,
        trade_id: str,
        current_price: float,
    ) -> dict:
        """
        Update unrealized PnL and distance metrics for an open trade.

        Parameters
        ----------
        trade_id : str
            Trade identifier.
        current_price : float
            Current mark price.

        Returns
        -------
        dict
            Updated trade record with ``unrealized_pnl`` and ``distance_to_sl``.
        """
        trade = self._get_trade(trade_id)
        if not trade or trade.get("closed_at"):
            return {"error": "Trade not found or already closed"}

        entry = trade["entry_price"]
        size = trade["size"]
        side = trade["side"]
        sl = trade["stop_loss"]

        # Unrealized PnL
        if side == "long":
            unrealized_pnl = (current_price - entry) * size
            distance_to_sl = current_price - sl
        else:
            unrealized_pnl = (entry - current_price) * size
            distance_to_sl = sl - current_price

        r_multiple = unrealized_pnl / (abs(entry - sl) * size) if entry != sl else 0.0

        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE trades SET updated_at = ? WHERE trade_id = ?",
                (now, trade_id),
            )
            conn.commit()

        return {
            "trade_id": trade_id,
            "symbol": trade["symbol"],
            "side": side,
            "entry_price": entry,
            "current_price": current_price,
            "size": size,
            "unrealized_pnl": round(unrealized_pnl, 4),
            "distance_to_sl": round(distance_to_sl, 4),
            "r_multiple": round(r_multiple, 4),
        }

    def close_position(
        self,
        trade_id: str,
        exit_price: float,
        exit_reason: str,
    ) -> dict:
        """
        Close a trade and record realized PnL + R-multiple.

        Parameters
        ----------
        trade_id : str
            Trade identifier.
        exit_price : float
            Average exit fill price.
        exit_reason : str
            One of: tp1, tp2, tp3, sl, breakeven, trailing_stop, manual, time_exit, emergency.

        Returns
        -------
        dict
            Closed trade summary.
        """
        trade = self._get_trade(trade_id)
        if not trade:
            return {"error": "Trade not found"}
        if trade.get("closed_at"):
            return {"error": "Trade already closed"}

        entry = trade["entry_price"]
        size = trade["size"]
        side = trade["side"]
        sl = trade["stop_loss"]

        if side == "long":
            pnl = (exit_price - entry) * size
        else:
            pnl = (entry - exit_price) * size

        risk_amount = abs(entry - sl) * size
        r_multiple = pnl / risk_amount if risk_amount else 0.0

        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE trades
                SET exit_price = ?, pnl = ?, r_multiple = ?, exit_reason = ?, closed_at = ?, updated_at = ?
                WHERE trade_id = ?
                """,
                (exit_price, round(pnl, 4), round(r_multiple, 4), exit_reason, now, now, trade_id),
            )
            conn.commit()

        logger.info("Position closed: %s %s PnL=%.4f R=%.2f reason=%s",
                    trade_id, trade["symbol"], pnl, r_multiple, exit_reason)
        return self._get_trade(trade_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def _get_trade(self, trade_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM trades WHERE trade_id = ?", (trade_id,)
            ).fetchone()
            if row is None:
                return None
            return dict(row)

    def get_open_positions(self) -> List[dict]:
        """Return all trades without a ``closed_at`` timestamp."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM trades WHERE closed_at IS NULL ORDER BY opened_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_trade_history(self, limit: int = 100) -> List[dict]:
        """Return most recent closed trades."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM trades WHERE closed_at IS NOT NULL ORDER BY closed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_daily_pnl(self) -> float:
        """Sum realized PnL for today (UTC)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(pnl), 0) as pnl FROM trades WHERE DATE(closed_at) = ?",
                (today,),
            ).fetchone()
        return float(row["pnl"]) if row else 0.0

    def get_total_pnl(self) -> float:
        """Sum all realized PnL."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(pnl), 0) as pnl FROM trades WHERE closed_at IS NOT NULL"
            ).fetchone()
        return float(row["pnl"]) if row else 0.0

    def get_win_rate(self, days: int = 30) -> float:
        """
        Calculate win rate over the last N days.

        Returns
        -------
        float
            Win rate in [0, 1]. Returns 0.0 if no trades.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins
                FROM trades
                WHERE closed_at IS NOT NULL AND DATE(closed_at) >= ?
                """,
                (cutoff,),
            ).fetchone()
        total = row["total"] or 0
        wins = row["wins"] or 0
        return round(wins / total, 4) if total > 0 else 0.0

    def get_avg_r(self, days: int = 30) -> float:
        """
        Average R-multiple over the last N days.

        Returns
        -------
        float
            Mean R-multiple. Returns 0.0 if no trades.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(AVG(r_multiple), 0) as avg_r
                FROM trades
                WHERE closed_at IS NOT NULL AND DATE(closed_at) >= ?
                """,
                (cutoff,),
            ).fetchone()
        return round(float(row["avg_r"]), 4) if row and row["avg_r"] else 0.0

    def get_max_drawdown(self, days: int = 30) -> float:
        """
        Maximum drawdown (peak-to-trough) over the last N days.

        Returns
        -------
        float
            Max drawdown as a positive fraction (e.g., 0.05 = 5%).
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT pnl FROM trades
                WHERE closed_at IS NOT NULL AND DATE(closed_at) >= ?
                ORDER BY closed_at ASC
                """,
                (cutoff,),
            ).fetchall()

        if not rows:
            return 0.0

        cum = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in rows:
            cum += r["pnl"]
            if cum > peak:
                peak = cum
            dd = peak - cum
            if dd > max_dd:
                max_dd = dd

        # Normalize: if we don't know starting balance, return absolute drawdown
        return round(max_dd, 4)

    def get_stats(self, days: int = 30) -> dict:
        """Convenience wrapper for all key statistics."""
        return {
            "daily_pnl": self.get_daily_pnl(),
            "total_pnl": self.get_total_pnl(),
            "win_rate": self.get_win_rate(days),
            "avg_r": self.get_avg_r(days),
            "max_drawdown": self.get_max_drawdown(days),
            "open_positions": len(self.get_open_positions()),
        }
