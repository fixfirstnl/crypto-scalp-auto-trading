"""ICTSMCStrategy: Main strategy orchestrator.

Wires together all ICT/SMC components (MarketStructure, OrderBlocks, FairValueGaps,
LiquiditySweep) into a unified trading pipeline. The strategy operates across
multiple timeframes:

- HTF (1H/4H): Bias via MarketStructure (BOS/CHoCH)
- MTF (15m): Setup scan — liquidity sweep + OB/FVG confluence
- LTF (5m): Entry zone refinement
- Entry (1m): Confirmation via EMA cross + RSI + volume

Entry Rules (Simplified):
1. HTF bias aligned (bullish → long, bearish → short)
2. Liquidity sweep (Asian range or equal highs/lows)
3. Order Block + FVG confluence in premium/discount zone
4. EMA 9/21 crossover confirmation
5. RSI not overbought/oversold (30-70 zone)
6. Volume spike (>1.5x average)

Exit Rules:
- Stop-loss: 5-15 pips below/above entry (or 1x ATR)
- TP1: 33% @ 1R (risk amount)
- TP2: 33% @ 2R
- TP3: 34% trailing (runner)
- Breakeven after TP1: move SL to entry + 1 pip
- Trailing stop after TP2: 50% of the distance from entry to TP2

Usage:
    strategy = ICTSMCStrategy(data_cache, indicator_engine)
    setup = strategy.scan_for_setup('BTC/USDT:USDT', 'bullish', candles_15m, candles_5m)
    if setup['signal'] != 'none':
        entry = strategy.confirm_entry(setup, candles_1m, indicators)
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

import pandas as pd
import numpy as np

from src.layer1_data import DataCache, IndicatorEngine
from .market_structure import MarketStructure
from .order_blocks import OrderBlocks
from .fair_value_gaps import FairValueGaps
from .liquidity_sweep import LiquiditySweep

logger = logging.getLogger(__name__)


class ICTSMCStrategy:
    """ICT/SMC hybrid scalping strategy orchestrator.
    
    Parameters
    ----------
    data_cache : DataCache
        Layer-1 data cache for OHLCV retrieval.
    indicator_engine : IndicatorEngine
        Layer-1 indicator calculator.
    """

    def __init__(
        self,
        data_cache: DataCache,
        indicator_engine: IndicatorEngine,
    ) -> None:
        self.data_cache = data_cache
        self.indicator_engine = indicator_engine
        
        # Strategy components
        self.market_structure = None  # Created per-analysis
        self.order_blocks = None
        self.fvg = None
        self.liquidity_sweep = None

    # ------------------------------------------------------------------
    # Stage 1: Setup Scan (15m + 5m)
    # ------------------------------------------------------------------

    def scan_for_setup(
        self,
        symbol: str,
        bias: str,  # 'bullish' or 'bearish'
        setup_candles: pd.DataFrame,  # 15m candles
        entry_candles: pd.DataFrame,  # 5m candles
    ) -> Dict[str, Any]:
        """Scan for a valid ICT/SMC setup.
        
        Parameters
        ----------
        symbol : str
            Trading pair.
        bias : str
            'bullish' or 'bearish' from HTF analysis.
        setup_candles : pd.DataFrame
            15m OHLCV candles for setup scan.
        entry_candles : pd.DataFrame
            5m OHLCV candles for entry zone refinement.
        
        Returns
        -------
        dict
            Setup result with signal, confluence score, and details.
        """
        if setup_candles.empty or entry_candles.empty:
            return {"signal": "none", "reason": "Insufficient candle data"}
        
        # Initialize components
        self.market_structure = MarketStructure(setup_candles)
        self.order_blocks = OrderBlocks(setup_candles)
        self.fvg = FairValueGaps(setup_candles)
        self.liquidity_sweep = LiquiditySweep(setup_candles, entry_candles)
        
        # 1. Detect market structure (BOS/CHoCH on 15m)
        structure = self.market_structure.detect_structure(lookback=10)
        
        # 2. Find order blocks
        obs = self.order_blocks.find_order_blocks()
        
        # 3. Find fair value gaps
        fvgs = self.fvg.find_fvgs()
        
        # 4. Check for liquidity sweep
        sweep = self.liquidity_sweep.check_sweep(bias=bias)
        
        # 5. Check OB + FVG confluence
        confluence = self._check_confluence(obs, fvgs, bias)
        
        # 6. Determine if we have a valid setup
        if not sweep.get('sweep_found', False):
            return {"signal": "none", "reason": "No liquidity sweep detected", "setup": {}}
        
        if confluence['score'] < 2:  # Need at least 2 confluence factors
            return {"signal": "none", "reason": "Insufficient confluence", "setup": {}}
        
        # Build setup result
        signal = "long" if bias == "bullish" else "short"
        
        setup = {
            "signal": signal,
            "bias": bias,
            "structure": structure,
            "sweep": sweep,
            "confluence": confluence,
            "order_blocks": obs,
            "fvgs": fvgs,
            "setup": {
                "entry_zone": confluence.get('entry_zone', {}),
                "stop_loss": confluence.get('stop_loss', 0),
                "take_profit_1": confluence.get('take_profit_1', 0),
                "take_profit_2": confluence.get('take_profit_2', 0),
                "take_profit_3": confluence.get('take_profit_3', 0),
            },
        }
        
        logger.info(
            "Setup scan: %s signal=%s confluence=%d/5",
            symbol, signal, confluence['score']
        )
        return setup

    # ------------------------------------------------------------------
    # Stage 2: Entry Confirmation (1m)
    # ------------------------------------------------------------------

    def confirm_entry(
        self,
        signal: Dict[str, Any],
        ltf_candles: pd.DataFrame,  # 1m candles
        indicators: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Confirm entry on LTF with indicators.
        
        Parameters
        ----------
        signal : dict
            Setup result from scan_for_setup.
        ltf_candles : pd.DataFrame
            1m OHLCV candles.
        indicators : dict
            Indicator values from IndicatorEngine.
        
        Returns
        -------
        dict
            Entry confirmation with price, SL, TPs, and confirmation status.
        """
        if ltf_candles.empty or not indicators:
            return {"confirmed": False, "reason": "No LTF data or indicators"}
        
        setup = signal.get('setup', {})
        entry_zone = setup.get('entry_zone', {})
        
        # Get latest indicator values
        ema_9 = indicators.get('ema9', 0)
        ema_21 = indicators.get('ema21', 0)
        rsi = indicators.get('rsi', 50)
        volume_avg = indicators.get('volume_avg', 0)
        spread = indicators.get('spread', 0)
        spread_avg = indicators.get('spread_avg', 0)
        
        # Current price
        current_price = ltf_candles['close'].iloc[-1]
        
        # 1. EMA Crossover confirmation
        ema_cross = self._check_ema_cross(ltf_candles, signal['signal'])
        
        # 2. RSI filter (not overbought/oversold)
        rsi_valid = 30 < rsi < 70
        
        # 3. Volume confirmation (>1.5x average)
        current_volume = ltf_candles['volume'].iloc[-1] if 'volume' in ltf_candles.columns else 0
        volume_spike = current_volume > volume_avg * 1.5 if volume_avg > 0 else False
        
        # 4. Spread check (not too wide)
        spread_ok = spread < spread_avg * 2 if spread_avg > 0 else True
        
        # 5. Price in entry zone
        in_zone = self._price_in_zone(current_price, entry_zone)
        
        # All confirmations must pass
        confirmations = {
            'ema_cross': ema_cross,
            'rsi_valid': rsi_valid,
            'volume_spike': volume_spike,
            'spread_ok': spread_ok,
            'in_zone': in_zone,
        }
        
        all_confirmed = all(confirmations.values())
        
        if not all_confirmed:
            failed = [k for k, v in confirmations.items() if not v]
            return {
                "confirmed": False,
                "reason": f"Entry confirmation failed: {', '.join(failed)}",
                "confirmations": confirmations,
            }
        
        # Calculate entry, SL, TPs
        entry_price = current_price
        stop_loss = setup.get('stop_loss', entry_price * 0.99)  # Default 1% SL
        
        # Risk:Reward ratios
        risk = abs(entry_price - stop_loss)
        tp1 = entry_price + risk * 1 if signal['signal'] == 'long' else entry_price - risk * 1
        tp2 = entry_price + risk * 2 if signal['signal'] == 'long' else entry_price - risk * 2
        tp3 = entry_price + risk * 3 if signal['signal'] == 'long' else entry_price - risk * 3
        
        result = {
            "confirmed": True,
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit_1": round(tp1, 2),
            "take_profit_2": round(tp2, 2),
            "take_profit_3": round(tp3, 2),
            "confirmations": confirmations,
            "current_price": current_price,
            "rsi": rsi,
            "volume_ratio": round(current_volume / volume_avg, 2) if volume_avg > 0 else 0,
        }
        
        logger.info(
            "Entry confirmed: entry=%.2f SL=%.2f TP1=%.2f TP2=%.2f TP3=%.2f",
            entry_price, stop_loss, tp1, tp2, tp3
        )
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_confluence(
        self,
        obs: list,
        fvgs: list,
        bias: str,
    ) -> Dict[str, Any]:
        """Check for OB + FVG confluence and score it.
        
        Returns:
            dict with 'score' (0-5), 'entry_zone', 'stop_loss', 'take_profits'
        """
        score = 0
        entry_zone = {"min": 0, "max": 0}
        stop_loss = 0
        tp1 = tp2 = tp3 = 0
        
        # Factor 1: Has valid OB
        if obs and len(obs) > 0:
            score += 1
            # Use most recent OB as entry zone
            ob = obs[-1]
            entry_zone = {
                "min": min(ob.get('high', 0), ob.get('low', 0)),
                "max": max(ob.get('high', 0), ob.get('low', 0)),
            }
            # SL beyond OB
            if bias == 'bullish':
                stop_loss = ob.get('low', 0) * 0.999
            else:
                stop_loss = ob.get('high', 0) * 1.001
        
        # Factor 2: Has valid FVG
        if fvgs and len(fvgs) > 0:
            score += 1
            fvg = fvgs[-1]
            # FVG overlaps with OB zone
            if entry_zone['min'] > 0:
                fvg_min = min(fvg.get('high', 0), fvg.get('low', 0))
                fvg_max = max(fvg.get('high', 0), fvg.get('low', 0))
                overlap = not (fvg_max < entry_zone['min'] or fvg_min > entry_zone['max'])
                if overlap:
                    score += 1  # Bonus for overlap
                    entry_zone = {
                        "min": max(entry_zone['min'], fvg_min),
                        "max": min(entry_zone['max'], fvg_max),
                    }
        
        # Factor 3: Structure aligned
        if bias in ['bullish', 'bearish']:
            score += 1
        
        # Factor 4: Entry zone is valid
        if entry_zone['min'] > 0 and entry_zone['max'] > entry_zone['min']:
            score += 1
        
        # Calculate TPs based on entry zone midpoint
        if entry_zone['min'] > 0:
            mid = (entry_zone['min'] + entry_zone['max']) / 2
            risk = abs(mid - stop_loss) if stop_loss > 0 else mid * 0.01
            if bias == 'bullish':
                tp1 = mid + risk * 1
                tp2 = mid + risk * 2
                tp3 = mid + risk * 3
            else:
                tp1 = mid - risk * 1
                tp2 = mid - risk * 2
                tp3 = mid - risk * 3
        
        return {
            'score': score,
            'entry_zone': entry_zone,
            'stop_loss': round(stop_loss, 2),
            'take_profit_1': round(tp1, 2),
            'take_profit_2': round(tp2, 2),
            'take_profit_3': round(tp3, 2),
        }

    def _check_ema_cross(self, candles: pd.DataFrame, signal: str) -> bool:
        """Check for EMA 9/21 crossover confirmation.
        
        For long: EMA 9 > EMA 21 and price > EMA 9
        For short: EMA 9 < EMA 21 and price < EMA 9
        """
        if len(candles) < 21:
            return False
        
        ema_9 = candles['close'].ewm(span=9, adjust=False).mean()
        ema_21 = candles['close'].ewm(span=21, adjust=False).mean()
        
        current_price = candles['close'].iloc[-1]
        ema_9_current = ema_9.iloc[-1]
        ema_21_current = ema_21.iloc[-1]
        
        if signal == 'long':
            return ema_9_current > ema_21_current and current_price > ema_9_current
        else:
            return ema_9_current < ema_21_current and current_price < ema_9_current

    def _price_in_zone(self, price: float, zone: Dict[str, float]) -> bool:
        """Check if price is within the entry zone."""
        if not zone or zone.get('min', 0) == 0:
            return True  # No zone defined = always valid
        return zone['min'] <= price <= zone['max']
