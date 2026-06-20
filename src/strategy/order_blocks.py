"""Order Block Identification — Institutional Supply/Demand Zones.

Order Blocks (OBs) are the last opposing candle before an aggressive,
structure-breaking move.  This module identifies bullish and bearish OBs,
scores them for quality, and finds confluence with Fair Value Gaps.

All heavy lifting is vectorised via pandas/numpy.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class OrderBlocks:
    """Identify and score institutional Order Blocks.

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
        self._bullish_obs: List[Dict[str, Any]] = []
        self._bearish_obs: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _candle_body(open_: float, close: float) -> float:
        return abs(close - open_)

    @staticmethod
    def _is_bullish(open_: float, close: float) -> bool:
        return close > open_

    @staticmethod
    def _is_bearish(open_: float, close: float) -> bool:
        return close < open_

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def find_bullish_order_blocks(self, min_body_size: float = 0.001) -> List[Dict[str, Any]]:
        """Find bullish Order Blocks.

        A bullish OB is the **last bearish candle** before a strong bullish
        impulse that breaks a prior swing high (BOS).  The OB body forms a
        demand zone where institutional buyers may have entered.

        Parameters
        ----------
        min_body_size : float
            Minimum candle body as a fraction of price (default 0.1 %).

        Returns
        -------
        List[dict]
            Each dict: ``index``, ``open``, ``high``, ``low``, ``close``,
            ``strength`` (0-100), ``time``, ``body_size``, ``times_tested``.
        """
        opens = self.candles["open"].values
        highs = self.candles["high"].values
        lows = self.candles["low"].values
        closes = self.candles["close"].values
        volumes = self.candles["volume"].values
        times = self.candles.index
        avg_vol = float(np.mean(volumes)) if np.mean(volumes) > 0 else 1.0

        obs: List[Dict[str, Any]] = []

        # Vectorised: find bearish candles
        bearish = closes < opens
        # Find impulsive bullish moves (3-candle displacement)
        for i in range(3, len(closes) - 1):
            if not bearish[i]:
                continue

            # Body size check
            body = self._candle_body(opens[i], closes[i])
            if body / closes[i] < min_body_size:
                continue

            # Displacement: next 3 candles show strong bullish move
            # Simplified: close[i+3] > high[i] and close[i+3] > close[i+2] > close[i+1]
            if not (closes[i + 3] > highs[i] and closes[i + 3] > closes[i + 2] > closes[i + 1]):
                continue

            # Volume confirmation on the displacement candle
            displacement_vol = volumes[i + 3]
            vol_strength = min(displacement_vol / avg_vol, 3.0) / 3.0  # 0-1

            # Strength scoring (0-100)
            strength = 50.0 + (vol_strength * 50.0)

            ob = {
                "index": int(i),
                "open": float(opens[i]),
                "high": float(highs[i]),
                "low": float(lows[i]),
                "close": float(closes[i]),
                "strength": float(strength),
                "time": times[i],
                "body_size": float(body),
                "times_tested": 0,
            }
            obs.append(ob)

        self._bullish_obs = obs
        logger.info("Found %d bullish Order Blocks (min_body=%.4f)", len(obs), min_body_size)
        return obs

    def find_bearish_order_blocks(self, min_body_size: float = 0.001) -> List[Dict[str, Any]]:
        """Find bearish Order Blocks.

        A bearish OB is the **last bullish candle** before a strong bearish
        impulse that breaks a prior swing low (BOS).  The OB body forms a
        supply zone.

        Parameters & Returns — same as :meth:`find_bullish_order_blocks`.
        """
        opens = self.candles["open"].values
        highs = self.candles["high"].values
        lows = self.candles["low"].values
        closes = self.candles["close"].values
        volumes = self.candles["volume"].values
        times = self.candles.index
        avg_vol = float(np.mean(volumes)) if np.mean(volumes) > 0 else 1.0

        obs: List[Dict[str, Any]] = []
        bullish = closes > opens

        for i in range(3, len(closes) - 1):
            if not bullish[i]:
                continue

            body = self._candle_body(opens[i], closes[i])
            if body / closes[i] < min_body_size:
                continue

            # Displacement: next 3 candles show strong bearish move
            if not (closes[i + 3] < lows[i] and closes[i + 3] < closes[i + 2] < closes[i + 1]):
                continue

            displacement_vol = volumes[i + 3]
            vol_strength = min(displacement_vol / avg_vol, 3.0) / 3.0
            strength = 50.0 + (vol_strength * 50.0)

            ob = {
                "index": int(i),
                "open": float(opens[i]),
                "high": float(highs[i]),
                "low": float(lows[i]),
                "close": float(closes[i]),
                "strength": float(strength),
                "time": times[i],
                "body_size": float(body),
                "times_tested": 0,
            }
            obs.append(ob)

        self._bearish_obs = obs
        logger.info("Found %d bearish Order Blocks (min_body=%.4f)", len(obs), min_body_size)
        return obs

    def score_order_block(self, ob: Dict[str, Any], market_structure: Dict[str, Any]) -> float:
        """Score an Order Block for quality (0-100).

        Scoring criteria:
            1. **HTF bias alignment** (+30 pts) — OB direction matches bias.
            2. **Displacement strength** (+25 pts) — body size of the move.
            3. **Volume at creation** (+25 pts) — high volume = conviction.
            4. **Times tested** (+20 pts) — fewer touches = fresher zone.

        Parameters
        ----------
        ob : dict
            Order block dict from the find_* methods.
        market_structure : dict
            Output of :meth:`MarketStructure.detect_structure`.

        Returns
        -------
        float
            Composite score 0-100.
        """
        score = 0.0
        bias = market_structure.get("bias", "neutral")

        # 1. Bias alignment
        is_bullish = ob["close"] > ob["open"]
        if (bias == "bullish" and not is_bullish) or (bias == "bearish" and is_bullish):
            score += 30.0
        elif bias == "neutral":
            score += 15.0

        # 2. Displacement strength (body size relative to price)
        body_ratio = ob["body_size"] / ob["close"]
        score += min(body_ratio * 1000, 25.0)  # cap at 25

        # 3. Volume strength (already baked into ob["strength"])
        vol_score = (ob["strength"] - 50.0) / 50.0 * 25.0 if ob["strength"] >= 50.0 else 0.0
        score += min(vol_score, 25.0)

        # 4. Times tested (fewer = better)
        tested = ob.get("times_tested", 0)
        score += max(20.0 - tested * 5.0, 0.0)

        return min(score, 100.0)

    def find_ob_fvg_confluence(
        self, bullish: bool = True, fvgs: List[Dict[str, Any]] | None = None
    ) -> List[Dict[str, Any]]:
        """Find overlapping zones where Order Block and FVG coincide.

        Confluence is the highest-probability entry zone in ICT/SMC.

        Parameters
        ----------
        bullish : bool
            Scan bullish OBs + bullish FVGs if True, else bearish.
        fvgs : list or None
            FVG dicts from :class:`FairValueGaps`.  If None, the caller
            must have provided them externally; this module does not import
            FVG to keep dependencies loose.

        Returns
        -------
        List[dict]
            Each dict: ``ob`` (the OB dict), ``fvg`` (the FVG dict),
            ``confluence_zone`` (top, bottom), ``score`` (0-100).
        """
        if fvgs is None:
            logger.warning("No FVGs provided for confluence scan; returning empty.")
            return []

        obs = self._bullish_obs if bullish else self._bearish_obs
        confluences: List[Dict[str, Any]] = []

        for ob in obs:
            ob_top = max(ob["open"], ob["close"])
            ob_bottom = min(ob["open"], ob["close"])

            for fvg in fvgs:
                fvg_top = fvg["top"]
                fvg_bottom = fvg["bottom"]

                # Overlap check
                overlap_top = min(ob_top, fvg_top)
                overlap_bottom = max(ob_bottom, fvg_bottom)
                if overlap_top > overlap_bottom:
                    overlap_size = overlap_top - overlap_bottom
                    ob_size = ob_top - ob_bottom
                    fvg_size = fvg_top - fvg_bottom

                    # Confluence score: % overlap relative to both zones
                    ob_pct = overlap_size / ob_size if ob_size > 0 else 0
                    fvg_pct = overlap_size / fvg_size if fvg_size > 0 else 0
                    score = (ob_pct + fvg_pct) * 50.0  # 0-100

                    confluences.append(
                        {
                            "ob": ob,
                            "fvg": fvg,
                            "confluence_zone": {
                                "top": float(overlap_top),
                                "bottom": float(overlap_bottom),
                            },
                            "score": float(min(score, 100.0)),
                        }
                    )

        # Sort by score descending
        confluences.sort(key=lambda x: x["score"], reverse=True)
        logger.info(
            "Found %d OB+FVG confluences (bullish=%s)", len(confluences), bullish
        )
        return confluences

    def get_nearest_ob(self, price: float, bullish: bool = True) -> Dict[str, Any] | None:
        """Return the nearest active Order Block to the current price.

        Parameters
        ----------
        price : float
            Current market price.
        bullish : bool
            If True, search bullish OBs; else bearish.

        Returns
        -------
        dict or None
            The closest OB dict, or None if no OBs exist.
        """
        obs = self._bullish_obs if bullish else self._bearish_obs
        if not obs:
            return None

        # Distance to OB mid-point
        def dist(ob: Dict[str, Any]) -> float:
            mid = (ob["open"] + ob["close"]) / 2.0
            return abs(price - mid)

        return min(obs, key=dist)

    def is_price_in_ob_zone(
        self, price: float, ob: Dict[str, Any], tolerance: float = 0.002
    ) -> bool:
        """Check if price lies within the Order Block body ± tolerance.

        Parameters
        ----------
        price : float
            Price to test.
        ob : dict
            Order block dict.
        tolerance : float
            Fractional tolerance (default 0.2 % of price).

        Returns
        -------
        bool
        """
        ob_top = max(ob["open"], ob["close"])
        ob_bottom = min(ob["open"], ob["close"])
        tol = price * tolerance
        return (ob_bottom - tol) <= price <= (ob_top + tol)
