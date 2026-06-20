"""
Historical Loader
==================
Backfill historical OHLCV data from Bybit and persist to CSV.

Uses CCXT Pro ``fetch_ohlcv`` with pagination to download large
historical windows. Respects rate limits via CCXT's built-in throttling.

Output files are stored in ``data/`` as CSV with columns:
    timestamp, open, high, low, close, volume

Dependencies
------------
- pandas
- asyncio

Example
-------
    client = BybitDataClient(api_key, api_secret, testnet=True)
    loader = HistoricalLoader(client)
    candles = await loader.backfill("BTC/USDT:USDT", "1m", days=30)
    loader.save_to_csv("BTCUSDT", "1m", candles)
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pandas as pd

from .bybit_client import BybitDataClient

logger = logging.getLogger(__name__)


class HistoricalLoader:
    """
    Historical OHLCV backfill and CSV persistence.

    Parameters
    ----------
    bybit_client : BybitDataClient
        Initialized CCXT Pro wrapper.
    data_dir : str, default "data"
        Directory to save/load CSV files. Created automatically if missing.
    """

    def __init__(
        self,
        bybit_client: BybitDataClient,
        data_dir: str = "data",
    ) -> None:
        self.client: BybitDataClient = bybit_client
        self.data_dir: str = data_dir

        os.makedirs(self.data_dir, exist_ok=True)
        logger.info(
            "HistoricalLoader initialized | data_dir=%s", os.path.abspath(self.data_dir)
        )

    # ------------------------------------------------------------------
    # Backfill helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _timeframe_to_ms(timeframe: str) -> int:
        """Convert CCXT timeframe string to milliseconds."""
        multipliers = {
            "m": 60_000,
            "h": 3_600_000,
            "d": 86_400_000,
            "w": 604_800_000,
        }
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        return value * multipliers[unit]

    # ------------------------------------------------------------------
    # Single backfill
    # ------------------------------------------------------------------

    async def backfill(
        self,
        symbol: str,
        timeframe: str,
        days: int = 30,
        total_limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Download historical OHLCV candles for a symbol+timeframe.

        Parameters
        ----------
        symbol : str
            E.g. ``"BTC/USDT:USDT"``.
        timeframe : str
            E.g. ``"1m", "5m", "15m", "1h"``.
        days : int, default 30
            How many days of history to fetch.
        total_limit : int, optional
            Override the total number of candles to fetch. If ``None``,
            computed from ``days`` and ``timeframe``.

        Returns
        -------
        pd.DataFrame
            Columns: ``timestamp, open, high, low, close, volume``.
            Sorted ascending by timestamp. Empty if no data.
        """
        # Compute total limit from days if not provided
        if total_limit is None:
            tf_ms = self._timeframe_to_ms(timeframe)
            total_limit = int((days * 86_400_000) / tf_ms) + 1

        # Compute since (start timestamp)
        since_dt = datetime.now(timezone.utc) - timedelta(days=days)
        since_ms = int(since_dt.timestamp() * 1000)

        logger.info(
            "Backfill start | symbol=%s tf=%s days=%d total_limit=%d since=%s",
            symbol,
            timeframe,
            days,
            total_limit,
            since_dt.isoformat(),
        )

        all_candles: List[List[float]] = []
        page_size = 200
        current_since = since_ms
        pages = 0

        while len(all_candles) < total_limit:
            pages += 1
            try:
                page = await self.client.fetch_ohlcv(
                    symbol,
                    timeframe,
                    limit=min(page_size, total_limit - len(all_candles)),
                    since=current_since,
                )
            except Exception as exc:
                logger.error("Backfill page %d failed: %s", pages, exc)
                break

            if not page:
                logger.info("Backfill: no more data at page %d", pages)
                break

            # Filter out candles before since_ms (exchange may return earlier data)
            valid = [c for c in page if c[0] >= since_ms]
            if not valid:
                break

            all_candles.extend(valid)

            # Advance since
            last_ts = int(valid[-1][0])
            current_since = last_ts + 1

            if len(page) < page_size:
                break

            # Throttle between pages (CCXT rate limiter handles per-request,
            # but we add a small async sleep to be extra polite)
            await asyncio.sleep(0.15)

        logger.info(
            "Backfill complete | symbol=%s tf=%s pages=%d candles=%d",
            symbol,
            timeframe,
            pages,
            len(all_candles),
        )

        return self._candles_to_df(all_candles)

    # ------------------------------------------------------------------
    # Batch backfill
    # ------------------------------------------------------------------

    async def backfill_all(
        self,
        symbols: List[str],
        timeframes: List[str],
        days: int = 30,
    ) -> Dict[str, pd.DataFrame]:
        """
        Batch backfill for multiple symbols and timeframes.

        Runs sequentially (not concurrently) to avoid rate-limit issues.

        Parameters
        ----------
        symbols : List[str]
        timeframes : List[str]
        days : int, default 30

        Returns
        -------
        Dict[str, pd.DataFrame]
            Keys are ``"symbol|timeframe"``; values are DataFrames.
        """
        results: Dict[str, pd.DataFrame] = {}

        for symbol in symbols:
            for tf in timeframes:
                key = f"{symbol}|{tf}"
                df = await self.backfill(symbol, tf, days=days)
                results[key] = df
                if not df.empty:
                    self.save_to_csv(symbol, tf, df)
                # Small delay between symbols to be polite
                await asyncio.sleep(0.5)

        return results

    # ------------------------------------------------------------------
    # CSV persistence
    # ------------------------------------------------------------------

    def _filename(self, symbol: str, timeframe: str) -> str:
        """Generate CSV file path."""
        # Normalize symbol for filename (remove slashes, colons)
        safe_symbol = symbol.replace("/", "_").replace(":", "_")
        return os.path.join(self.data_dir, f"{safe_symbol}_{timeframe}.csv")

    def save_to_csv(
        self, symbol: str, timeframe: str, candles: pd.DataFrame
    ) -> None:
        """
        Save candles to CSV.

        Parameters
        ----------
        symbol : str
        timeframe : str
        candles : pd.DataFrame
            Must contain columns ``timestamp, open, high, low, close, volume``.
        """
        if candles.empty:
            logger.warning("save_to_csv called with empty DataFrame | %s %s", symbol, timeframe)
            return

        filepath = self._filename(symbol, timeframe)
        try:
            candles.to_csv(filepath, index=False)
            logger.info(
                "Saved CSV | %s rows=%d path=%s",
                filepath,
                len(candles),
                os.path.abspath(filepath),
            )
        except Exception as exc:
            logger.error("Failed to save CSV %s: %s", filepath, exc)

    def load_from_csv(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """
        Load candles from CSV.

        Returns
        -------
        pd.DataFrame
            Empty DataFrame if file does not exist.
        """
        filepath = self._filename(symbol, timeframe)
        if not os.path.exists(filepath):
            logger.warning("CSV not found | %s", filepath)
            return pd.DataFrame()

        try:
            df = pd.read_csv(filepath)
            # Convert timestamp to int if it was stored as string
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
            logger.info("Loaded CSV | %s rows=%d", filepath, len(df))
            return df
        except Exception as exc:
            logger.error("Failed to load CSV %s: %s", filepath, exc)
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _candles_to_df(candles: List[List[float]]) -> pd.DataFrame:
        """
        Convert CCXT OHLCV list to pandas DataFrame.

        Parameters
        ----------
        candles : List[List[float]]
            [[timestamp, open, high, low, close, volume], ...]

        Returns
        -------
        pd.DataFrame
            Columns: ``timestamp, open, high, low, close, volume``.
        """
        if not candles:
            return pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

        df = pd.DataFrame(
            candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"])
        df = df.reset_index(drop=True)
        return df
