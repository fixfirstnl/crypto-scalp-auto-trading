"""consensus.py — Consensus Engine / Voting Logic.

Evaluates the outputs of all four agents and produces a single
``buy`` / ``sell`` / ``hold`` decision with a unified confidence score.

Consensus rules (hard-coded)
----------------------------
1. Bias must align with signal (long ↔ bullish, short ↔ bearish).
2. Signal confidence ≥ 70.
3. Risk must approve (``approved=True``).
4. Execution plan must be ready (``order_type != "none"``).
5. All four agents must agree → trade is executed.

If any rule fails → ``hold``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ConsensusEngine:
    """Voting engine that aggregates multi-agent outputs into a trade decision.

    Parameters
    ----------
    min_confidence : float, default 70.0
        Minimum signal confidence required for a trade (0-100 scale).
    """

    def __init__(self, min_confidence: float = 70.0) -> None:
        self.min_confidence = min_confidence

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def evaluate(
        self,
        bias: Dict[str, Any],
        signal: Optional[Dict[str, Any]],
        risk: Optional[Dict[str, Any]],
        exec_plan: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate all agent outputs and return consensus.

        Parameters
        ----------
        bias : dict
            Output of :meth:`BiasAgent.analyze`.
        signal : dict or None
            Output of :meth:`SignalAgent.generate`.
        risk : dict or None
            Output of :meth:`RiskAgent.evaluate`.
        exec_plan : dict or None
            Output of :meth:`ExecAgent.optimize`.

        Returns
        -------
        dict
            ``consensus`` (``'buy'`` | ``'sell'`` | ``'hold'``),
            ``confidence`` (float), ``details`` (diagnostics), ``trade`` (dict or None).
        """
        details: Dict[str, Any] = {
            "bias_aligned": False,
            "signal_confident": False,
            "risk_approved": False,
            "exec_ready": False,
            "reasons": [],
        }

        # Rule 1: valid signal exists
        if signal is None or signal.get("signal", "none") == "none":
            details["reasons"].append("No valid signal generated")
            return self._hold_result(details)

        bias_direction = bias.get("bias", "neutral")
        signal_direction = signal.get("signal", "none")

        # Rule 2: bias aligns with signal
        if not self._bias_signal_alignment(bias_direction, signal_direction):
            details["reasons"].append(
                f"Bias mismatch: {bias_direction} vs {signal_direction}"
            )
            return self._hold_result(details)
        details["bias_aligned"] = True

        # Rule 3: signal confidence ≥ threshold
        signal_conf = float(signal.get("confidence", 0.0))
        if signal_conf < self.min_confidence:
            details["reasons"].append(
                f"Signal confidence too low: {signal_conf:.1f} < {self.min_confidence}"
            )
            return self._hold_result(details)
        details["signal_confident"] = True

        # Rule 4: risk approved
        if risk is None or not risk.get("approved", False):
            reason = risk.get("reason", "Risk rejected") if risk else "No risk evaluation"
            details["reasons"].append(f"Risk not approved: {reason}")
            return self._hold_result(details)
        details["risk_approved"] = True

        # Rule 5: execution ready
        if exec_plan is None or exec_plan.get("order_type", "none") == "none":
            details["reasons"].append("Execution plan not ready")
            return self._hold_result(details)
        details["exec_ready"] = True

        # All checks passed → consensus
        consensus_conf = self._confidence_score(
            float(bias.get("confidence", 0.0)),
            signal_conf,
        )

        trade = self._build_trade(signal, risk, exec_plan)

        result = {
            "consensus": "buy" if signal_direction == "long" else "sell",
            "confidence": round(consensus_conf, 2),
            "details": details,
            "trade": trade,
        }
        logger.info(
            "ConsensusEngine: %s consensus=%s confidence=%.1f",
            trade.get("symbol", ""),
            result["consensus"],
            consensus_conf,
        )
        return result

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _bias_signal_alignment(bias: str, signal: str) -> bool:
        """Return True if *bias* and *signal* are aligned."""
        if bias == "neutral" or signal == "none":
            return False
        return (bias == "bullish" and signal == "long") or (
            bias == "bearish" and signal == "short"
        )

    @staticmethod
    def _confidence_score(bias_conf: float, signal_conf: float) -> float:
        """Weighted consensus confidence (signal is more important at entry)."""
        return min(bias_conf * 0.3 + signal_conf * 0.7, 100.0)

    @staticmethod
    def _hold_result(details: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "consensus": "hold",
            "confidence": 0.0,
            "details": details,
            "trade": None,
        }

    @staticmethod
    def _build_trade(
        signal: Dict[str, Any],
        risk: Dict[str, Any],
        exec_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Assemble the final trade instruction dict for Layer 3."""
        return {
            "symbol": signal.get("symbol", ""),
            "direction": signal.get("signal", "none"),
            "entry_price": exec_plan.get("entry_price", signal.get("entry", 0.0)),
            "stop_loss": signal.get("stop", 0.0),
            "size": risk.get("size", 0.0),
            "order_type": exec_plan.get("order_type", "limit"),
            "partials": exec_plan.get("partials", []),
            "sl_order": exec_plan.get("sl_order", {}),
            "trailing_after_tp2": exec_plan.get("trailing_after_tp2", False),
            "max_loss": risk.get("max_loss", 0.0),
            "risk_score": risk.get("risk_score", 0.0),
        }
