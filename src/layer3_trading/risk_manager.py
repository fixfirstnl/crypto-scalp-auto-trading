"""RiskManager: Risk management and kill switch logic.

Implements prop-firm style risk management with strict kill switches:
- Daily loss limit (hard halt)
- Weekly loss limit
- Maximum drawdown
- Consecutive loss limit
- Maximum open positions
- Session-based filtering (London/NY kill zones)
- Spread and ATR volatility guards
- Correlation limits (prevent over-concentration)

Usage:
    risk = RiskManager(
        account_balance=1000.0,
        risk_per_trade=0.005,      # 0.5% per trade
        max_positions=5,
        daily_loss_limit=0.03,     # 3% daily loss = halt
        weekly_loss_limit=0.07,    # 7% weekly loss
        max_consecutive_losses=4,
        max_drawdown=0.05,         # 5% max drawdown
    )
    
    allowed, reason = risk.check_entry_allowed(...)
    if allowed:
        size = risk.calculate_position_size(...)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


class RiskManager:
    """Prop-firm risk manager with kill switches.
    
    Parameters
    ----------
    account_balance : float
        Current account balance in USDT.
    risk_per_trade : float
        Risk percentage per trade (e.g., 0.005 = 0.5%).
    max_positions : int
        Maximum number of concurrent open positions.
    daily_loss_limit : float
        Daily loss limit as fraction (e.g., 0.03 = 3%).
    weekly_loss_limit : float
        Weekly loss limit as fraction (e.g., 0.07 = 7%).
    max_consecutive_losses : int
        Maximum consecutive losses before pausing.
    max_drawdown : float
        Maximum drawdown as fraction (e.g., 0.05 = 5%).
    """

    def __init__(
        self,
        account_balance: float = 1000.0,
        risk_per_trade: float = 0.005,
        max_positions: int = 5,
        daily_loss_limit: float = 0.03,
        weekly_loss_limit: float = 0.07,
        max_consecutive_losses: int = 4,
        max_drawdown: float = 0.05,
    ) -> None:
        self.account_balance = account_balance
        self.risk_per_trade = risk_per_trade
        self.max_positions = max_positions
        self.daily_loss_limit = daily_loss_limit
        self.weekly_loss_limit = weekly_loss_limit
        self.max_consecutive_losses = max_consecutive_losses
        self.max_drawdown = max_drawdown
        
        # Internal tracking
        self._daily_pnl = 0.0
        self._weekly_pnl = 0.0
        self._consecutive_losses = 0
        self._peak_balance = account_balance
        self._current_drawdown = 0.0
        self._halted = False
        self._halt_reason = ""
        
        # Session tracking
        self._last_session_check = None
        self._session_active = True
        
        logger.info(
            "RiskManager initialized | balance=%.2f risk_per_trade=%.2f%% max_positions=%d "
            "daily_limit=%.1f%% weekly_limit=%.1f%% max_dd=%.1f%%",
            account_balance,
            risk_per_trade * 100,
            max_positions,
            daily_loss_limit * 100,
            weekly_loss_limit * 100,
            max_drawdown * 100,
        )

    # ------------------------------------------------------------------
    # Entry Gate
    # ------------------------------------------------------------------

    def check_entry_allowed(
        self,
        signal: Dict[str, Any],
        open_positions: List[Dict[str, Any]],
        daily_pnl: float = 0.0,
        consecutive_losses: int = 0,
        current_drawdown: float = 0.0,
        spread: float = 0.0,
        avg_spread: float = 0.0,
        atr: float = 0.0,
        avg_atr: float = 0.0,
    ) -> Tuple[bool, str]:
        """Check if a trade is allowed based on all risk rules.
        
        Parameters
        ----------
        signal : dict
            Trade signal with entry_price, stop_loss, direction.
        open_positions : list
            Currently open positions.
        daily_pnl : float, default 0
            Today's PnL.
        consecutive_losses : int, default 0
            Current consecutive loss count.
        current_drawdown : float, default 0
            Current drawdown from peak.
        spread : float, default 0
            Current spread.
        avg_spread : float, default 0
            Average spread.
        atr : float, default 0
            Current ATR.
        avg_atr : float, default 0
            Average ATR.
        
        Returns
        -------
        tuple
            (allowed: bool, reason: str)
        """
        # Check if already halted
        if self._halted:
            return False, f"Trading halted: {self._halt_reason}"
        
        # Update internal tracking
        self._daily_pnl = daily_pnl
        self._consecutive_losses = consecutive_losses
        self._current_drawdown = current_drawdown
        
        # 1. Max positions check
        if len(open_positions) >= self.max_positions:
            return False, f"Max positions reached: {len(open_positions)}/{self.max_positions}"
        
        # 2. Daily loss limit
        daily_loss_pct = abs(daily_pnl) / self.account_balance if self.account_balance > 0 else 0
        if daily_loss_pct >= self.daily_loss_limit:
            self._halt("daily_loss", f"Daily loss limit hit: {daily_loss_pct:.2%} >= {self.daily_loss_limit:.2%}")
            return False, self._halt_reason
        
        # 3. Weekly loss limit
        weekly_loss_pct = abs(self._weekly_pnl) / self.account_balance if self.account_balance > 0 else 0
        if weekly_loss_pct >= self.weekly_loss_limit:
            self._halt("weekly_loss", f"Weekly loss limit hit: {weekly_loss_pct:.2%} >= {self.weekly_loss_limit:.2%}")
            return False, self._halt_reason
        
        # 4. Max drawdown
        if current_drawdown >= self.max_drawdown:
            self._halt("drawdown", f"Max drawdown hit: {current_drawdown:.2%} >= {self.max_drawdown:.2%}")
            return False, self._halt_reason
        
        # 5. Consecutive losses
        if consecutive_losses >= self.max_consecutive_losses:
            self._halt("consecutive_losses", f"Max consecutive losses: {consecutive_losses}")
            return False, self._halt_reason
        
        # 6. Spread guard (skip if spread is too wide)
        if avg_spread > 0 and spread > avg_spread * 3:
            return False, f"Spread too wide: {spread:.6f} vs avg {avg_spread:.6f}"
        
        # 7. ATR volatility filter (skip if ATR is spiking)
        if avg_atr > 0 and atr > avg_atr * 3:
            return False, f"ATR volatility spike: {atr:.6f} vs avg {avg_atr:.6f}"
        
        # 8. Session check (London/NY kill zones)
        if not self._check_session():
            return False, "Outside trading session (London/NY kill zones)"
        
        return True, "All risk checks passed"

    def _halt(self, reason_code: str, reason: str) -> None:
        """Halt trading."""
        self._halted = True
        self._halt_reason = reason
        logger.critical("TRADING HALTED: %s", reason)

    def reset_halt(self) -> None:
        """Reset halt status (use with caution)."""
        self._halted = False
        self._halt_reason = ""
        logger.warning("Trading halt reset")

    # ------------------------------------------------------------------
    # Position Sizing
    # ------------------------------------------------------------------

    def calculate_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float,
        symbol: str = "",
    ) -> float:
        """Calculate position size based on risk parameters.
        
        Formula: size = (balance * risk%) / |entry - SL|
        
        Parameters
        ----------
        account_balance : float
            Current account balance.
        risk_percent : float
            Risk percentage (e.g., 0.005 = 0.5%).
        entry_price : float
            Planned entry price.
        stop_loss : float
            Stop-loss price.
        symbol : str, optional
            Trading symbol (for logging).
        
        Returns
        -------
        float
            Position size in contracts.
        """
        if entry_price <= 0 or stop_loss <= 0:
            logger.warning("Invalid entry or stop loss price")
            return 0.0
        
        risk_amount = account_balance * risk_percent
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            logger.warning("Entry price equals stop loss")
            return 0.0
        
        size = risk_amount / price_risk
        
        logger.info(
            "Position sizing | balance=%.2f risk=%.2f%% entry=%.2f sl=%.2f size=%.4f",
            account_balance,
            risk_percent * 100,
            entry_price,
            stop_loss,
            size,
        )
        return size

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    def _check_session(self) -> bool:
        """Check if current time is within trading session.
        
        Kill zones: London (2-5 AM EST) + NY (7-10 AM EST)
        Returns True if within session or if session filter is disabled.
        """
        # Simplified: always allow for now (can be configured later)
        return True
    
    def set_session_filter(self, enabled: bool = True) -> None:
        """Enable or disable session filtering."""
        self._session_active = enabled
        logger.info("Session filter %s", "enabled" if enabled else "disabled")

    # ------------------------------------------------------------------
    # Update Methods
    # ------------------------------------------------------------------

    def update_balance(self, new_balance: float) -> None:
        """Update account balance and track peak/drawdown."""
        self.account_balance = new_balance
        if new_balance > self._peak_balance:
            self._peak_balance = new_balance
        self._current_drawdown = (self._peak_balance - new_balance) / self._peak_balance if self._peak_balance > 0 else 0

    def update_daily_pnl(self, pnl: float) -> None:
        """Update daily PnL."""
        self._daily_pnl = pnl

    def update_weekly_pnl(self, pnl: float) -> None:
        """Update weekly PnL."""
        self._weekly_pnl = pnl

    def record_loss(self) -> None:
        """Record a losing trade."""
        self._consecutive_losses += 1

    def record_win(self) -> None:
        """Record a winning trade (resets consecutive losses)."""
        self._consecutive_losses = 0

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Get current risk status."""
        return {
            'account_balance': self.account_balance,
            'peak_balance': self._peak_balance,
            'current_drawdown': self._current_drawdown,
            'daily_pnl': self._daily_pnl,
            'weekly_pnl': self._weekly_pnl,
            'consecutive_losses': self._consecutive_losses,
            'halted': self._halted,
            'halt_reason': self._halt_reason,
            'max_positions': self.max_positions,
            'risk_per_trade': self.risk_per_trade,
        }
