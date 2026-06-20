"""TelegramBot: Real-time trade alerts and remote command interface.

Provides:
- Trade entry/exit alerts with PnL
- Error notifications
- Kill switch alerts
- Daily PnL reports
- Remote commands: /status, /pnl, /stop, /start

Dependencies:
- python-telegram-bot >= 20.0

Usage:
    bot = TelegramBot(bot_token, chat_id)
    await bot.initialize()
    bot.set_callbacks(
        status=get_status_fn,
        pnl=get_pnl_fn,
        stop=stop_fn,
        start=start_fn,
    )
    await bot.start_polling()
    
    # Send alerts
    await bot.send_trade_alert({...})
    await bot.send_error_alert('API connection failed')
    await bot.send_kill_switch_alert('Daily loss limit hit')
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot for trade alerts and remote commands.
    
    Parameters
    ----------
    bot_token : str
        Telegram bot token from @BotFather.
    chat_id : str
        Telegram chat ID for alerts.
    """

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.application: Optional[Application] = None
        
        # Callbacks for commands
        self._status_callback: Optional[Callable[[], Awaitable[str]]] = None
        self._pnl_callback: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None
        self._stop_callback: Optional[Callable[[], Awaitable[None]]] = None
        self._start_callback: Optional[Callable[[], Awaitable[None]]] = None
        
        logger.info("TelegramBot initialized | chat_id=%s", chat_id)

    async def initialize(self) -> None:
        """Initialize the bot application."""
        self.application = Application.builder().token(self.bot_token).build()
        
        # Register command handlers
        self.application.add_handler(CommandHandler("status", self._status_command))
        self.application.add_handler(CommandHandler("pnl", self._pnl_command))
        self.application.add_handler(CommandHandler("stop", self._stop_command))
        self.application.add_handler(CommandHandler("start", self._start_command))
        
        logger.info("TelegramBot handlers registered")

    def set_callbacks(
        self,
        status: Optional[Callable[[], Awaitable[str]]] = None,
        pnl: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None,
        stop: Optional[Callable[[], Awaitable[None]]] = None,
        start: Optional[Callable[[], Awaitable[None]]] = None,
    ) -> None:
        """Set callback functions for remote commands."""
        self._status_callback = status
        self._pnl_callback = pnl
        self._stop_callback = stop
        self._start_callback = start

    async def start_polling(self) -> None:
        """Start polling for Telegram updates."""
        if not self.application:
            await self.initialize()
        
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("TelegramBot polling started")

    async def stop_polling(self) -> None:
        """Stop polling for Telegram updates."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("TelegramBot polling stopped")

    # ------------------------------------------------------------------
    # Command Handlers
    # ------------------------------------------------------------------

    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if self._status_callback:
            status = await self._status_callback()
            await update.message.reply_text(status)
        else:
            await update.message.reply_text("Status callback not configured")

    async def _pnl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pnl command."""
        if self._pnl_callback:
            pnl = await self._pnl_callback()
            message = (
                f"📊 PnL Report\n"
                f"Date: {pnl.get('date', 'Today')}\n"
                f"Daily PnL: {pnl.get('daily_pnl', 0):.2f} USDT\n"
                f"Total PnL: {pnl.get('total_pnl', 0):.2f} USDT\n"
                f"Win Rate: {pnl.get('win_rate', 0):.1f}%\n"
                f"Trades: {pnl.get('total_trades', 0)}"
            )
            await update.message.reply_text(message)
        else:
            await update.message.reply_text("PnL callback not configured")

    async def _stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stop command — halt trading."""
        if self._stop_callback:
            await self._stop_callback()
            await update.message.reply_text("🛑 Trading halted by user command")
        else:
            await update.message.reply_text("Stop callback not configured")

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command — resume trading."""
        if self._start_callback:
            await self._start_callback()
            await update.message.reply_text("✅ Trading resumed by user command")
        else:
            await update.message.reply_text("Start callback not configured")

    # ------------------------------------------------------------------
    # Alert Methods
    # ------------------------------------------------------------------

    async def send_trade_alert(self, trade: Dict[str, Any]) -> None:
        """Send a trade entry alert.
        
        Parameters
        ----------
        trade : dict
            Trade details: symbol, side, entry, sl, tp1, size.
        """
        emoji = "🟢" if trade.get('side') == 'buy' else "🔴"
        message = (
            f"{emoji} Trade Alert\n"
            f"Symbol: {trade.get('symbol', 'Unknown')}\n"
            f"Side: {trade.get('side', 'Unknown').upper()}\n"
            f"Entry: {trade.get('entry', 0):.2f}\n"
            f"SL: {trade.get('sl', 0):.2f}\n"
            f"TP1: {trade.get('tp1', 0):.2f}\n"
            f"Size: {trade.get('size', 0):.4f}"
        )
        await self._send_message(message)

    async def send_exit_alert(self, trade: Dict[str, Any]) -> None:
        """Send a trade exit alert with PnL."""
        pnl = trade.get('pnl', 0)
        emoji = "🟢" if pnl > 0 else "🔴"
        message = (
            f"{emoji} Trade Closed\n"
            f"Symbol: {trade.get('symbol', 'Unknown')}\n"
            f"PnL: {pnl:.2f} USDT\n"
            f"Exit: {trade.get('exit_price', 0):.2f}"
        )
        await self._send_message(message)

    async def send_error_alert(self, error_message: str) -> None:
        """Send an error notification."""
        message = f"⚠️ Error Alert\n{error_message}"
        await self._send_message(message)

    async def send_kill_switch_alert(self, reason: str) -> None:
        """Send a kill switch activation alert."""
        message = f"🛑 KILL SWITCH ACTIVATED\nReason: {reason}\nTrading halted until manual reset."
        await self._send_message(message)

    async def send_daily_report(self, stats: Dict[str, Any]) -> None:
        """Send a daily PnL report."""
        message = (
            f"📊 Daily Report\n"
            f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
            f"Total Trades: {stats.get('total_trades', 0)}\n"
            f"Win Rate: {stats.get('win_rate', 0):.1f}%\n"
            f"Total PnL: {stats.get('total_pnl', 0):.2f} USDT\n"
            f"Profit Factor: {stats.get('profit_factor', 0)}\n"
            f"Max Drawdown: {stats.get('max_drawdown', 0):.2f} USDT"
        )
        await self._send_message(message)

    async def _send_message(self, message: str) -> None:
        """Send a message to the configured chat."""
        if not self.application:
            logger.warning("TelegramBot not initialized, cannot send message")
            return
        
        try:
            await self.application.bot.send_message(chat_id=self.chat_id, text=message)
        except Exception as e:
            logger.error("Failed to send Telegram message: %s", e)
