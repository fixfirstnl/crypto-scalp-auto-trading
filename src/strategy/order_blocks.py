"""OrderBlocks: Identify and score Order Blocks (OB) for ICT/SMC analysis.

Order Blocks are the last opposing candle before a strong move, representing
institutional supply/demand zones. This module identifies:

- Bullish OB: Last bearish candle before a strong bullish move
- Bearish OB: Last bullish candle before a strong bearish move
- OB scoring: Based on move strength, proximity to current price, and confluence

Usage:
    ob = OrderBlocks(candles)
    blocks = ob.find_order_blocks()
    # blocks = [{type, high, low, score, index, strength}, ...]
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class OrderBlocks:
    """Identify and score Order Blocks from OHLCV data.
    
    Parameters
    ----------
    candles : pd.DataFrame
        OHLCV DataFrame with columns: open, high, low, close, volume
    """

    def __init__(self, candles: pd.DataFrame) -> None:
        self.candles = candles
        self.opens = candles['open'].values
        self.highs = candles['high'].values
        self.lows = candles['low'].values
        self.closes = candles['close'].values

    def find_order_blocks(self, lookback: int = 20) -> List[Dict[str, Any]]:
        """Find order blocks in recent candles.
        
        Parameters
        ----------
        lookback : int, default 20
            Number of candles to analyze.
        
        Returns
        -------
        list
            List of order block dictionaries.
        """
        if len(self.candles) < lookback + 5:
            return []
        
        recent = self.candles.tail(lookback).reset_index(drop=True)
        blocks = []
        
        for i in range(2, len(recent) - 3):
            # Check for bullish OB (bearish candle before strong bullish move)
            if self._is_bullish_ob(recent, i):
                block = self._create_block(recent, i, 'bullish')
                if block:
                    blocks.append(block)
            
            # Check for bearish OB (bullish candle before strong bearish move)
            if self._is_bearish_ob(recent, i):
                block = self._create_block(recent, i, 'bearish')
                if block:
                    blocks.append(block)
        
        # Sort by score (descending)
        blocks.sort(key=lambda x: x['score'], reverse=True)
        return blocks[:5]  # Return top 5

    def _is_bullish_ob(self, candles: pd.DataFrame, idx: int) -> bool:
        """Check if candle at idx is a bullish order block."""
        if idx < 2 or idx >= len(candles) - 3:
            return False
        
        # The OB candle should be bearish (close < open)
        if candles['close'].iloc[idx] >= candles['open'].iloc[idx]:
            return False
        
        # Next 1-3 candles should be strongly bullish
        next_candles = candles.iloc[idx + 1:idx + 4]
        bull_count = sum(next_candles['close'] > next_candles['open'])
        
        if bull_count < 2:
            return False
        
        # The move should be significant (>1%)
        move = (next_candles['high'].max() - candles['close'].iloc[idx]) / candles['close'].iloc[idx]
        return move > 0.01

    def _is_bearish_ob(self, candles: pd.DataFrame, idx: int) -> bool:
        """Check if candle at idx is a bearish order block."""
        if idx < 2 or idx >= len(candles) - 3:
            return False
        
        # The OB candle should be bullish (close > open)
        if candles['close'].iloc[idx] <= candles['open'].iloc[idx]:
            return False
        
        # Next 1-3 candles should be strongly bearish
        next_candles = candles.iloc[idx + 1:idx + 4]
        bear_count = sum(next_candles['close'] < next_candles['open'])
        
        if bear_count < 2:
            return False
        
        # The move should be significant (>1%)
        move = (candles['close'].iloc[idx] - next_candles['low'].min()) / candles['close'].iloc[idx]
        return move > 0.01

    def _create_block(self, candles: pd.DataFrame, idx: int, ob_type: str) -> Dict[str, Any]:
        """Create an order block dictionary with scoring."""
        candle = candles.iloc[idx]
        high = candle['high']
        low = candle['low']
        
        # Calculate strength based on the subsequent move
        next_candles = candles.iloc[idx + 1:idx + 4]
        if ob_type == 'bullish':
            move = (next_candles['high'].max() - candle['close']) / candle['close']
        else:
            move = (candle['close'] - next_candles['low'].min()) / candle['close']
        
        # Score: strength (0-50) + freshness (0-30) + volume (0-20)
        strength_score = min(move * 100 * 5, 50)  # 1% move = 5 points, cap at 50
        
        # Freshness: how recent (0-30)
        freshness = max(0, 30 - (len(candles) - idx) * 2)
        
        # Volume: relative to average (0-20)
        avg_volume = candles['volume'].mean() if 'volume' in candles.columns else 1
        volume_ratio = candle.get('volume', avg_volume) / avg_volume if avg_volume > 0 else 1
        volume_score = min(volume_ratio * 10, 20)
        
        total_score = strength_score + freshness + volume_score
        
        return {
            'type': ob_type,
            'high': float(high),
            'low': float(low),
            'score': round(total_score, 2),
            'index': idx,
            'strength': round(move * 100, 2),  # % move
            'freshness': round(freshness, 2),
            'volume_score': round(volume_score, 2),
            'open': float(candle['open']),
            'close': float(candle['close']),
        }
