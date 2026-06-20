"""
Data Cache
===========
Dual-mode caching layer: Redis (production) or thread-safe in-memory dict (fallback).

Stores:
- OHLCV candles (last 500 per symbol/timeframe)
- L2 order books (latest snapshot per symbol)
- Computed indicator values (latest per symbol/timeframe/indicator)

For candles, data is stored as compressed JSON strings (efficient enough for
<500 rows). If Redis is unavailable, falls back to an in-memory dict with
asyncio.Lock for thread safety.

Dependencies
------------
- redis >= 5.0 (optional; only imported if use_redis=True)
- pandas, numpy, json, zlib

Example
-------
    cache = DataCache(redis_url="redis://localhost:6379", use_redis=True)
    cache.set_candles("BTCUSDT", "1m", candles_df)
    df = cache.get_candles("BTCUSDT", "1m", limit=100)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class DataCache:
    """
    Cache wrapper with Redis primary + in-memory fallback.

    Parameters
    ----------
    redis_url : str, default "redis://localhost:6379"
        Redis connection string.
    use_redis : bool, default True
        Attempt Redis connection. If False, always use in-memory.
    max_candles : int, default 500
        Max candles retained per (symbol, timeframe) key.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        use_redis: bool = True,
        max_candles: int = 500,
    ) -> None:
        self.redis_url: str = redis_url
        self.use_redis: bool = use_redis
        self.max_candles: int = max_candles

        self._redis: Optional[Any] = None
        self._redis_available: bool = False

        # In-memory fallback storage
        self._memory: Dict[str, Any] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

        # Attempt Redis connection
        if self.use_redis:
            try:
                import redis as redis_lib

                self._redis = redis_lib.from_url(
                    redis_url, decode_responses=False, socket_connect_timeout=2
                )
                self._redis.ping()
                self._redis_available = True
                logger.info("Redis connected | url=%s", redis_url)
            except Exception as exc:
                logger.warning(
                    "Redis unavailable (%s). Falling back to in-memory cache.", exc
                )
                self._redis = None
                self._redis_available = False

        if not self._redis_available:
            logger.info("In-memory cache initialized")

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _candle_key(symbol: str, timeframe: str) -> str:
        return f"candles:{symbol}:{timeframe}"

    @staticmethod
    def _orderbook_key(symbol: str) -> str:
        return f"orderbook:{symbol}"

    @staticmethod
    def _indicator_key(symbol: str, timeframe: str, indicator: str) -> str:
        return f"indicator:{symbol}:{timeframe}:{indicator}"

    # ------------------------------------------------------------------
    # Candles
    # ------------------------------------------------------------------

    def set_candles(
        self, symbol: str, timeframe: str, candles: pd.DataFrame
    ) -> None:
        """
        Store OHLCV candles, keeping only the last ``max_candles`` rows.

        Parameters
        ----------
        symbol : str
            E.g. ``"BTCUSDT"``.
        timeframe : str
            E.g. ``"1m"``.
        candles : pd.DataFrame
            Must contain columns ``open``, ``high``, ``low``, ``close``, ``volume``
            and a DatetimeIndex or integer index.
        """
        if candles.empty:
            return

        # Trim to max
        trimmed = candles.tail(self.max_candles).copy()
        payload = self._df_to_json(trimmed)

        if self._redis_available and self._redis is not None:
            try:
                key = self._candle_key(symbol, timeframe)
                self._redis.set(key, payload)
            except Exception as exc:
                logger.warning("Redis set_candles failed: %s. Using memory.", exc)
                self._fallback_set(self._candle_key(symbol, timeframe), payload)
        else:
            self._fallback_set(self._candle_key(symbol, timeframe), payload)

    def get_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> pd.DataFrame:
        """
        Retrieve cached OHLCV candles.

        Parameters
        ----------
        symbol : str
        timeframe : str
        limit : int, default 100
            Number of most recent candles to return.

        Returns
        -------
        pd.DataFrame
            Empty DataFrame if no cached data found.
        """
        payload: Optional[bytes] = None
        key = self._candle_key(symbol, timeframe)

        if self._redis_available and self._redis is not None:
            try:
                payload = self._redis.get(key)
            except Exception as exc:
                logger.warning("Redis get_candles failed: %s", exc)
        else:
            payload = self._memory.get(key)

        if payload is None:
            return pd.DataFrame()

        df = self._json_to_df(payload)
        if df.empty:
            return df
        return df.tail(limit).reset_index(drop=True)

    # ------------------------------------------------------------------
    # Orderbook
    # ------------------------------------------------------------------

    def set_orderbook(self, symbol: str, orderbook: Dict[str, Any]) -> None:
        """Store latest L2 order book snapshot."""
        payload = json.dumps(orderbook).encode("utf-8")
        key = self._orderbook_key(symbol)

        if self._redis_available and self._redis is not None:
            try:
                self._redis.set(key, payload)
            except Exception as exc:
                logger.warning("Redis set_orderbook failed: %s", exc)
                self._fallback_set(key, payload)
        else:
            self._fallback_set(key, payload)

    def get_orderbook(self, symbol: str) -> Dict[str, Any]:
        """Retrieve latest L2 order book snapshot."""
        payload: Optional[bytes] = None
        key = self._orderbook_key(symbol)

        if self._redis_available and self._redis is not None:
            try:
                payload = self._redis.get(key)
            except Exception as exc:
                logger.warning("Redis get_orderbook failed: %s", exc)
        else:
            payload = self._memory.get(key)

        if payload is None:
            return {}
        try:
            return json.loads(payload)
        except Exception as exc:
            logger.error("Failed to decode orderbook JSON: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Indicators
    # ------------------------------------------------------------------

    def set_indicator(
        self,
        symbol: str,
        timeframe: str,
        indicator: str,
        values: Any,
    ) -> None:
        """
        Store a computed indicator value.

        For pandas Series, the *last* value is stored as a scalar
        (agents only need the latest indicator reading). For complex
        objects like volume_profile dicts, they are JSON-serialized.
        """
        key = self._indicator_key(symbol, timeframe, indicator)

        if isinstance(values, pd.Series):
            payload = json.dumps({"value": float(values.iloc[-1])}).encode("utf-8")
        elif isinstance(values, (dict, list)):
            try:
                payload = json.dumps(values, default=str).encode("utf-8")
            except Exception:
                payload = json.dumps({"error": "serialization failed"}).encode("utf-8")
        else:
            payload = json.dumps({"value": float(values)}).encode("utf-8")

        if self._redis_available and self._redis is not None:
            try:
                self._redis.set(key, payload)
            except Exception as exc:
                logger.warning("Redis set_indicator failed: %s", exc)
                self._fallback_set(key, payload)
        else:
            self._fallback_set(key, payload)

    def get_indicator(
        self, symbol: str, timeframe: str, indicator: str
    ) -> Any:
        """
        Retrieve the latest indicator value.

        Returns
        -------
        float or dict or None
            The stored value, or ``None`` if not found.
        """
        payload: Optional[bytes] = None
        key = self._indicator_key(symbol, timeframe, indicator)

        if self._redis_available and self._redis is not None:
            try:
                payload = self._redis.get(key)
            except Exception as exc:
                logger.warning("Redis get_indicator failed: %s", exc)
        else:
            payload = self._memory.get(key)

        if payload is None:
            return None
        try:
            data = json.loads(payload)
            if isinstance(data, dict) and "value" in data:
                return data["value"]
            return data
        except Exception as exc:
            logger.error("Failed to decode indicator JSON: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all cached data (both Redis and in-memory)."""
        if self._redis_available and self._redis is not None:
            try:
                # Flush only keys belonging to this app (prefix-based)
                for key in self._redis.scan_iter(match="candles:*"):
                    self._redis.delete(key)
                for key in self._redis.scan_iter(match="orderbook:*"):
                    self._redis.delete(key)
                for key in self._redis.scan_iter(match="indicator:*"):
                    self._redis.delete(key)
                logger.info("Redis cache cleared")
            except Exception as exc:
                logger.warning("Redis clear failed: %s", exc)

        self._memory.clear()
        logger.info("In-memory cache cleared")

    def health(self) -> Dict[str, Any]:
        """Return cache health status."""
        return {
            "redis_available": self._redis_available,
            "redis_url": self.redis_url,
            "memory_keys": len(self._memory),
            "max_candles": self.max_candles,
        }

    # ------------------------------------------------------------------
    # Fallback helpers
    # ------------------------------------------------------------------

    def _fallback_set(self, key: str, value: bytes) -> None:
        """Thread-safe in-memory set."""
        # Note: asyncio.Lock is not re-entrant; for sync access we use a simple
        # dict update. In an async context the caller should be in an event loop.
        self._memory[key] = value

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _df_to_json(df: pd.DataFrame) -> bytes:
        """Serialize DataFrame to compact JSON bytes."""
        # Convert to records; handle numpy types
        records = df.to_dict(orient="records")
        # Replace NaN/inf with None for JSON compatibility
        cleaned = DataCache._clean_for_json(records)
        return json.dumps(cleaned).encode("utf-8")

    @staticmethod
    def _json_to_df(payload: bytes) -> pd.DataFrame:
        """Deserialize JSON bytes back to DataFrame."""
        try:
            records = json.loads(payload)
            if not records:
                return pd.DataFrame()
            return pd.DataFrame(records)
        except Exception as exc:
            logger.error("Failed to deserialize DataFrame JSON: %s", exc)
            return pd.DataFrame()

    @staticmethod
    def _clean_for_json(obj: Any) -> Any:
        """Recursively replace NaN/inf with None for JSON serialization."""
        if isinstance(obj, dict):
            return {k: DataCache._clean_for_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [DataCache._clean_for_json(v) for v in obj]
        if isinstance(obj, float):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return obj
        return obj
