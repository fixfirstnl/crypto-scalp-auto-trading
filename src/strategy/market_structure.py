"""Market Structure Detection — BOS/CHoCH & Swing Points.

Implements the Higher-Timeframe (HTF) bias engine using:
    - Break of Structure (BOS) — continuation signal
    - Change of Character (CHoCH) — reversal signal
    - Swing high/low detection via local extrema
    - Premium/Discount classification relative to swing points

All calculations are vectorized via pandas/numpy for sub-second performance.
"""

from __future__ import annotations

import logging
from typing import List, Tuple, Dict, Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MarketStructure:
    """Detect market structure shifts (BOS, CHoCH) and swing points.

    Parameters
    ----------
    candles : pd.DataFrame
        Must contain columns: ``open``, ``high``, ``low``, ``close``, ``volume``.
        Index should be a monotonic DatetimeIndex.
    """

    def __init__(self, candles: pd.DataFrame) -> None:
        if not isinstance(candles, pd.DataFrame):
            raise TypeError("candles must be a pandas DataFrame")
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(candles.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        self.candles = candles.copy()
        self._swing_highs: List[Dict[str, Any]] = []
        self._swing_lows: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def find_swing_points(self, lookback: int = 5) -> Tuple[List[Dict], List[Dict]]:
        """Find local swing highs and lows using a rolling window.

        A swing high is a candle whose ``high`` is strictly greater than the
        ``high`` of ``lookback`` candles on both sides.  Swing low is the
        symmetric condition on ``low``.

        Returns
        -------
        Tuple[swing_highs, swing_lows]
            Each element is a list of dicts with keys:
            ``index`` (int), ``price`` (float), ``time`` (pd.Timestamp).
        """
        highs = self.candles["high"].values
        lows = self.candles["low"].values
        times = self.candles.index

        # Vectorised local-max / local-min using rolling
        roll_max = pd.Series(highs).rolling(window=2 * lookback + 1, center=True).max()
        roll_min = pd.Series(lows).rolling(window=2 * lookback + 1, center=True).min()

        swing_high_mask = (highs == roll_max.values) & (
            pd.Series(highs).diff(lookback).fillna(0) > 0
        )
        swing_low_mask = (lows == roll_min.values) & (
            pd.Series(lows).diff(lookback).fillna(0) < 0
        )

        # Exclude edges where the window isn't fully formed
        valid = np.arange(lookback, len(self.candles) - lookback)
        swing_high_mask[:lookback] = False
        swing_high_mask[-lookback:] = False
        swing_low_mask[:lookback] = False
        swing_low_mask[-lookback:] = False

        self._swing_highs = [
            {"index": int(i), "price": float(highs[i]), "time": times[i]}
            for i in np.where(swing_high_mask)[0]
            if i in valid
        ]
        self._swing_lows = [
            {"index": int(i), "price": float(lows[i]), "time": times[i]}
            for i in np.where(swing_low_mask)[0]
            if i in valid
        ]

        logger.debug(
            "Found %d swing highs and %d swing lows (lookback=%d)",
            len(self._swing_highs),
            len(self._swing_lows),
            lookback,
        )
        return self._swing_highs, self._swing_lows

    def detect_bos(self, lookback: int = 5) -> List[Dict[str, Any]]:
        """Detect Break of Structure events.

        A **bullish BOS** occurs when the close of a candle exceeds the most
        recent swing high.  A **bearish BOS** occurs when the close drops below
        the most recent swing low.  Strength is measured as the ratio of the
        break candle's volume to the rolling average volume.

        Returns
        -------
        List[dict]
            Each dict: ``index``, ``price``, ``direction`` (``'bullish'`` |
            ``'bearish'``), ``strength`` (float), ``time``.
        """
        if not self._swing_highs or not self._swing_lows:
            self.find_swing_points(lookback)

        closes = self.candles["close"].values
        volumes = self.candles["volume"].values
        times = self.candles.index
        avg_vol = float(np.mean(volumes))

        bos_events: List[Dict[str, Any]] = []
        last_sh_idx = 0
        last_sl_idx = 0

        for i in range(1, len(closes)):
            # Advance swing pointers
            while last_sh_idx < len(self._swing_highs) and self._swing_highs[last_sh_idx]["index"] < i:
                last_sh_idx += 1
            while last_sl_idx < len(self._swing_lows) and self._swing_lows[last_sl_idx]["index"] < i:
                last_sl_idx += 1

            # Need at least one prior swing point
            if last_sh_idx == 0 or last_sl_idx == 0:
                continue

            prev_sh = self._swing_highs[last_sh_idx - 1]
            prev_sl = self._swing_lows[last_sl_idx - 1]

            # Bullish BOS: close above prior swing high
            if closes[i] > prev_sh["price"]:
                strength = (volumes[i] / avg_vol) if avg_vol > 0 else 1.0
                bos_events.append(
                    {
                        "index": int(i),
                        "price": float(closes[i]),
                        "direction": "bullish",
                        "strength": float(strength),
                        "time": times[i],
                    }
                )
            # Bearish BOS: close below prior swing low
            elif closes[i] < prev_sl["price"]:
                strength = (volumes[i] / avg_vol) if avg_vol > 0 else 1.0
                bos_events.append(
                    {
                        "index": int(i),
                        "price": float(closes[i]),
                        "direction": "bearish",
                        "strength": float(strength),
                        "time": times[i],
                    }
                )

        logger.info("Detected %d BOS events (lookback=%d)", len(bos_events), lookback)
        return bos_events

    def detect_choch(self, lookback: int = 5) -> List[Dict[str, Any]]:
        """Detect Change of Character events.

        A **bullish CHoCH** is the first close above a prior swing high *after*
        a confirmed bearish BOS (i.e., trend flip).  A **bearish CHoCH** is the
        first close below a prior swing low *after* a confirmed bullish BOS.

        This is the first violation of the *established* structure, signalling
        a potential reversal rather than continuation.

        Returns
        -------
        List[dict]
            Same schema as :meth:`detect_bos`.
        """
        bos_events = self.detect_bos(lookback)
        if not bos_events:
            return []

        closes = self.candles["close"].values
        volumes = self.candles["volume"].values
        times = self.candles.index
        avg_vol = float(np.mean(volumes)) if np.mean(volumes) > 0 else 1.0

        choch_events: List[Dict[str, Any]] = []
        # Track the most recent BOS direction
        last_bos_dir: str | None = None
        last_bos_idx = -1

        for i in range(1, len(closes)):
            # Update last BOS state
            for bos in bos_events:
                if bos["index"] == i:
                    last_bos_dir = bos["direction"]
                    last_bos_idx = i

            if last_bos_dir is None or last_bos_idx < 0:
                continue

            # Need swing points that occurred *before* the last BOS
            valid_sh = [s for s in self._swing_highs if s["index"] < last_bos_idx]
            valid_sl = [s for s in self._swing_lows if s["index"] < last_bos_idx]
            if not valid_sh or not valid_sl:
                continue

            prev_sh = valid_sh[-1]
            prev_sl = valid_sl[-1]

            # Bearish CHoCH: close below prior swing low after bullish BOS
            if last_bos_dir == "bullish" and closes[i] < prev_sl["price"]:
                strength = volumes[i] / avg_vol
                choch_events.append(
                    {
                        "index": int(i),
                        "price": float(closes[i]),
                        "direction": "bearish",
                        "strength": float(strength),
                        "time": times[i],
                    }
                )
                # Reset — we have a new character
                last_bos_dir = None

            # Bullish CHoCH: close above prior swing high after bearish BOS
            elif last_bos_dir == "bearish" and closes[i] > prev_sh["price"]:
                strength = volumes[i] / avg_vol
                choch_events.append(
                    {
                        "index": int(i),
                        "price": float(closes[i]),
                        "direction": "bullish",
                        "strength": float(strength),
                        "time": times[i],
                    }
                )
                last_bos_dir = None

        logger.info("Detected %d CHoCH events (lookback=%d)", len(choch_events), lookback)
        return choch_events

    def detect_structure(self, lookback: int = 10) -> Dict[str, Any]:
        """Aggregate market-structure diagnostic.

        Combines BOS, CHoCH, and swing-point analysis into a single bias
        dictionary suitable for the HTF bias engine.

        Returns
        -------
        dict
            Keys:
            - ``bias``: ``'bullish'`` | ``'bearish'`` | ``'neutral'``
            - ``last_bos``: most recent BOS event or ``None``
            - ``last_choch``: most recent CHoCH event or ``None``
            - ``swing_highs``: list of swing highs
            - ``swing_lows``: list of swing lows
            - ``strength``: composite structure strength (0.0 – 1.0+)
        """
        # Ensure fresh state
        self.find_swing_points(lookback)
        bos = self.detect_bos(lookback)
        choch = self.detect_choch(lookback)

        last_bos = bos[-1] if bos else None
        last_choch = choch[-1] if choch else None

        # Determine bias
        if last_choch and last_bos:
            # CHoCH is more recent → reversal bias; BOS more recent → continuation
            if last_choch["index"] > last_bos["index"]:
                bias = last_choch["direction"]  # bullish or bearish
            else:
                bias = last_bos["direction"]
        elif last_bos:
            bias = last_bos["direction"]
        elif last_choch:
            bias = last_choch["direction"]
        else:
            bias = "neutral"

        # Composite strength = avg of last BOS & CHoCH strengths, capped at 1.0
        strengths = []
        if last_bos:
            strengths.append(min(last_bos["strength"], 3.0) / 3.0)
        if last_choch:
            strengths.append(min(last_choch["strength"], 3.0) / 3.0)
        strength = float(np.mean(strengths)) if strengths else 0.0

        result = {
            "bias": bias,
            "last_bos": last_bos,
            "last_choch": last_choch,
            "swing_highs": self._swing_highs,
            "swing_lows": self._swing_lows,
            "strength": strength,
        }
        logger.info("Market structure: bias=%s, strength=%.2f", bias, strength)
        return result

    def get_premium_discount(self, current_price: float) -> str:
        """Classify price as Premium, Discount, or Equilibrium.

        * Premium  – price is within 10 % of the most recent swing high.
        * Discount – price is within 10 % of the most recent swing low.
        * Equilibrium – neither.

        Parameters
        ----------
        current_price : float
            The price to classify.

        Returns
        -------
        str
            ``'premium'`` | ``'discount'`` | ``'equilibrium'``
        """
        if not self._swing_highs or not self._swing_lows:
            self.find_swing_points()

        if not self._swing_highs or not self._swing_lows:
            return "equilibrium"

        last_high = self._swing_highs[-1]["price"]
        last_low = self._swing_lows[-1]["price"]
        range_size = last_high - last_low
        if range_size <= 0:
            return "equilibrium"

        # Distance as % of range
        dist_high = (last_high - current_price) / range_size
        dist_low = (current_price - last_low) / range_size

        threshold = 0.10  # 10 % of the range
        if dist_high <= threshold:
            return "premium"
        if dist_low <= threshold:
            return "discount"
        return "equilibrium"
