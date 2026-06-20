"""Telegram bot for trade alerts, notifications, and remote commands."""

import asyncio
import logging
from typing import Dict, Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

logger = logging.getLogger(__name__)


class TelegramBot:
    """Async Telegram bot for trading alerts and remote control.

    Supports:
    - Trade alerts with formatted messages
    - Error notifications
    - Daily PnL reports
    - Kill switch alerts
    - Remote commands: /status, /stop, /start, /pnl
    """

    def __init__(self, bot_token: str, chat_id: str) -> None:
        """Initialize the Telegram bot.

        Args:
            bot_token: Telegram Bot API token from @BotFather.
            chat_id: Target chat ID for notifications (group or user).
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.app: Optional[Application] = None
        self._trading_enabled = True
        self._status_callback: Optional[callable] = None
        self._pnl_callback: Optional[callable] = None
        self._stop_callback: Optional[callable] = None
        self._start_callback: Optional[callable] = None

    async def initialize(self) -> None:
        """Initialize the Telegram application."""
        self.app = Application.builder().token(self.bot_token).build()
        self._register_handlers()
        await self.app.initialize()
        logger.info("Telegram bot initialized")

    def _register_handlers(self) -> None:
        """Register command handlers."""
        handlers = [
            CommandHandler("status", self._cmd_status),
            CommandHandler("stop", self._cmd_stop),
            CommandHandler("start", self._cmd_start),
            CommandHandler("pnl", self._cmd_pnl),
        ]
        for handler in handlers:
            self.app.add_handler(handler)

    def set_callbacks(
        self,
        status: Optional[callable] = None,
        pnl: Optional[callable] = None,
        stop: Optional[callable] = None,
        start: Optional[callable] = None,
    ) -> None:
        """Register callbacks for command handlers."""
        self._status_callback = status
        self._pnl_callback = pnl
        self._stop_callback = stop
        self._start_callback = start

    async def send_message(self, text: str) -> None:
        """Send a plain text message to the configured chat."""
        if not self.app:
            logger.warning("Telegram bot not initialized, skipping message")
            return
        try:
            await self.app.bot.send_message(
                chat_id=self.chat_id, text=text, parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    async def send_trade_alert(self, trade: Dict) -> None:
        """Send a formatted trade alert.

        Args:
            trade: Dict with keys: symbol, side, entry, stop_loss,
                   take_profit, size, confidence, reason.
        """
        emoji = "🟢" if trade.get("side", "").upper() == "BUY" else "🔴"
        message = (
            f"{emoji} <b>TRADE ALERT</b> {emoji}\n\n"
            f"<b>Symbol:</b> {trade.get('symbol', 'N/A')}\n"
            f"<b>Side:</b> {trade.get('side', 'N/A')}\n"
            f"<b>Entry:</b> {trade.get('entry', 'N/A')}\n"
            f"<b>Stop Loss:</b> {trade.get('stop_loss', 'N/A')}\n"
            f"<b>Take Profit:</b> {trade.get('take_profit', 'N/A')}\n"
            f"<b>Size:</b> {trade.get('size', 'N/A')}\n"
            f"<b>Confidence:</b> {trade.get('confidence', 'N/A')}%\n"
            f"<b>Reason:</b> {trade.get('reason', 'N/A')}\n"
            f"<b>Time:</b> {trade.get('timestamp', 'N/A')}"
        )
        await self.send_message(message)

    async def send_error_alert(self, error: str) -> None:
        """Send an error notification."""
        message = f"🚨 <b>ERROR ALERT</b> 🚨\n\n<code>{error}</code>"
        await self.send_message(message)

    async def send_daily_report(self, stats: Dict) -> None:
        """Send a daily PnL and performance report.

        Args:
            stats: Dict with keys: pnl, win_rate, total_trades, wins, losses,
                   avg_profit, avg_loss, max_drawdown, date.
        """
        pnl_emoji = "🟢" if stats.get("pnl", 0) >= 0 else "🔴"
        message = (
            f"📊 <b>DAILY REPORT</b> 📊\n\n"
            f"<b>Date:</b> {stats.get('date', 'N/A')}\n"
            f"{pnl_emoji} <b>PnL:</b> {stats.get('pnl', 0):.4f} USDT\n"
            f"<b>Win Rate:</b> {stats.get('win_rate', 0):.1f}%\n"
            f"<b>Total Trades:</b> {stats.get('total_trades', 0)}\n"
            f"<b>Wins:</b> {stats.get('wins', 0)} | <b>Losses:</b> {stats.get('losses', 0)}\n"
            f"<b>Avg Profit:</b> {stats.get('avg_profit', 0):.4f}\n"
            f"<b>Avg Loss:</b> {stats.get('avg_loss', 0):.4f}\n"
            f"<b>Max Drawdown:</b> {stats.get('max_drawdown', 0):.2f}%"
        )
        await self.send_message(message)

    async def send_kill_switch_alert(self, reason: str) -> None:
        """Send a kill switch activation alert."""
        message = (
            f"⛔ <b>KILL SWITCH ACTIVATED</b> ⛔\n\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Action:</b> All trading halted. Manual review required."
        )
        await self.send_message(message)

    async def start_polling(self) -> None:
        """Start polling for Telegram commands (non-blocking)."""
        if not self.app:
            await self.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        logger.info("Telegram bot polling started")

    async def stop_polling(self) -> None:
        """Stop polling gracefully."""
        if self.app and self.app.updater:
            await self.app.updater.stop()
            await self.app.stop()
            logger.info("Telegram bot polling stopped")

    # Command handlers
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if self._status_callback:
            status = await self._status_callback()
            await update.message.reply_text(f"📋 Status:\n{status}", parse_mode="HTML")
        else:
            await update.message.reply_text(
                f"Trading enabled: {self._trading_enabled}"
            )

    async def _cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stop command — halt trading."""
        self._trading_enabled = False
        if self._stop_callback:
            await self._stop_callback()
        await update.message.reply_text("🛑 Trading halted. Use /start to resume.")
        logger.warning("Trading halted via Telegram command")

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command — resume trading."""
        self._trading_enabled = True
        if self._start_callback:
            await self._start_callback()
        await update.message.reply_text("✅ Trading resumed.")
        logger.info("Trading resumed via Telegram command")

    async def _cmd_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pnl command — show daily PnL."""
        if self._pnl_callback:
            stats = await self._pnl_callback()
            pnl_emoji = "🟢" if stats.get("pnl", 0) >= 0 else "🔴"
            text = (
                f"{pnl_emoji} <b>Today's PnL:</b> {stats.get('pnl', 0):.4f} USDT\n"
                f"<b>Win Rate:</b> {stats.get('win_rate', 0):.1f}%\n"
                f"<b>Trades:</b> {stats.get('total_trades', 0)}"
            )
            await update.message.reply_text(text, parse_mode="HTML")
        else:
            await update.message.reply_text("PnL data not available.")
