"""
Indicator Engine
================
Technical indicator calculations for the ICT/SMC hybrid scalping strategy.

Supported indicators
----------------------
- EMA 9 / EMA 21 — crossover signals, dynamic support/resistance
- VWAP — intraday fair-value anchor (typical price × volume cumulative)
- RSI(14) — momentum / divergence confirmation
- ATR(14) — volatility-based stop / target sizing
- Volume Profile — POC, VAH, VAL (histogram of volume at price levels)

All methods accept a pandas DataFrame of OHLCV candles and return
pandas Series or dicts. Optimized for speed via vectorized operations.

Dependencies
------------
- pandas >= 2.0
- numpy

Note: pandas-ta / ta-lib not strictly required; pure pandas/numpy
implementations are used for portability and speed.

Example
-------
    engine = IndicatorEngine(data_cache)
    indicators = engine.calculate_all(candles)
    # indicators['ema_9'], indicators['vwap'], indicators['rsi'], etc.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from .data_cache import DataCache

logger = logging.getLogger(__name__)


class IndicatorEngine:
    """
    Calculate technical indicators for crypto scalping.

    Parameters
    ----------
    data_cache : DataCache, optional
        Reference to the cache layer; used to persist computed indicators
        so other layers can retrieve them without re-computation.
    """

    def __init__(self, data_cache: Optional[DataCache] = None) -> None:
        self.cache: Optional[DataCache] = data_cache
        logger.info("IndicatorEngine initialized")

    # ------------------------------------------------------------------
    # EMA
    # ------------------------------------------------------------------

    def calculate_ema(
        self, candles: pd.DataFrame, period: int
    ) -> pd.Series:
        """
        Calculate Exponential Moving Average (EMA).

        Parameters
        ----------
        candles : pd.DataFrame
            Must contain a ``close`` column.
        period : int
            EMA lookback period (e.g. 9 or 21).

        Returns
        -------
        pd.Series
            EMA values aligned with the input index.
        """
        if "close" not in candles.columns:
            raise ValueError("DataFrame must contain 'close' column")
        ema = candles["close"].ewm(span=period, adjust=False).mean()
        return ema

    # ------------------------------------------------------------------
    # VWAP
    # ------------------------------------------------------------------

    def calculate_vwap(self, candles: pd.DataFrame) -> pd.Series:
        """
        Calculate Volume-Weighted Average Price (VWAP).

        Uses the *typical price* = (high + low + close) / 3.
        VWAP = cumulative(TP × volume) / cumulative(volume)

        Parameters
        ----------
        candles : pd.DataFrame
            Must contain ``high``, ``low``, ``close``, ``volume`` columns.

        Returns
        -------
        pd.Series
            VWAP values aligned with the input index.
        """
        required = {"high", "low", "close", "volume"}
        missing = required - set(candles.columns)
        if missing:
            raise ValueError(f"DataFrame missing columns: {missing}")

        typical_price = (candles["high"] + candles["low"] + candles["close"]) / 3.0
        tp_vol = typical_price * candles["volume"]
        vwap = tp_vol.cumsum() / candles["volume"].cumsum()
        return vwap

    # ------------------------------------------------------------------
    # RSI
    # ------------------------------------------------------------------

    def calculate_rsi(
        self, candles: pd.DataFrame, period: int = 14
    ) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).

        Parameters
        ----------
        candles : pd.DataFrame
            Must contain ``close`` column.
        period : int, default 14
            RSI lookback period.

        Returns
        -------
        pd.Series
            RSI values (0-100). NaN for first `period` rows.
        """
        if "close" not in candles.columns:
            raise ValueError("DataFrame must contain 'close' column")

        delta = candles["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    # ------------------------------------------------------------------
    # ATR
    # ------------------------------------------------------------------

    def calculate_atr(
        self, candles: pd.DataFrame, period: int = 14
    ) -> pd.Series:
        """
        Calculate Average True Range (ATR).

        Used for dynamic stop-loss and take-profit sizing.

        Parameters
        ----------
        candles : pd.DataFrame
            Must contain ``high``, ``low``, ``close`` columns.
        period : int, default 14
            ATR lookback period.

        Returns
        -------
        pd.Series
            ATR values aligned with the input index.
        """
        required = {"high", "low", "close"}
        missing = required - set(candles.columns)
        if missing:
            raise ValueError(f"DataFrame missing columns: {missing}")

        high_low = candles["high"] - candles["low"]
        high_close = (candles["high"] - candles["close"].shift()).abs()
        low_close = (candles["low"] - candles["close"].shift()).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.ewm(span=period, adjust=False).mean()
        return atr

    # ------------------------------------------------------------------
    # Volume Profile
    # ------------------------------------------------------------------

    def calculate_volume_profile(
        self, candles: pd.DataFrame, bins: int = 10
    ) -> Dict[str, Any]:
        """
        Calculate Volume Profile for a candle set.

        Returns POC (Point of Control), VAH (Value Area High),
        VAL (Value Area Low), and the full histogram.

        Parameters
        ----------
        candles : pd.DataFrame
            Must contain ``low``, ``high``, ``volume`` columns.
        bins : int, default 10
            Number of price-level bins for the histogram.

        Returns
        -------
        dict
            {
                "poc": float,          # price with highest volume
                "vah": float,          # 70th percentile (top of value area)
                "val": float,          # 30th percentile (bottom of value area)
                "histogram": pd.Series,  # volume per bin (index=price midpoint)
                "bin_edges": np.ndarray, # price boundaries
            }
        """
        required = {"low", "high", "volume"}
        missing = required - set(candles.columns)
        if missing:
            raise ValueError(f"DataFrame missing columns: {missing}")

        if candles.empty:
            return {
                "poc": np.nan,
                "vah": np.nan,
                "val": np.nan,
                "histogram": pd.Series(dtype=float),
                "bin_edges": np.array([]),
            }

        # Approximate price per candle as typical price
        typical = (candles["high"] + candles["low"] + candles.get("close", candles["high"])) / 3.0

        # Create weighted histogram
        hist, bin_edges = np.histogram(
            typical, bins=bins, weights=candles["volume"]
        )
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

        # POC: price level with maximum volume
        poc_idx = int(np.argmax(hist))
        poc = float(bin_centers[poc_idx])

        # Value Area = 70 % of total volume centred around POC
        total_vol = hist.sum()
        target_vol = 0.70 * total_vol

        # Expand outward from POC until 70 % captured
        n = len(hist)
        left = poc_idx
        right = poc_idx
        cum_vol = hist[poc_idx]

        while cum_vol < target_vol and (left > 0 or right < n - 1):
            left_vol = hist[left - 1] if left > 0 else 0
            right_vol = hist[right + 1] if right < n - 1 else 0
            if left_vol >= right_vol and left > 0:
                left -= 1
                cum_vol += left_vol
            elif right < n - 1:
                right += 1
                cum_vol += right_vol
            else:
                break

        vah = float(bin_edges[right + 1])
        val = float(bin_edges[left])

        result = {
            "poc": poc,
            "vah": vah,
            "val": val,
            "histogram": pd.Series(hist, index=bin_centers),
            "bin_edges": bin_edges,
        }
        return result

    # ------------------------------------------------------------------
    # Volume metrics (helpers)
    # ------------------------------------------------------------------

    def calculate_volume_sma(
        self, candles: pd.DataFrame, period: int = 20
    ) -> pd.Series:
        """Simple moving average of volume."""
        if "volume" not in candles.columns:
            raise ValueError("DataFrame must contain 'volume' column")
        return candles["volume"].rolling(window=period, min_periods=1).mean()

    def calculate_volume_ratio(
        self, candles: pd.DataFrame, period: int = 20
    ) -> pd.Series:
        """
        Volume ratio = current volume / SMA volume.

        Values > 1.5x indicate a volume spike (used for entry confirmation).
        """
        vol_sma = self.calculate_volume_sma(candles, period)
        ratio = candles["volume"] / vol_sma.replace(0, np.nan)
        return ratio

    # ------------------------------------------------------------------
    # Composite: calculate all
    # ------------------------------------------------------------------

    def calculate_all(
        self, candles: pd.DataFrame, symbol: str = "", timeframe: str = ""
    ) -> Dict[str, Any]:
        """
        Compute the full indicator set for scalping.

        Parameters
        ----------
        candles : pd.DataFrame
            OHLCV DataFrame with columns ``open``, ``high``, ``low``, ``close``, ``volume``.
        symbol : str, optional
            If provided, cached under ``symbol/timeframe`` keys.
        timeframe : str, optional
            If provided, cached under ``symbol/timeframe`` keys.

        Returns
        -------
        dict
            {
                "ema_9": pd.Series,
                "ema_21": pd.Series,
                "vwap": pd.Series,
                "rsi": pd.Series,
                "atr": pd.Series,
                "volume_profile": dict,
                "volume_sma_20": pd.Series,
                "volume_ratio": pd.Series,
            }
        """
        if candles.empty:
            logger.warning("calculate_all called with empty DataFrame")
            return {}

        # Ensure required columns exist
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(candles.columns)
        if missing:
            raise ValueError(f"DataFrame missing columns: {missing}")

        # Core indicators
        ema_9 = self.calculate_ema(candles, period=9)
        ema_21 = self.calculate_ema(candles, period=21)
        vwap = self.calculate_vwap(candles)
        rsi = self.calculate_rsi(candles, period=14)
        atr = self.calculate_atr(candles, period=14)
        volume_profile = self.calculate_volume_profile(candles, bins=10)
        volume_sma_20 = self.calculate_volume_sma(candles, period=20)
        volume_ratio = self.calculate_volume_ratio(candles, period=20)

        result = {
            "ema_9": ema_9,
            "ema_21": ema_21,
            "vwap": vwap,
            "rsi": rsi,
            "atr": atr,
            "volume_profile": volume_profile,
            "volume_sma_20": volume_sma_20,
            "volume_ratio": volume_ratio,
        }

        # Persist to cache if available
        if self.cache is not None and symbol and timeframe:
            for key, value in result.items():
                self.cache.set_indicator(symbol, timeframe, key, value)
            logger.debug(
                "Indicators cached | symbol=%s timeframe=%s indicators=%d",
                symbol,
                timeframe,
                len(result),
            )

        return result
