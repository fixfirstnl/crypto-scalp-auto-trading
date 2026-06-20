"""FairValueGaps: Detect and track Fair Value Gaps (FVG) for ICT/SMC analysis.

Fair Value Gaps are imbalances in price action where a candle's wick doesn't
fully overlap the previous candle's body, creating an unfilled zone. These zones
act as magnets for price and provide confluence with Order Blocks.

This module identifies:
- Bullish FVG: Low of current candle > High of candle 2 candles ago (gap up)
- Bearish FVG: High of current candle < Low of candle 2 candles ago (gap down)
- FVG fill tracking: Whether price has returned to fill the gap

Usage:
    fvg = FairValueGaps(candles)
    gaps = fvg.find_fvgs()
    # gaps = [{type, high, low, filled, fill_index, age}, ...]
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class FairValueGaps:
    """Detect Fair Value Gaps in OHLCV data.
    
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

    def find_fvgs(self, lookback: int = 20) -> List[Dict[str, Any]]:
        """Find Fair Value Gaps in recent candles.
        
        Parameters
        ----------
        lookback : int, default 20
            Number of candles to analyze.
        
        Returns
        -------
        list
            List of FVG dictionaries.
        """
        if len(self.candles) < lookback + 5:
            return []
        
        recent = self.candles.tail(lookback).reset_index(drop=True)
        fvgs = []
        
        for i in range(2, len(recent)):
            # Check for bullish FVG (gap up)
            if self._is_bullish_fvg(recent, i):
                fvg = self._create_fvg(recent, i, 'bullish')
                if fvg:
                    fvgs.append(fvg)
            
            # Check for bearish FVG (gap down)
            if self._is_bearish_fvg(recent, i):
                fvg = self._create_fvg(recent, i, 'bearish')
                if fvg:
                    fvgs.append(fvg)
        
        return fvgs

    def _is_bullish_fvg(self, candles: pd.DataFrame, idx: int) -> bool:
        """Check for bullish FVG at index.
        
        Bullish FVG: Low[idx] > High[idx-2] (gap up between idx-2 and idx)
        """
        if idx < 2:
            return False
        return candles['low'].iloc[idx] > candles['high'].iloc[idx - 2]

    def _is_bearish_fvg(self, candles: pd.DataFrame, idx: int) -> bool:
        """Check for bearish FVG at index.
        
        Bearish FVG: High[idx] < Low[idx-2] (gap down between idx-2 and idx)
        """
        if idx < 2:
            return False
        return candles['high'].iloc[idx] < candles['low'].iloc[idx - 2]

    def _create_fvg(self, candles: pd.DataFrame, idx: int, fvg_type: str) -> Dict[str, Any]:
        """Create FVG dictionary with fill tracking."""
        if fvg_type == 'bullish':
            high = candles['low'].iloc[idx]  # Upper boundary
            low = candles['high'].iloc[idx - 2]  # Lower boundary
        else:
            high = candles['low'].iloc[idx - 2]  # Upper boundary
            low = candles['high'].iloc[idx]  # Lower boundary
        
        # Check if FVG has been filled (price returned to the zone)
        filled = False
        fill_index = -1
        
        for j in range(idx + 1, len(candles)):
            candle_low = candles['low'].iloc[j]
            candle_high = candles['high'].iloc[j]
            
            if fvg_type == 'bullish':
                # FVG filled if price drops below the high of the FVG
                if candle_low <= high:
                    filled = True
                    fill_index = j
                    break
            else:
                # FVG filled if price rises above the low of the FVG
                if candle_high >= low:
                    filled = True
                    fill_index = j
                    break
        
        # Age: how many candles since FVG formed
        age = len(candles) - idx - 1
        
        # Size of the gap
        gap_size = abs(high - low) / ((high + low) / 2) * 100
        
        return {
            'type': fvg_type,
            'high': float(high),
            'low': float(low),
            'filled': filled,
            'fill_index': fill_index,
            'age': age,
            'gap_size': round(gap_size, 4),  # % of price
            'index': idx,
        }
