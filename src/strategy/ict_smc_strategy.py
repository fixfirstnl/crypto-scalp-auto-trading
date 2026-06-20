"""Main ICT/SMC Strategy Orchestrator.

Wires the full signal-generation pipeline:

    HTF Bias (1H/4H) → Setup Scan (15m) → Entry Confirmation (5m/1m) → Signal

Each stage is isolated so the ConsensusEngine (BiasAgent → SignalAgent →
RiskAgent → ExecAgent) can veto at any point.

Usage:
    strategy = ICTSMCStrategy(data_cache, indicator_engine)
    signal = strategy.generate_signal("BTC/USDT:USDT")
    if signal:
        # pass to RiskAgent / ExecAgent
        ...
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List

import numpy as np
import pandas as pd

from .market_structure import MarketStructure
from .order_blocks import OrderBlocks
from .fair_value_gaps import FairValueGaps
from .liquidity_sweep import LiquiditySweep

logger = logging.getLogger(__name__)


class ICTSMCStrategy:
    """ICT/SMC hybrid scalping strategy orchestrator.

    Parameters
    ----------
    data_cache : Any
        Data-layer cache object (e.g., Redis wrapper) that exposes
        ``get_candles(symbol, timeframe) -> pd.DataFrame``.
    indicator_engine : Any
        Indicator calculator that exposes ``get(symbol, timeframe) -> dict``
        with keys ``ema9``, ``ema21``, ``rsi``, ``vwap``, ``volume_avg``,
        ``spread``, ``spread_avg``.
    """

    def __init__(self, data_cache: Any, indicator_engine: Any) -> None:
        self.data_cache = data_cache
        self.indicator_engine = indicator_engine

    # ------------------------------------------------------------------ #
    #  Stage 1 — HTF Bias
    # ------------------------------------------------------------------ #

    def analyze_bias(self, symbol: str, htf_candles: pd.DataFrame) -> Dict[str, Any]:
        """Determine the Higher-Timeframe market bias.

        Uses :class:`MarketStructure` on 1H or 4H candles to detect BOS/CHoCH
        and derive a bullish / bearish / neutral bias with confidence.

        Parameters
        ----------
        symbol : str
            Trading pair (e.g. ``'BTC/USDT:USDT'``).
        htf_candles : pd.DataFrame
            1H or 4H OHLCV DataFrame.

        Returns
        -------
        dict
            ``bias`` (``'bullish'`` | ``'bearish'`` | ``'neutral'``),
            ``confidence`` (0.0-1.0), ``structure`` (raw MarketStructure output).
        """
        try:
            ms = MarketStructure(htf_candles)
            structure = ms.detect_structure(lookback=10)
        except Exception as exc:
            logger.error("MarketStructure failed for %s: %s", symbol, exc)
            return {"bias": "neutral", "confidence": 0.0, "structure": {}}

        bias = structure.get("bias", "neutral")
        strength = structure.get("strength", 0.0)

        # Confidence = structure strength * recency factor
        last_bos = structure.get("last_bos")
        last_choch = structure.get("last_choch")
        recency = 0.5
        if last_bos or last_choch:
            max_idx = len(htf_candles) - 1
            latest_event_idx = -1
            if last_bos:
                latest_event_idx = max(latest_event_idx, last_bos["index"])
            if last_choch:
                latest_event_idx = max(latest_event_idx, last_choch["index"])
            if max_idx > 0 and latest_event_idx >= 0:
                recency = latest_event_idx / max_idx

        confidence = min(strength * recency * 2.0, 1.0)  # cap at 1.0

        result = {
            "bias": bias,
            "confidence": float(confidence),
            "structure": structure,
        }
        logger.info("HTF bias for %s: %s (confidence=%.2f)", symbol, bias, confidence)
        return result

    # ------------------------------------------------------------------ #
    #  Stage 2 — Setup Scan
    # ------------------------------------------------------------------ #

    def scan_for_setup(
        self,
        symbol: str,
        bias: str,
        setup_candles: pd.DataFrame,
        entry_candles: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Scan for a valid ICT/SMC setup.

        Pipeline:
            1. Detect liquidity sweep on 15m (setup_candles).
            2. Find OB + FVG confluence on 5m (entry_candles).
            3. Check LTF confirmation on 1m/5m.

        Parameters
        ----------
        symbol : str
            Trading pair.
        bias : str
            HTF bias (``'bullish'`` | ``'bearish'`` | ``'neutral'``).
        setup_candles : pd.DataFrame
            15m OHLCV — used for liquidity sweep detection.
        entry_candles : pd.DataFrame
            5m OHLCV — used for OB/FVG confluence and entry zone.

        Returns
        -------
        dict
            ``signal`` (``'long'`` | ``'short'`` | ``'none'``),
            ``setup`` (detailed dict if signal != none).
        """
        if bias == "neutral":
            logger.info("Setup scan for %s: neutral bias — no trade.", symbol)
            return {"signal": "none", "setup": {}}

        # --- Step 1: Liquidity Sweep (15m) ---
        liq = LiquiditySweep(setup_candles)
        if bias == "bullish":
            sweep = liq.detect_sweep_low(threshold=0.005)
            expected_direction = "long"
        else:
            sweep = liq.detect_sweep_high(threshold=0.005)
            expected_direction = "short"

        if not sweep.get("swept", False):
            logger.info("Setup scan for %s: no liquidity sweep detected.", symbol)
            return {"signal": "none", "setup": {}}

        avg_vol_15m = float(np.mean(setup_candles["volume"].values))
        if not liq.is_genuine_sweep(sweep, avg_vol_15m):
            logger.info("Setup scan for %s: sweep not genuine (volume/body check failed).", symbol)
            return {"signal": "none", "setup": {}}

        # --- Step 2: OB + FVG Confluence (5m) ---
        obs = OrderBlocks(entry_candles)
        fvgs = FairValueGaps(entry_candles)

        if bias == "bullish":
            ob_list = obs.find_bullish_order_blocks()
            fvg_list = fvgs.find_bullish_fvgs()
        else:
            ob_list = obs.find_bearish_order_blocks()
            fvg_list = fvgs.find_bearish_fvgs()

        # Build a dummy market_structure for scoring (lightweight)
        ms_dummy = {"bias": bias}
        confluences = obs.find_ob_fvg_confluence(
            bullish=(bias == "bullish"), fvgs=fvg_list
        )
        if not confluences:
            logger.info("Setup scan for %s: no OB+FVG confluence found.", symbol)
            return {"signal": "none", "setup": {}}

        # Pick the highest-scored confluence zone
        best = confluences[0]
        zone = best["confluence_zone"]
        zone_mid = (zone["top"] + zone["bottom"]) / 2.0

        # --- Step 3: LTF Confirmation (check on entry_candles) ---
        # Check if price is currently near the confluence zone
        current_price = float(entry_candles["close"].iloc[-1])
        zone_tol = current_price * 0.005  # 0.5 % of price
        price_near_zone = abs(current_price - zone_mid) <= zone_tol

        if not price_near_zone:
            logger.info(
                "Setup scan for %s: price %.2f too far from zone %.2f (tol=%.2f).",
                symbol, current_price, zone_mid, zone_tol,
            )
            return {"signal": "none", "setup": {}}

        setup = {
            "signal": expected_direction,
            "sweep": sweep,
            "confluence": best,
            "zone": zone,
            "zone_mid": float(zone_mid),
            "current_price": float(current_price),
            "obs_count": len(ob_list),
            "fvgs_count": len(fvg_list),
        }
        logger.info(
            "Setup scan for %s: %s signal detected (zone=%.2f, score=%.1f)",
            symbol, expected_direction, zone_mid, best["score"],
        )
        return {"signal": expected_direction, "setup": setup}

    # ------------------------------------------------------------------ #
    #  Stage 3 — Entry Confirmation
    # ------------------------------------------------------------------ #

    def confirm_entry(
        self,
        signal: Dict[str, Any],
        ltf_candles: pd.DataFrame,
        indicators: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Confirm entry with LTF indicator checks.

        Checks:
            - EMA crossover (9 > 21 for longs, 9 < 21 for shorts)
            - RSI not extreme (longs: RSI > 40; shorts: RSI < 60)
            - Volume > 1.5x average
            - Spread < 2x average

        Parameters
        ----------
        signal : dict
            Output of :meth:`scan_for_setup`.
        ltf_candles : pd.DataFrame
            1m or 5m OHLCV for LTF confirmation.
        indicators : dict
            From ``indicator_engine.get(symbol, timeframe)``:
            ``ema9``, ``ema21``, ``rsi``, ``volume_avg``, ``spread``, ``spread_avg``.

        Returns
        -------
        dict
            ``confirmed`` (bool), ``entry_price``, ``stop_loss``,
            ``take_profit_1``, ``take_profit_2``, ``take_profit_3``,
            ``size`` (placeholder — RiskAgent will override),
            ``reason`` (str).
        """
        if signal.get("signal", "none") == "none":
            return {"confirmed": False, "reason": "No signal to confirm"}

        direction = signal["signal"]  # 'long' or 'short'
        setup = signal["setup"]
        zone = setup["zone"]
        zone_mid = setup["zone_mid"]

        # Indicator extraction with safe defaults
        ema9 = indicators.get("ema9", 0.0)
        ema21 = indicators.get("ema21", 0.0)
        rsi = indicators.get("rsi", 50.0)
        vol_avg = indicators.get("volume_avg", 0.0)
        spread = indicators.get("spread", 0.0)
        spread_avg = indicators.get("spread_avg", 0.0)

        current_price = float(ltf_candles["close"].iloc[-1])
        current_vol = float(ltf_candles["volume"].iloc[-1])

        reasons: List[str] = []

        # 1. EMA cross check
        ema_aligned = (direction == "long" and ema9 > ema21) or (direction == "short" and ema9 < ema21)
        if not ema_aligned:
            reasons.append(f"EMA not aligned (9={ema9:.2f}, 21={ema21:.2f})")

        # 2. RSI check
        if direction == "long" and rsi < 40:
            reasons.append(f"RSI too low for long ({rsi:.1f})")
        if direction == "short" and rsi > 60:
            reasons.append(f"RSI too high for short ({rsi:.1f})")

        # 3. Volume check
        if vol_avg > 0 and current_vol < 1.5 * vol_avg:
            reasons.append(f"Volume too low ({current_vol:.0f} < {1.5*vol_avg:.0f})")

        # 4. Spread check
        if spread_avg > 0 and spread > 2.0 * spread_avg:
            reasons.append(f"Spread too wide ({spread:.4f} > {2.0*spread_avg:.4f})")

        if reasons:
            reason_str = "; ".join(reasons)
            logger.info("Entry NOT confirmed for %s: %s", direction, reason_str)
            return {"confirmed": False, "reason": reason_str}

        # --- Entry price & Stop Loss ---
        # Entry: limit order at zone_mid (or market on strong momentum)
        entry_price = zone_mid

        # SL: below OB low for longs, above OB high for shorts
        ob = setup["confluence"]["ob"]
        if direction == "long":
            stop_loss = min(ob["low"], zone["bottom"]) * 0.999  # 0.1 % buffer below
        else:
            stop_loss = max(ob["high"], zone["top"]) * 1.001  # 0.1 % buffer above

        # R-multiple targets
        r_targets = self.get_r_multiples(entry_price, stop_loss, direction)

        result = {
            "confirmed": True,
            "entry_price": float(entry_price),
            "stop_loss": float(stop_loss),
            "take_profit_1": r_targets["tp1"],
            "take_profit_2": r_targets["tp2"],
            "take_profit_3": r_targets["tp3"],
            "size": 0.0,  # placeholder — RiskAgent calculates this
            "reason": "All checks passed",
        }
        logger.info(
            "Entry CONFIRMED: %s @ %.2f, SL=%.2f, TP1=%.2f, TP2=%.2f, TP3=%.2f",
            direction, entry_price, stop_loss, r_targets["tp1"], r_targets["tp2"], r_targets["tp3"],
        )
        return result

    # ------------------------------------------------------------------ #
    #  Full Pipeline
    # ------------------------------------------------------------------ #

    def generate_signal(self, symbol: str) -> Dict[str, Any] | None:
        """Orchestrate the full signal-generation pipeline.

        1. Fetch HTF (1H/4H) candles → HTF bias.
        2. Fetch 15m setup candles → liquidity sweep.
        3. Fetch 5m entry candles → OB/FVG confluence.
        4. Fetch 1m LTF candles + indicators → entry confirmation.
        5. Return complete signal or None.

        Parameters
        ----------
        symbol : str
            Trading pair (e.g. ``'BTC/USDT:USDT'``).

        Returns
        -------
        dict or None
            Complete signal dict if all stages pass, otherwise ``None``.
        """
        logger.info("Generating signal for %s ...", symbol)

        # 1. HTF Bias
        try:
            htf_candles = self.data_cache.get_candles(symbol, "1h")
        except Exception as exc:
            logger.error("Failed to fetch HTF candles for %s: %s", symbol, exc)
            return None

        bias_result = self.analyze_bias(symbol, htf_candles)
        if bias_result["bias"] == "neutral" or bias_result["confidence"] < 0.3:
            logger.info("Signal for %s: insufficient bias confidence.", symbol)
            return None

        # 2. Setup Scan (15m)
        try:
            setup_candles = self.data_cache.get_candles(symbol, "15m")
            entry_candles = self.data_cache.get_candles(symbol, "5m")
        except Exception as exc:
            logger.error("Failed to fetch setup candles for %s: %s", symbol, exc)
            return None

        setup_result = self.scan_for_setup(
            symbol, bias_result["bias"], setup_candles, entry_candles
        )
        if setup_result["signal"] == "none":
            return None

        # 3. Entry Confirmation (1m LTF)
        try:
            ltf_candles = self.data_cache.get_candles(symbol, "1m")
            indicators = self.indicator_engine.get(symbol, "1m")
        except Exception as exc:
            logger.error("Failed to fetch LTF data for %s: %s", symbol, exc)
            return None

        entry_result = self.confirm_entry(setup_result, ltf_candles, indicators)
        if not entry_result["confirmed"]:
            return None

        # Assemble final signal
        final_signal = {
            "symbol": symbol,
            "direction": setup_result["signal"],
            "bias": bias_result["bias"],
            "bias_confidence": bias_result["confidence"],
            "entry_price": entry_result["entry_price"],
            "stop_loss": entry_result["stop_loss"],
            "take_profit_1": entry_result["take_profit_1"],
            "take_profit_2": entry_result["take_profit_2"],
            "take_profit_3": entry_result["take_profit_3"],
            "size": entry_result["size"],  # RiskAgent will override
            "setup": setup_result["setup"],
            "reason": entry_result["reason"],
            "timestamp": pd.Timestamp.utcnow().isoformat(),
        }
        logger.info("Final signal generated for %s: %s", symbol, final_signal)
        return final_signal

    # ------------------------------------------------------------------ #
    #  Utilities
    # ------------------------------------------------------------------ #

    def get_r_multiples(
        self, entry: float, stop_loss: float, direction: str
    ) -> Dict[str, float]:
        """Calculate 1R, 2R, and 3R profit targets.

        Parameters
        ----------
        entry : float
            Entry price.
        stop_loss : float
            Stop-loss price.
        direction : str
            ``'long'`` or ``'short'``.

        Returns
        -------
        dict
            ``tp1`` (1R), ``tp2`` (2R), ``tp3`` (3R).
        """
        if direction == "long":
            risk = entry - stop_loss
            if risk <= 0:
                logger.warning("Long SL %.4f is above entry %.4f — invalid.", stop_loss, entry)
                risk = entry * 0.005  # fallback 0.5 % risk
            return {
                "tp1": float(entry + risk * 1.0),
                "tp2": float(entry + risk * 2.0),
                "tp3": float(entry + risk * 3.0),
            }
        else:  # short
            risk = stop_loss - entry
            if risk <= 0:
                logger.warning("Short SL %.4f is below entry %.4f — invalid.", stop_loss, entry)
                risk = entry * 0.005
            return {
                "tp1": float(entry - risk * 1.0),
                "tp2": float(entry - risk * 2.0),
                "tp3": float(entry - risk * 3.0),
            }
