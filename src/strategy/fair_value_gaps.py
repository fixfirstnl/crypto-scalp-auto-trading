"""Fair Value Gap (FVG) Detection — 3-Candle Imbalance Zones.

A Fair Value Gap is a 3-candle pattern where the wicks of the first and third
candles do not overlap, indicating aggressive buying/selling that left an
imbalanced zone likely to be revisited.

All detection is vectorised via pandas/numpy.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FairValueGaps:
    """Identify and score Fair Value Gaps.

    Parameters
    ----------
    candles : pd.DataFrame
        Must contain ``open``, ``high``, ``low``, ``close``, ``volume``.
    """

    def __init__(self, candles: pd.DataFrame) -> None:
        if not isinstance(candles, pd.DataFrame):
            raise TypeError("candles must be a pandas DataFrame")
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(candles.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        self.candles = candles.copy()
        self._bullish_fvgs: List[Dict[str, Any]] = []
        self._bearish_fvgs: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def find_bullish_fvgs(self, min_gap_size: float = 0.001) -> List[Dict[str, Any]]:
        """Find bullish Fair Value Gaps.

        A **bullish FVG** is a 3-candle pattern where:
            ``candle[0].low > candle[2].high``
        The gap between candle 0 low and candle 2 high is the unfilled zone.

        Parameters
        ----------
        min_gap_size : float
            Minimum gap as a fraction of price (default 0.1 %).

        Returns
        -------
        List[dict]
            Each dict: ``index`` (candle 2 index), ``top``, ``bottom``,
            ``size``, ``fill_percentage``, ``time``.
        """
        opens = self.candles["open"].values
        highs = self.candles["high"].values
        lows = self.candles["low"].values
        closes = self.candles["close"].values
        times = self.candles.index

        fvgs: List[Dict[str, Any]] = []
        # Need 3 consecutive candles; we label the pattern by the 3rd candle index
        for i in range(2, len(closes)):
            c0_low = lows[i - 2]
            c2_high = highs[i]

            # Bullish FVG: candle 0 low > candle 2 high
            if c0_low > c2_high:
                gap_size = c0_low - c2_high
                if gap_size / closes[i] < min_gap_size:
                    continue

                fvgs.append(
                    {
                        "index": int(i),
                        "top": float(c0_low),
                        "bottom": float(c2_high),
                        "size": float(gap_size),
                        "fill_percentage": 0.0,  # fresh
                        "time": times[i],
                    }
                )

        self._bullish_fvgs = fvgs
        logger.info("Found %d bullish FVGs (min_gap=%.4f)", len(fvgs), min_gap_size)
        return fvgs

    def find_bearish_fvgs(self, min_gap_size: float = 0.001) -> List[Dict[str, Any]]:
        """Find bearish Fair Value Gaps.

        A **bearish FVG** is a 3-candle pattern where:
            ``candle[0].high < candle[2].low``
        The gap between candle 0 high and candle 2 low is the unfilled zone.

        Parameters & Returns — same as :meth:`find_bullish_fvgs`.
        """
        opens = self.candles["open"].values
        highs = self.candles["high"].values
        lows = self.candles["low"].values
        closes = self.candles["close"].values
        times = self.candles.index

        fvgs: List[Dict[str, Any]] = []
        for i in range(2, len(closes)):
            c0_high = highs[i - 2]
            c2_low = lows[i]

            if c0_high < c2_low:
                gap_size = c2_low - c0_high
                if gap_size / closes[i] < min_gap_size:
                    continue

                fvgs.append(
                    {
                        "index": int(i),
                        "top": float(c2_low),
                        "bottom": float(c0_high),
                        "size": float(gap_size),
                        "fill_percentage": 0.0,
                        "time": times[i],
                    }
                )

        self._bearish_fvgs = fvgs
        logger.info("Found %d bearish FVGs (min_gap=%.4f)", len(fvgs), min_gap_size)
        return fvgs

    def score_fvg(self, fvg: Dict[str, Any], market_structure: Dict[str, Any]) -> float:
        """Score a Fair Value Gap for quality (0-100).

        Criteria:
            1. **HTF bias alignment** (+30 pts)
            2. **Gap size** (+30 pts) — larger = more significant imbalance
            3. **Fill status** (+20 pts) — fresh (0 % fill) = best
            4. **Recency** (+20 pts) — more recent = higher probability

        Parameters
        ----------
        fvg : dict
            FVG dict from the find_* methods.
        market_structure : dict
            Output of :meth:`MarketStructure.detect_structure`.

        Returns
        -------
        float
            Composite score 0-100.
        """
        score = 0.0
        bias = market_structure.get("bias", "neutral")

        # Determine direction from gap orientation
        is_bullish = fvg["top"] > fvg["bottom"]  # always true, but semantics help
        # Bullish FVG: top > bottom, expecting price to come back up through it
        # For scoring, bullish FVG aligns with bullish bias
        fvg_direction = "bullish" if is_bullish else "bearish"

        if bias == fvg_direction:
            score += 30.0
        elif bias == "neutral":
            score += 15.0

        # Gap size (relative to price)
        mid_price = (fvg["top"] + fvg["bottom"]) / 2.0
        size_ratio = fvg["size"] / mid_price
        score += min(size_ratio * 500, 30.0)  # cap at 30

        # Fill status: 0% fill = 20 pts, 100% fill = 0 pts
        fill = fvg.get("fill_percentage", 0.0)
        score += (1.0 - min(fill, 1.0)) * 20.0

        # Recency: latest FVG gets up to 20 pts
        max_idx = len(self.candles) - 1
        idx = fvg["index"]
        recency = idx / max_idx if max_idx > 0 else 1.0
        score += recency * 20.0

        return min(score, 100.0)

    def get_fill_percentage(self, fvg: Dict[str, Any], current_price: float) -> float:
        """Calculate how much of the FVG has been filled by price action.

        * 0 %   = price has not touched the gap (fresh).
        * 100 % = price has fully traversed the gap (filled).
        * >100 % = price overshot through the gap.

        Parameters
        ----------
        fvg : dict
            FVG dict with ``top`` and ``bottom``.
        current_price : float
            Latest price.

        Returns
        -------
        float
            Fill percentage 0-100+.
        """
        top = max(fvg["top"], fvg["bottom"])
        bottom = min(fvg["top"], fvg["bottom"])
        gap_size = top - bottom
        if gap_size <= 0:
            return 100.0

        # Distance from bottom to current price
        filled = current_price - bottom
        pct = (filled / gap_size) * 100.0
        return float(np.clip(pct, 0.0, 200.0))

    def find_fvg_in_zone(self, price: float, zone_size: float = 0.01) -> List[Dict[str, Any]]:
        """Find all FVGs that lie within ``zone_size`` % of the given price.

        Parameters
        ----------
        price : float
            Centre price.
        zone_size : float
            Fractional radius (default 1 %).

        Returns
        -------
        List[dict]
            Matching FVGs from both bullish and bearish sets.
        """
        tol = price * zone_size
        all_fvgs = self._bullish_fvgs + self._bearish_fvgs
        matches = [
            fvg
            for fvg in all_fvgs
            if abs(((fvg["top"] + fvg["bottom"]) / 2.0) - price) <= tol
        ]
        return matches
