"""Utils Module: Shared utilities for the trading system.

Provides logging, Telegram notifications, news filtering, and database management
services used across all layers of the architecture.

Components:
- setup_logger: Structured JSON logging with colored console output
- TelegramBot: Real-time trade alerts, PnL reports, and remote commands
- NewsFilter: Economic calendar filtering for high-impact events
- DatabaseManager: SQLite database initialization and management

Usage:
    from src.utils import setup_logger, TelegramBot, NewsFilter, DatabaseManager
    
    logger = setup_logger('my_module', level='INFO', log_file='logs/my.log')
    telegram = TelegramBot(bot_token, chat_id)
    news = NewsFilter(news_buffer_minutes=15)
    db = DatabaseManager(db_path='data/trading.db')
"""

from __future__ import annotations

from .logger import setup_logger
from .telegram_bot import TelegramBot
from .news_filter import NewsFilter
from .database_manager import DatabaseManager

__all__ = [
    'setup_logger',
    'TelegramBot',
    'NewsFilter',
    'DatabaseManager',
]
