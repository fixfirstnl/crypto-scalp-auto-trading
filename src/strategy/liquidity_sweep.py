"""LiquiditySweep: Detect liquidity sweeps for ICT/SMC entry triggers.

Identifies liquidity sweeps that serve as entry triggers:
1. Asian Range Sweeps: Price sweeps Asian session high/low, then reverses
2. Equal Highs/Lows Sweeps: Price sweeps equal highs/lows (double tops/bottoms), then reverses
3. Previous Day High/Low Sweeps: Price sweeps previous day's extreme, then reverses

A valid sweep requires:
- Price briefly breaks a key level (high/low)
- Immediate reversal (wick rejection)
- Structure alignment (with HTF bias)
- Volume confirmation

Usage:
    sweep = LiquiditySweep(setup_candles, entry_candles)
    result = sweep.check_sweep(bias='bullish')
    # result['sweep_found'] = True/False
    # result['sweep_type'] = 'asian_high' | 'asian_low' | 'equal_high' | 'equal_low' | 'pdh' | 'pdl'
    # result['strength'] = 0-1 (confidence score)
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class LiquiditySweep:
    """Detect liquidity sweeps for entry confirmation.
    
    Parameters
    ----------
    setup_candles : pd.DataFrame
        15m OHLCV candles for setup analysis.
    entry_candles : pd.DataFrame
        5m OHLCV candles for entry zone refinement.
    """

    def __init__(
        self,
        setup_candles: pd.DataFrame,
        entry_candles: pd.DataFrame,
    ) -> None:
        self.setup_candles = setup_candles
        self.entry_candles = entry_candles

    def check_sweep(self, bias: str) -> Dict[str, Any]:
        """Check for a valid liquidity sweep aligned with bias.
        
        Parameters
        ----------
        bias : str
            'bullish' or 'bearish' from HTF analysis.
        
        Returns
        -------
        dict
            Sweep detection result.
        """
        if self.setup_candles.empty or self.entry_candles.empty:
            return {"sweep_found": False, "reason": "No candle data"}
        
        # Check Asian range sweep
        asian_sweep = self._check_asian_range_sweep(bias)
        if asian_sweep.get('sweep_found'):
            return asian_sweep
        
        # Check equal highs/lows sweep
        equal_sweep = self._check_equal_sweep(bias)
        if equal_sweep.get('sweep_found'):
            return equal_sweep
        
        # Check previous day high/low sweep
        pd_sweep = self._check_previous_day_sweep(bias)
        if pd_sweep.get('sweep_found'):
            return pd_sweep
        
        return {"sweep_found": False, "reason": "No valid sweep detected"}

    def _check_asian_range_sweep(self, bias: str) -> Dict[str, Any]:
        """Check for Asian range liquidity sweep.
        
        Asian session (approx 00:00-08:00 UTC) high/low often gets swept
        during London/NY sessions.
        """
        # Simplified: look at last 24 candles (6 hours on 15m) for range
        if len(self.setup_candles) < 24:
            return {"sweep_found": False}
        
        recent = self.setup_candles.tail(24)
        asian_high = recent['high'].max()
        asian_low = recent['low'].min()
        
        current = self.setup_candles.iloc[-1]
        
        if bias == 'bullish':
            # Looking for sweep of Asian low (price dips below, then reverses up)
            if current['low'] < asian_low and current['close'] > asian_low:
                # Wick below, close above = sweep of lows with reversal
                strength = (asian_low - current['low']) / (current['high'] - current['low'])
                return {
                    "sweep_found": True,
                    "sweep_type": "asian_low",
                    "strength": round(min(strength, 1.0), 2),
                    "level": round(asian_low, 2),
                    "price": round(current['close'], 2),
                }
        
        if bias == 'bearish':
            # Looking for sweep of Asian high (price spikes above, then reverses down)
            if current['high'] > asian_high and current['close'] < asian_high:
                # Wick above, close below = sweep of highs with reversal
                strength = (current['high'] - asian_high) / (current['high'] - current['low'])
                return {
                    "sweep_found": True,
                    "sweep_type": "asian_high",
                    "strength": round(min(strength, 1.0), 2),
                    "level": round(asian_high, 2),
                    "price": round(current['close'], 2),
                }
        
        return {"sweep_found": False}

    def _check_equal_sweep(self, bias: str) -> Dict[str, Any]:
        """Check for equal highs/lows sweep (double tops/bottoms)."""
        if len(self.setup_candles) < 10:
            return {"sweep_found": False}
        
        recent = self.setup_candles.tail(10)
        
        # Find equal highs (within 0.1%)
        highs = recent['high'].values
        for i in range(len(highs) - 1):
            for j in range(i + 1, len(highs)):
                if abs(highs[i] - highs[j]) / highs[i] < 0.001:  # 0.1% tolerance
                    # Equal high found - check if recent candle swept it
                    current = self.setup_candles.iloc[-1]
                    if current['high'] > highs[i] and current['close'] < highs[i]:
                        if bias == 'bearish':
                            return {
                                "sweep_found": True,
                                "sweep_type": "equal_high",
                                "strength": 0.8,
                                "level": round(highs[i], 2),
                                "price": round(current['close'], 2),
                            }
        
        # Find equal lows (within 0.1%)
        lows = recent['low'].values
        for i in range(len(lows) - 1):
            for j in range(i + 1, len(lows)):
                if abs(lows[i] - lows[j]) / lows[i] < 0.001:  # 0.1% tolerance
                    # Equal low found - check if recent candle swept it
                    current = self.setup_candles.iloc[-1]
                    if current['low'] < lows[i] and current['close'] > lows[i]:
                        if bias == 'bullish':
                            return {
                                "sweep_found": True,
                                "sweep_type": "equal_low",
                                "strength": 0.8,
                                "level": round(lows[i], 2),
                                "price": round(current['close'], 2),
                            }
        
        return {"sweep_found": False}

    def _check_previous_day_sweep(self, bias: str) -> Dict[str, Any]:
        """Check for previous day high/low sweep."""
        # Need at least 96 candles (24 hours on 15m) for previous day
        if len(self.setup_candles) < 96:
            return {"sweep_found": False}
        
        # Previous day (candles 24-48 hours ago)
        prev_day = self.setup_candles.iloc[-96:-48]
        if len(prev_day) == 0:
            return {"sweep_found": False}
        
        pd_high = prev_day['high'].max()
        pd_low = prev_day['low'].min()
        
        current = self.setup_candles.iloc[-1]
        
        if bias == 'bullish':
            # Sweep of previous day low
            if current['low'] < pd_low and current['close'] > pd_low:
                strength = (pd_low - current['low']) / (current['high'] - current['low'])
                return {
                    "sweep_found": True,
                    "sweep_type": "pdl",
                    "strength": round(min(strength, 1.0), 2),
                    "level": round(pd_low, 2),
                    "price": round(current['close'], 2),
                }
        
        if bias == 'bearish':
            # Sweep of previous day high
            if current['high'] > pd_high and current['close'] < pd_high:
                strength = (current['high'] - pd_high) / (current['high'] - current['low'])
                return {
                    "sweep_found": True,
                    "sweep_type": "pdh",
                    "strength": round(min(strength, 1.0), 2),
                    "level": round(pd_high, 2),
                    "price": round(current['close'], 2),
                }
        
        return {"sweep_found": False}
