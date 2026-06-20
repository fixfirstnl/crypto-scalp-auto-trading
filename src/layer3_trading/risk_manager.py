"""
risk_manager.py — Kill switches, circuit breakers, and pre-trade risk gates.

Implements the ICT/SMC scalper risk profile:
- 0.5 % risk per trade
- 3 % daily hard loss limit
- 7 % weekly loss limit
- Max 5 open positions
- Max 4 consecutive losses
- 5 % max drawdown halt
- Kill-zone session filter (London / NY EST)
- Spread + ATR volatility guards
- Correlation cap (2 per base currency)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Session windows in EST (UTC-5 standard, UTC-4 DST). We use configurable offsets.
KILL_ZONES_EST = [
    (2, 5),   # London  2:00 – 5:00 AM EST
    (7, 10),  # NY      7:00 – 10:00 AM EST
]


class RiskManager:
    """
    Central risk gate for the trading system.

    Parameters
    ----------
    account_balance : float
        Current account balance in USDT (or base currency).
    risk_per_trade : float, default 0.005
        Fraction of balance to risk per trade (0.5 %).
    max_positions : int, default 5
        Max simultaneous open positions.
    daily_loss_limit : float, default 0.03
        Hard daily loss limit as fraction of balance (3 %).
    weekly_loss_limit : float, default 0.07
        Weekly loss limit as fraction of balance (7 %).
    max_consecutive_losses : int, default 4
        Trading pause after this many consecutive losses.
    max_drawdown : float, default 0.05
        Halt if drawdown exceeds this fraction (5 %).
    spread_multiplier : float, default 2.0
        Reject entry if spread > 2× average.
    atr_min_multiplier : float, default 1.0
        Reject if ATR < 1× 20-day average (dead market).
    atr_max_multiplier : float, default 2.0
        Reject if ATR > 2× 20-day average (erratic).
    """

    def __init__(
        self,
        account_balance: float,
        risk_per_trade: float = 0.005,
        max_positions: int = 5,
        daily_loss_limit: float = 0.03,
        weekly_loss_limit: float = 0.07,
        max_consecutive_losses: int = 4,
        max_drawdown: float = 0.05,
        spread_multiplier: float = 2.0,
        atr_min_multiplier: float = 1.0,
        atr_max_multiplier: float = 2.0,
    ):
        self.account_balance = account_balance
        self.risk_per_trade = risk_per_trade
        self.max_positions = max_positions
        self.daily_loss_limit = daily_loss_limit
        self.weekly_loss_limit = weekly_loss_limit
        self.max_consecutive_losses = max_consecutive_losses
        self.max_drawdown = max_drawdown
        self.spread_multiplier = spread_multiplier
        self.atr_min_multiplier = atr_min_multiplier
        self.atr_max_multiplier = atr_max_multiplier

        # Mutable counters
        self._consecutive_losses = 0
        self._daily_pnl = 0.0
        self._weekly_pnl = 0.0
        self._peak_balance = account_balance
        self._halted = False
        self._halt_reason = ""

    # ------------------------------------------------------------------
    # Entry gate
    # ------------------------------------------------------------------

    def check_entry_allowed(
        self,
        signal: dict,
        open_positions: List[dict],
        daily_pnl: float,
        consecutive_losses: int,
        current_drawdown: float,
        spread: float,
        avg_spread: float,
        atr: float,
        avg_atr: float,
    ) -> Tuple[bool, str]:
        """
        Pre-trade risk gate. Returns (allowed, reason).

        Checks, in order:
        1. Kill switch (global halt)
        2. Daily / weekly loss limits
        3. Max positions
        4. Consecutive-loss guard
        5. Drawdown halt
        6. Spread guard
        7. ATR volatility guard
        8. Correlation limit
        9. Session filter
        10. News filter (placeholder)
        """
        # 1. Global halt
        if self._halted:
            return False, f"GLOBAL_HALT: {self._halt_reason}"

        # 2. Daily loss
        if daily_pnl < -self.account_balance * self.daily_loss_limit:
            return False, f"DAILY_LOSS_LIMIT: {daily_pnl:.2f} < {-self.account_balance * self.daily_loss_limit:.2f}"

        # 3. Weekly loss
        if self._weekly_pnl < -self.account_balance * self.weekly_loss_limit:
            return False, f"WEEKLY_LOSS_LIMIT: {self._weekly_pnl:.2f} < {-self.account_balance * self.weekly_loss_limit:.2f}"

        # 4. Max positions
        if len(open_positions) >= self.max_positions:
            return False, f"MAX_POSITIONS: {len(open_positions)} >= {self.max_positions}"

        # 5. Consecutive losses
        if consecutive_losses >= self.max_consecutive_losses:
            return False, f"CONSECUTIVE_LOSSES: {consecutive_losses} >= {self.max_consecutive_losses}"

        # 6. Drawdown
        if current_drawdown >= self.max_drawdown:
            return False, f"MAX_DRAWDOWN: {current_drawdown:.2%} >= {self.max_drawdown:.2%}"

        # 7. Spread guard
        if avg_spread > 0 and spread > avg_spread * self.spread_multiplier:
            return False, f"SPREAD_GUARD: {spread:.4f} > {avg_spread * self.spread_multiplier:.4f}"

        # 8. ATR guard
        if avg_atr > 0:
            if atr < avg_atr * self.atr_min_multiplier:
                return False, f"ATR_TOO_LOW: {atr:.4f} < {avg_atr * self.atr_min_multiplier:.4f}"
            if atr > avg_atr * self.atr_max_multiplier:
                return False, f"ATR_TOO_HIGH: {atr:.4f} > {avg_atr * self.atr_max_multiplier:.4f}"

        # 9. Correlation
        symbol = signal.get("symbol", "")
        if not self.check_correlation_limit(symbol, open_positions):
            return False, "CORRELATION_LIMIT: max 2 positions per base currency"

        # 10. Session filter
        if not self.check_session_filter(timezone="EST"):
            return False, "SESSION_FILTER: outside London/NY kill zones"

        # 11. News filter (placeholder)
        if not self.check_news_filter(symbol):
            return False, "NEWS_FILTER: high-impact event window"

        return True, ""

    # ------------------------------------------------------------------
    # Kill switch
    # ------------------------------------------------------------------

    def check_kill_switch(
        self,
        daily_pnl: float,
        current_drawdown: float,
        consecutive_losses: int,
    ) -> Tuple[bool, str]:
        """
        Global circuit breaker. Returns (halt, reason).

        True → trading must stop immediately.
        """
        if daily_pnl <= -self.account_balance * self.daily_loss_limit:
            reason = f"DAILY_LOSS_HALT: {daily_pnl:.2f} (limit {-self.account_balance * self.daily_loss_limit:.2f})"
            self._trigger_halt(reason)
            return True, reason

        if current_drawdown >= self.max_drawdown:
            reason = f"DRAWDOWN_HALT: {current_drawdown:.2%} (limit {self.max_drawdown:.2%})"
            self._trigger_halt(reason)
            return True, reason

        if consecutive_losses >= self.max_consecutive_losses:
            reason = f"CONSECUTIVE_LOSS_HALT: {consecutive_losses} (limit {self.max_consecutive_losses})"
            self._trigger_halt(reason)
            return True, reason

        return False, ""

    def _trigger_halt(self, reason: str):
        self._halted = True
        self._halt_reason = reason
        logger.critical("KILL SWITCH TRIGGERED: %s", reason)

    def reset_halt(self):
        """Manual reset after review (requires human intervention)."""
        self._halted = False
        self._halt_reason = ""
        logger.warning("Kill switch manually reset.")

    def is_halted(self) -> bool:
        return self._halted

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def calculate_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float,
        symbol: str = "",
    ) -> float:
        """
        Risk-based position size in contracts.

        Formula
        -------
        contracts = (balance × risk%) / |entry_price − stop_loss|

        Parameters
        ----------
        account_balance : float
            Current balance.
        risk_percent : float
            Fraction of balance to risk (e.g., 0.005 = 0.5 %).
        entry_price : float
            Planned entry price.
        stop_loss : float
            Stop-loss price.
        symbol : str, optional
            For future leverage or min-size adjustments.

        Returns
        -------
        float
            Position size in contracts (base coin quantity).
        """
        if entry_price == stop_loss:
            logger.warning("Entry price equals stop loss; cannot size position.")
            return 0.0

        risk_amount = account_balance * risk_percent
        price_distance = abs(entry_price - stop_loss)
        size = risk_amount / price_distance

        # Round down to 3 decimals for BTC/ETH perp (adjust per symbol if needed)
        size = round(size - 0.0005, 3)
        size = max(size, 0.0)

        logger.info(
            "Position sizing: balance=%.2f risk=%.2f%% entry=%.2f sl=%.2f → size=%.4f",
            account_balance, risk_percent * 100, entry_price, stop_loss, size,
        )
        return size

    # ------------------------------------------------------------------
    # Correlation limit
    # ------------------------------------------------------------------

    def check_correlation_limit(
        self,
        new_symbol: str,
        open_positions: List[dict],
    ) -> bool:
        """
        Allow max 2 positions per base currency.

        Examples
        --------
        BTC/USDT:USDT and BTC/USDC:USDC share base ``BTC`` → counts as 1.
        """
        base = new_symbol.split("/")[0] if "/" in new_symbol else new_symbol
        count = 0
        for pos in open_positions:
            sym = pos.get("symbol", "")
            existing_base = sym.split("/")[0] if "/" in sym else sym
            if existing_base == base:
                count += 1
        return count < 2

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    def check_news_filter(self, symbol: str) -> bool:
        """
        Placeholder for economic-calendar / news integration.

        Returns True if trading is allowed (no imminent red-folder news).
        """
        # TODO: integrate Forex Factory or similar API
        return True

    def check_session_filter(self, timezone: str = "EST") -> bool:
        """
        Only allow entries during London (2–5 AM) and NY (7–10 AM) kill zones.

        Parameters
        ----------
        timezone : str
            "EST" or "UTC".  EST windows are shifted +5h for UTC.
        """
        now = datetime.now(timezone.utc)
        hour = now.hour

        if timezone.upper() == "EST":
            # Simple fixed-offset (ignoring DST for robustness; adjust if needed)
            est_hour = (hour - 5) % 24
            for start, end in KILL_ZONES_EST:
                if start <= est_hour < end:
                    return True
            return False
        else:
            # UTC windows: 07-10 (London), 12-15 (NY)
            utc_windows = [(7, 10), (12, 15)]
            for start, end in utc_windows:
                if start <= hour < end:
                    return True
            return False

    # ------------------------------------------------------------------
    # Stats reset
    # ------------------------------------------------------------------

    def reset_daily_stats(self):
        """Call at UTC 00:00 to reset daily counters."""
        self._daily_pnl = 0.0
        self._consecutive_losses = 0
        logger.info("Daily stats reset.")

    def reset_weekly_stats(self):
        """Call at Sunday UTC 00:00."""
        self._weekly_pnl = 0.0
        logger.info("Weekly stats reset.")

    # ------------------------------------------------------------------
    # Mutators (called by trading layer on fill / close)
    # ------------------------------------------------------------------

    def update_balance(self, new_balance: float):
        """Update account balance and peak tracking."""
        self.account_balance = new_balance
        if new_balance > self._peak_balance:
            self._peak_balance = new_balance

    def record_pnl(self, pnl: float):
        """Update daily / weekly PnL and consecutive-loss counter."""
        self._daily_pnl += pnl
        self._weekly_pnl += pnl
        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        # Auto-check kill switch after every closed trade
        dd = (self._peak_balance - self.account_balance) / self._peak_balance if self._peak_balance else 0.0
        halted, reason = self.check_kill_switch(self._daily_pnl, dd, self._consecutive_losses)
        if halted:
            logger.critical("Auto-halt triggered after trade PnL: %s", reason)
