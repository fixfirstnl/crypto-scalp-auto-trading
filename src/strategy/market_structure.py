"""MarketStructure: BOS/CHoCH detection for ICT/SMC analysis.

Identifies market structure shifts on higher timeframes (1H/4H) to determine
directional bias. Key concepts:

- Break of Structure (BOS): Price breaks previous high/low in trend direction
- Change of Character (CHoCH): Price breaks previous low/high against trend (reversal signal)
- Premium/Discount: Price above/below 50% of the range (institutional reference)

Usage:
    ms = MarketStructure(candles)
    structure = ms.detect_structure(lookback=10)
    # structure['bias'] = 'bullish' | 'bearish' | 'neutral'
    # structure['last_bos'] = last BOS event
    # structure['last_choch'] = last CHoCH event
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class MarketStructure:
    """Detects BOS/CHoCH and market structure on OHLCV data.
    
    Parameters
    ----------
    candles : pd.DataFrame
        OHLCV DataFrame with columns: open, high, low, close, volume
    """

    def __init__(self, candles: pd.DataFrame) -> None:
        self.candles = candles
        self.highs = candles['high'].values
        self.lows = candles['low'].values
        self.closes = candles['close'].values

    def detect_structure(self, lookback: int = 10) -> Dict[str, Any]:
        """Detect market structure (BOS/CHoCH) over recent candles.
        
        Parameters
        ----------
        lookback : int, default 10
            Number of candles to analyze for structure.
        
        Returns
        -------
        dict
            Structure analysis with bias, BOS/CHoCH events, and strength.
        """
        if len(self.candles) < lookback + 5:
            return {"bias": "neutral", "strength": 0, "last_bos": None, "last_choch": None}
        
        recent_highs = self.highs[-lookback:]
        recent_lows = self.lows[-lookback:]
        
        # Find swing points
        swing_highs = self._find_swing_highs(recent_highs, window=3)
        swing_lows = self._find_swing_lows(recent_lows, window=3)
        
        # Detect BOS (Break of Structure)
        bos_events = self._detect_bos(swing_highs, swing_lows)
        
        # Detect CHoCH (Change of Character)
        choch_events = self._detect_choch(swing_highs, swing_lows)
        
        # Determine bias from most recent structure
        bias = "neutral"
        strength = 0
        last_bos = None
        last_choch = None
        
        if bos_events:
            last_bos = bos_events[-1]
            if last_bos['type'] == 'bullish_bos':
                bias = "bullish"
                strength = last_bos['strength']
            elif last_bos['type'] == 'bearish_bos':
                bias = "bearish"
                strength = last_bos['strength']
        
        if choch_events:
            last_choch = choch_events[-1]
            if last_choch['type'] == 'bullish_choch':
                bias = "bullish"
                strength = max(strength, last_choch['strength'])
            elif last_choch['type'] == 'bearish_choch':
                bias = "bearish"
                strength = max(strength, last_choch['strength'])
        
        # Premium/Discount classification
        mid = (np.max(recent_highs) + np.min(recent_lows)) / 2
        current_price = self.closes[-1]
        premium_discount = "premium" if current_price > mid else "discount"
        
        return {
            "bias": bias,
            "strength": strength,
            "last_bos": last_bos,
            "last_choch": last_choch,
            "premium_discount": premium_discount,
            "midpoint": mid,
            "swing_highs": len(swing_highs),
            "swing_lows": len(swing_lows),
        }

    def _find_swing_highs(self, prices: np.ndarray, window: int = 3) -> List[int]:
        """Find indices of swing highs."""
        highs = []
        for i in range(window, len(prices) - window):
            if prices[i] == max(prices[i - window:i + window + 1]):
                highs.append(i)
        return highs

    def _find_swing_lows(self, prices: np.ndarray, window: int = 3) -> List[int]:
        """Find indices of swing lows."""
        lows = []
        for i in range(window, len(prices) - window):
            if prices[i] == min(prices[i - window:i + window + 1]):
                lows.append(i)
        return lows

    def _detect_bos(self, swing_highs: List[int], swing_lows: List[int]) -> List[Dict[str, Any]]:
        """Detect Break of Structure events."""
        events = []
        
        # Bullish BOS: price breaks above previous swing high
        if len(swing_highs) >= 2:
            for i in range(1, len(swing_highs)):
                if self.highs[swing_highs[i]] > self.highs[swing_highs[i - 1]]:
                    events.append({
                        "type": "bullish_bos",
                        "index": swing_highs[i],
                        "price": float(self.highs[swing_highs[i]]),
                        "previous": float(self.highs[swing_highs[i - 1]]),
                        "strength": (self.highs[swing_highs[i]] - self.highs[swing_highs[i - 1]]) / self.highs[swing_highs[i - 1]] * 100,
                    })
        
        # Bearish BOS: price breaks below previous swing low
        if len(swing_lows) >= 2:
            for i in range(1, len(swing_lows)):
                if self.lows[swing_lows[i]] < self.lows[swing_lows[i - 1]]:
                    events.append({
                        "type": "bearish_bos",
                        "index": swing_lows[i],
                        "price": float(self.lows[swing_lows[i]]),
                        "previous": float(self.lows[swing_lows[i - 1]]),
                        "strength": (self.lows[swing_lows[i - 1]] - self.lows[swing_lows[i]]) / self.lows[swing_lows[i - 1]] * 100,
                    })
        
        return events

    def _detect_choch(self, swing_highs: List[int], swing_lows: List[int]) -> List[Dict[str, Any]]:
        """Detect Change of Character events."""
        events = []
        
        # Bullish CHoCH: price breaks above previous swing high after downtrend
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            # Check if last swing low was lower (downtrend) and then broke high
            if swing_lows[-1] > swing_highs[-2] and self.highs[swing_highs[-1]] > self.highs[swing_highs[-2]]:
                events.append({
                    "type": "bullish_choch",
                    "index": swing_highs[-1],
                    "price": float(self.highs[swing_highs[-1]]),
                    "strength": (self.highs[swing_highs[-1]] - self.highs[swing_highs[-2]]) / self.highs[swing_highs[-2]] * 100,
                })
            
            # Bearish CHoCH: price breaks below previous swing low after uptrend
            if swing_highs[-1] > swing_lows[-2] and self.lows[swing_lows[-1]] < self.lows[swing_lows[-2]]:
                events.append({
                    "type": "bearish_choch",
                    "index": swing_lows[-1],
                    "price": float(self.lows[swing_lows[-1]]),
                    "strength": (self.lows[swing_lows[-2]] - self.lows[swing_lows[-1]]) / self.lows[swing_lows[-2]] * 100,
                })
        
        return events
