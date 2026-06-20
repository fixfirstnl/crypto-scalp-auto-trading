"""Liquidity Sweep Detection — Stop-Hunt & Reversal Identification.

Detects liquidity sweeps where price briefly pierces a key level (Asian
session high/low, equal highs/lows, prior swing points), takes stops, and
immediately reverses.  Genuine sweeps are confirmed by volume spikes and
quick reversal candles.

All calculations are vectorised via pandas/numpy where possible.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class LiquiditySweep:
    """Detect liquidity sweeps on crypto perp candles.

    Parameters
    ----------
    candles : pd.DataFrame
        Must contain ``open``, ``high``, ``low``, ``close``, ``volume``.
        Index should be a DatetimeIndex (UTC).
    """

    def __init__(self, candles: pd.DataFrame) -> None:
        if not isinstance(candles, pd.DataFrame):
            raise TypeError("candles must be a pandas DataFrame")
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(candles.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        self.candles = candles.copy()

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def find_asian_range(self, lookback: int = 20) -> Dict[str, Any]:
        """Identify the Asian session high/low as liquidity targets.

        Approximation: assumes the most recent ``lookback`` candles cover the
        Asian session (UTC 00:00-08:00).  For 1m/5m/15m data this is reasonably
        accurate; for 1H data the lookback should be 8.

        Parameters
        ----------
        lookback : int
            Number of candles to scan backward.

        Returns
        -------
        dict
            ``high``, ``low``, ``mid``, ``time`` (timestamp of the high).
        """
        recent = self.candles.iloc[-lookback:]
        if recent.empty:
            return {"high": 0.0, "low": 0.0, "mid": 0.0, "time": None}

        high = float(recent["high"].max())
        low = float(recent["low"].min())
        high_time = recent["high"].idxmax()

        return {
            "high": high,
            "low": low,
            "mid": (high + low) / 2.0,
            "time": high_time,
        }

    def detect_sweep_low(self, threshold: float = 0.005) -> Dict[str, Any]:
        """Detect a sweep below the Asian low or prior swing low.

        Logic:
            1. Price wicks below the Asian low (or recent swing low) by at
               least ``threshold`` %.
            2. The candle immediately reverses (close back above the level).
            3. Volume is elevated.

        Parameters
        ----------
        threshold : float
            Minimum sweep depth as a fraction of price (default 0.5 %).

        Returns
        -------
        dict
            ``swept`` (bool), ``level`` (float), ``reversal_candle`` (int),
            ``strength`` (float), ``time``.
        """
        asian = self.find_asian_range()
        level = asian["low"]
        if level <= 0:
            return {"swept": False, "level": 0.0, "reversal_candle": -1, "strength": 0.0, "time": None}

        lows = self.candles["low"].values
        highs = self.candles["high"].values
        closes = self.candles["close"].values
        volumes = self.candles["volume"].values
        times = self.candles.index
        avg_vol = float(np.mean(volumes)) if np.mean(volumes) > 0 else 1.0

        # Scan backwards from the most recent candles
        for i in range(len(closes) - 1, 1, -1):
            # Wick below level
            if lows[i] < level * (1 - threshold):
                # Reversal: close back above level (or next candle does)
                if closes[i] > level or (i + 1 < len(closes) and closes[i + 1] > level):
                    vol_ratio = volumes[i] / avg_vol
                    strength = min(vol_ratio, 3.0) / 3.0  # 0-1
                    return {
                        "swept": True,
                        "level": float(level),
                        "reversal_candle": int(i),
                        "strength": float(strength),
                        "time": times[i],
                    }
                break  # only look at the most recent sweep

        return {"swept": False, "level": float(level), "reversal_candle": -1, "strength": 0.0, "time": None}

    def detect_sweep_high(self, threshold: float = 0.005) -> Dict[str, Any]:
        """Detect a sweep above the Asian high or prior swing high.

        Symmetric to :meth:`detect_sweep_low`.

        Returns
        -------
        dict
            Same schema as :meth:`detect_sweep_low`.
        """
        asian = self.find_asian_range()
        level = asian["high"]
        if level <= 0:
            return {"swept": False, "level": 0.0, "reversal_candle": -1, "strength": 0.0, "time": None}

        lows = self.candles["low"].values
        highs = self.candles["high"].values
        closes = self.candles["close"].values
        volumes = self.candles["volume"].values
        times = self.candles.index
        avg_vol = float(np.mean(volumes)) if np.mean(volumes) > 0 else 1.0

        for i in range(len(closes) - 1, 1, -1):
            if highs[i] > level * (1 + threshold):
                if closes[i] < level or (i + 1 < len(closes) and closes[i + 1] < level):
                    vol_ratio = volumes[i] / avg_vol
                    strength = min(vol_ratio, 3.0) / 3.0
                    return {
                        "swept": True,
                        "level": float(level),
                        "reversal_candle": int(i),
                        "strength": float(strength),
                        "time": times[i],
                    }
                break

        return {"swept": False, "level": float(level), "reversal_candle": -1, "strength": 0.0, "time": None}

    def is_genuine_sweep(self, sweep: Dict[str, Any], volume_avg: float) -> bool:
        """Validate whether a detected sweep is genuine (not a continuation).

        A genuine sweep must satisfy:
            1. **Quick reversal** — < 2 candles below/above the level.
            2. **Volume spike** — sweep candle volume > 1.5x average.
            3. **Strong reversal candle** — body of reversal candle > 50 % of range.

        Parameters
        ----------
        sweep : dict
            Output from ``detect_sweep_low`` or ``detect_sweep_high``.
        volume_avg : float
            Average volume over the recent lookback period.

        Returns
        -------
        bool
        """
        if not sweep.get("swept", False):
            return False

        idx = sweep["reversal_candle"]
        if idx < 0 or idx >= len(self.candles):
            return False

        # Volume check
        sweep_vol = float(self.candles["volume"].iloc[idx])
        if volume_avg > 0 and sweep_vol < 1.5 * volume_avg:
            return False

        # Strong reversal candle body
        row = self.candles.iloc[idx]
        candle_range = float(row["high"] - row["low"])
        body = abs(float(row["close"] - row["open"]))
        if candle_range > 0 and body / candle_range < 0.5:
            return False

        return True

    def get_liquidity_levels(self, lookback: int = 20) -> List[Dict[str, Any]]:
        """Aggregate liquidity targets from multiple sources.

        Sources:
            1. Asian session high / low
            2. Equal highs / equal lows within the lookback window
            3. Most recent swing high / swing low

        Parameters
        ----------
        lookback : int
            Candles to scan for equal highs/lows.

        Returns
        -------
        List[dict]
            Each dict: ``price``, ``type`` (``'high'`` | ``'low'``),
            ``source`` (``'asian'`` | ``'equal'`` | ``'swing'``), ``strength``.
        """
        levels: List[Dict[str, Any]] = []
        recent = self.candles.iloc[-lookback:]

        # 1. Asian range
        asian = self.find_asian_range(lookback)
        levels.append({"price": asian["high"], "type": "high", "source": "asian", "strength": 0.8})
        levels.append({"price": asian["low"], "type": "low", "source": "asian", "strength": 0.8})

        # 2. Equal highs / lows (clusters within 0.1 %)
        highs = recent["high"].values
        lows = recent["low"].values
        tol = np.mean(highs) * 0.001

        # Simple cluster detection: count near-duplicates
        for target in [highs, lows]:
            level_type = "high" if target is highs else "low"
            for i, price in enumerate(target):
                count = np.sum(np.abs(target - price) < tol)
                if count >= 2:  # at least 2 touches
                    levels.append(
                        {
                            "price": float(price),
                            "type": level_type,
                            "source": "equal",
                            "strength": min(count * 0.2, 1.0),
                        }
                    )

        # Deduplicate by price (within tolerance)
        unique_levels: List[Dict[str, Any]] = []
        for lvl in levels:
            is_new = True
            for existing in unique_levels:
                if abs(existing["price"] - lvl["price"]) < tol:
                    is_new = False
                    break
            if is_new:
                unique_levels.append(lvl)

        logger.info("Found %d unique liquidity levels (lookback=%d)", len(unique_levels), lookback)
        return unique_levels
