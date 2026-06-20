"""signal_agent.py — Entry Signal Generation Agent.

Scans for liquidity sweeps + OB/FVG confluence + EMA cross + RSI setups on
15m/5m/1m timeframes.  Pure rule-based; no LLM on the hot path.

Expected output schema
----------------------
    {
        "signal": "long" | "short" | "none",
        "entry": float,
        "stop": float,
        "tp1": float, "tp2": float, "tp3": float,
        "confidence": 0.0-100.0,
        "setup": { ... ICTSMCStrategy output ... },
        "timestamp": str,
    }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from src.layer1_data import DataCache, IndicatorEngine
from src.strategy import ICTSMCStrategy

logger = logging.getLogger(__name__)


class SignalAgent:
    """Entry Signal Generator — finds ICT/SMC scalp setups.

    Parameters
    ----------
    data_cache : DataCache
        Layer-1 cache.
    indicator_engine : IndicatorEngine
        Layer-1 indicator calculator.
    strategy : ICTSMCStrategy
        Strategy orchestrator with ``scan_for_setup`` and ``confirm_entry``.
    """

    def __init__(
        self,
        data_cache: DataCache,
        indicator_engine: IndicatorEngine,
        strategy: ICTSMCStrategy,
    ) -> None:
        self.data_cache = data_cache
        self.indicator_engine = indicator_engine
        self.strategy = strategy

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def generate(
        self, symbol: str, bias: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate an entry signal aligned with *bias*.

        Pipeline
        --------
        1. Fetch 15m (setup) + 5m (entry zone) + 1m (LTF) candles.
        2. ``scan_for_setup`` — liquidity sweep + OB/FVG confluence.
        3. Calculate indicators on 1m candles.
        4. ``confirm_entry`` — EMA cross + RSI + volume + spread checks.
        5. Compute confidence from confluence score + sweep strength.

        Parameters
        ----------
        symbol : str
            CCXT unified symbol.
        bias : dict
            Output of :meth:`BiasAgent.analyze`.

        Returns
        -------
        dict or None
            Signal dict if a valid setup is confirmed, else ``None``.
        """
        try:
            bias_direction = bias.get("bias", "neutral")
            if bias_direction == "neutral":
                logger.info("SignalAgent: neutral bias — no signal for %s", symbol)
                return None

            # --- Fetch multi-timeframe data ---
            candles_15m = self.data_cache.get_candles(symbol, "15m")
            candles_5m = self.data_cache.get_candles(symbol, "5m")
            candles_1m = self.data_cache.get_candles(symbol, "1m")

            if candles_15m.empty or candles_5m.empty or candles_1m.empty:
                logger.warning(
                    "SignalAgent: insufficient LTF data for %s (15m=%s 5m=%s 1m=%s)",
                    symbol,
                    len(candles_15m),
                    len(candles_5m),
                    len(candles_1m),
                )
                return None

            # Minimum bars for EMA 21 + RSI 14
            if len(candles_1m) < 30:
                logger.warning(
                    "SignalAgent: only %d 1m bars for %s (need ≥30)",
                    len(candles_1m),
                    symbol,
                )
                return None

            # --- Stage 1: Setup scan (15m + 5m) ---
            setup_result = self.strategy.scan_for_setup(
                symbol=symbol,
                bias=bias_direction,
                setup_candles=candles_15m,
                entry_candles=candles_5m,
            )

            if setup_result.get("signal", "none") == "none":
                logger.info("SignalAgent: no setup found for %s", symbol)
                return None

            # --- Stage 2: Indicator calculation (1m) ---
            indicators = self.indicator_engine.calculate_all(candles_1m, symbol, "1m")
            if not indicators:
                logger.warning("SignalAgent: indicator calculation failed for %s", symbol)
                return None

            indicator_inputs = self._build_indicator_inputs(indicators, symbol)

            # --- Stage 3: Entry confirmation (1m) ---
            entry_result = self.strategy.confirm_entry(
                signal=setup_result,
                ltf_candles=candles_1m,
                indicators=indicator_inputs,
            )

            if not entry_result.get("confirmed", False):
                logger.info(
                    "SignalAgent: entry not confirmed for %s — %s",
                    symbol,
                    entry_result.get("reason", "unknown"),
                )
                return None

            # --- Stage 4: Confidence scoring ---
            setup = setup_result.get("setup", {})
            confluence_score = setup.get("confluence", {}).get("score", 0.0)
            sweep_strength = float(setup.get("sweep", {}).get("strength", 0.0))

            # Base confidence from confluence + sweep; bonus for clean structure
            confidence = min(
                (confluence_score * 0.5 + sweep_strength * 50.0) * 1.5 + 10.0,
                100.0,
            )

            signal = {
                "symbol": symbol,
                "signal": setup_result["signal"],
                "entry": float(entry_result["entry_price"]),
                "stop": float(entry_result["stop_loss"]),
                "tp1": float(entry_result["take_profit_1"]),
                "tp2": float(entry_result["take_profit_2"]),
                "tp3": float(entry_result["take_profit_3"]),
                "confidence": round(confidence, 2),
                "setup": setup_result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(
                "SignalAgent: %s signal=%s entry=%.2f sl=%.2f conf=%.1f",
                symbol,
                signal["signal"],
                signal["entry"],
                signal["stop"],
                confidence,
            )
            return signal

        except Exception as exc:
            logger.error("SignalAgent generate failed for %s: %s", symbol, exc)
            return None

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _build_indicator_inputs(
        self, indicators: Dict[str, Any], symbol: str
    ) -> Dict[str, float]:
        """Map IndicatorEngine output to the schema expected by ``confirm_entry``."""

        def _last(series: Any) -> float:
            if isinstance(series, pd.Series) and not series.empty:
                return float(series.iloc[-1])
            return 0.0

        ema_9 = _last(indicators.get("ema_9"))
        ema_21 = _last(indicators.get("ema_21"))
        rsi = _last(indicators.get("rsi"))
        volume_avg = _last(indicators.get("volume_sma_20"))

        # Spread from live order book (best-effort)
        spread = 0.0
        spread_avg = 0.0
        try:
            orderbook = self.data_cache.get_orderbook(symbol)
            if (
                orderbook
                and "bids" in orderbook
                and "asks" in orderbook
                and orderbook["bids"]
                and orderbook["asks"]
            ):
                best_bid = float(orderbook["bids"][0][0])
                best_ask = float(orderbook["asks"][0][0])
                if best_bid > 0 and best_ask > 0:
                    spread = best_ask - best_bid
                    spread_avg = spread * 0.8  # rough estimate
        except Exception as exc:
            logger.debug("Spread read failed for %s: %s", symbol, exc)

        return {
            "ema9": ema_9,
            "ema21": ema_21,
            "rsi": rsi,
            "volume_avg": volume_avg,
            "spread": spread,
            "spread_avg": spread_avg,
        }
