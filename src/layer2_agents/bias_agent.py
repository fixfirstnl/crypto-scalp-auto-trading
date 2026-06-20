"""bias_agent.py — Higher-Timeframe Bias Detection Agent.

Pure rule-based logic wrapped as a CrewAI tool.  No LLM reasoning is used for
the critical path; the agent operates on vectorised BOS/CHoCH detection via
:class:`MarketStructure`.

Expected output schema
----------------------
    {
        "bias": "bullish" | "bearish" | "neutral",
        "confidence": 0.0-100.0,
        "structure": { ... MarketStructure.detect_structure() ... },
        "timestamp": "2026-06-20T12:00:00+00:00",
    }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

import pandas as pd

from layer1_data import DataCache, IndicatorEngine
from strategy import MarketStructure

logger = logging.getLogger(__name__)


class BiasAgent:
    """Higher-Timeframe Analyst — determines bullish / bearish / neutral bias.

    Parameters
    ----------
    data_cache : DataCache
        Layer-1 cache for OHLCV retrieval.
    indicator_engine : IndicatorEngine
        Layer-1 indicator calculator (used for optional EMA-slope confirmation).
    """

    def __init__(
        self,
        data_cache: DataCache,
        indicator_engine: IndicatorEngine,
    ) -> None:
        self.data_cache = data_cache
        self.indicator_engine = indicator_engine

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def analyze(self, symbol: str) -> Dict[str, Any]:
        """Determine HTF market bias for *symbol*.

        Pipeline
        --------
        1. Fetch 1H candles (primary) and 4H candles (fallback).
        2. Run :meth:`MarketStructure.detect_structure`.
        3. Compute confidence from structure strength + recency.
        4. If 1H is neutral, try 4H.

        Parameters
        ----------
        symbol : str
            CCXT unified symbol (e.g. ``'BTC/USDT:USDT'``).

        Returns
        -------
        dict
            ``bias``, ``confidence``, ``structure``, ``timestamp``.
        """
        try:
            candles_1h = self.data_cache.get_candles(symbol, "1h")
            if candles_1h.empty or len(candles_1h) < 20:
                logger.warning("BiasAgent: no 1H data for %s", symbol)
                return self._neutral_result("No 1H candles available")

            # --- Primary analysis on 1H ---
            ms = MarketStructure(candles_1h)
            structure = ms.detect_structure(lookback=10)

            bias = structure.get("bias", "neutral")
            strength = float(structure.get("strength", 0.0))

            confidence = self._compute_confidence(structure, candles_1h, strength)

            # --- Fallback to 4H if 1H is weak ---
            if bias == "neutral" or confidence < 30.0:
                candles_4h = self.data_cache.get_candles(symbol, "4h")
                if not candles_4h.empty and len(candles_4h) >= 20:
                    ms_4h = MarketStructure(candles_4h)
                    structure_4h = ms_4h.detect_structure(lookback=10)
                    bias_4h = structure_4h.get("bias", "neutral")
                    if bias_4h != "neutral":
                        bias = bias_4h
                        strength_4h = float(structure_4h.get("strength", 0.0))
                        confidence = self._compute_confidence(
                            structure_4h, candles_4h, strength_4h
                        )
                        structure = structure_4h

            result = {
                "bias": bias,
                "confidence": round(confidence, 2),
                "structure": structure,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            logger.info(
                "BiasAgent: %s bias=%s confidence=%.1f", symbol, bias, confidence
            )
            return result

        except Exception as exc:
            logger.error("BiasAgent analyze failed for %s: %s", symbol, exc)
            return self._neutral_result(str(exc))

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_confidence(
        structure: Dict[str, Any], candles: pd.DataFrame, strength: float
    ) -> float:
        """Confidence = structure strength × recency factor, capped at 100."""
        max_idx = len(candles) - 1
        if max_idx <= 0:
            return 0.0

        last_bos = structure.get("last_bos")
        last_choch = structure.get("last_choch")
        latest_event_idx = -1

        if last_bos and isinstance(last_bos, dict):
            latest_event_idx = max(latest_event_idx, int(last_bos.get("index", -1)))
        if last_choch and isinstance(last_choch, dict):
            latest_event_idx = max(
                latest_event_idx, int(last_choch.get("index", -1))
            )

        recency = 0.5
        if latest_event_idx >= 0:
            recency = latest_event_idx / max_idx

        return min(strength * recency * 200.0, 100.0)

    @staticmethod
    def _neutral_result(reason: str) -> Dict[str, Any]:
        return {
            "bias": "neutral",
            "confidence": 0.0,
            "structure": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": reason,
        }
