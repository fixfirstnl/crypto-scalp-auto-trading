"""Crypto Scalp Auto Trading System — Entry Point.

3-layer architecture:
  Layer 1 (Data): BybitDataClient, WebSocketFeed, DataCache, IndicatorEngine
  Layer 2 (Agentic): TradingCrew with Bias/Signal/Risk/Execution agents
  Layer 3 (Trading): ExecutionEngine, OrderManager, PositionTracker, RiskManager

Strategy: ICT/SMC hybrid scalping on Bybit perpetual futures.
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

from src.utils import setup_logger, TelegramBot, NewsFilter, DatabaseManager
from src.layer1_data import BybitDataClient, WebSocketFeed, DataCache, IndicatorEngine, HistoricalLoader
from src.layer3_trading import ExecutionEngine, OrderManager, PositionTracker, RiskManager
from src.strategy import ICTSMCStrategy
from src.layer2_agents import TradingCrew

# Load environment variables
load_dotenv()

# Global logger
logger = setup_logger("main", level="INFO", log_file="logs/main.log")

# Graceful shutdown flag
_shutdown_event = asyncio.Event()


class ConfigLoader:
    """Load and merge YAML configs with environment variable overrides."""

    @staticmethod
    def load(path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def merge_env(config: Dict[str, Any]) -> Dict[str, Any]:
        """Override config values with environment variables."""
        if "bybit" in config:
            config["bybit"]["api_key"] = os.getenv(
                "BYBIT_API_KEY", config["bybit"].get("api_key", "")
            )
            config["bybit"]["api_secret"] = os.getenv(
                "BYBIT_API_SECRET", config["bybit"].get("api_secret", "")
            )
        return config


class TradingSystem:
    """Main trading system orchestrator."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.telegram: Optional[TelegramBot] = None
        self.news_filter: Optional[NewsFilter] = None
        self.database: Optional[DatabaseManager] = None
        
        # Layer 1
        self.bybit_client: Optional[BybitDataClient] = None
        self.websocket_feed: Optional[WebSocketFeed] = None
        self.data_cache: Optional[DataCache] = None
        self.indicator_engine: Optional[IndicatorEngine] = None
        self.historical_loader: Optional[HistoricalLoader] = None
        
        # Layer 3
        self.execution_engine: Optional[ExecutionEngine] = None
        self.order_manager: Optional[OrderManager] = None
        self.position_tracker: Optional[PositionTracker] = None
        self.risk_manager: Optional[RiskManager] = None
        
        # Strategy
        self.strategy: Optional[ICTSMCStrategy] = None
        
        # Layer 2
        self.trading_crew: Optional[TradingCrew] = None
        
        self._running = False

    async def initialize(self) -> None:
        """Initialize all subsystems."""
        logger.info("Initializing Trading System...")

        # 1. Utils layer
        await self._init_utils()

        # 2. Data layer (Layer 1)
        await self._init_data_layer()

        # 3. Trading layer (Layer 3)
        await self._init_trading_layer()

        # 4. Strategy layer
        await self._init_strategy()

        # 5. Agentic layer (Layer 2)
        await self._init_agent_layer()

        # 6. Start Telegram polling
        if self.telegram:
            await self.telegram.start_polling()

        logger.info("Trading System initialized successfully")

    async def _init_utils(self) -> None:
        """Initialize utility services."""
        # Telegram Bot
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if bot_token and chat_id:
            self.telegram = TelegramBot(bot_token, chat_id)
            await self.telegram.initialize()
            self.telegram.set_callbacks(
                status=self._get_status,
                pnl=self._get_daily_pnl,
                stop=self._halt_trading,
                start=self._resume_trading,
            )
            logger.info("Telegram bot initialized")
        else:
            logger.warning("Telegram credentials not found; alerts disabled")

        # News Filter
        news_buffer = (
            self.config.get("strategy", {})
            .get("filters", {})
            .get("news_buffer_minutes", 15)
        )
        self.news_filter = NewsFilter(news_buffer_minutes=news_buffer)
        await self.news_filter.fetch_economic_calendar(days=7)
        logger.info("News filter initialized")

        # Database Manager (SQLite)
        self.database = DatabaseManager(db_path="data/trading.db")
        self.database.init_schema()
        logger.info("Database manager initialized (SQLite)")

    async def _init_data_layer(self) -> None:
        """Initialize Layer 1: Data infrastructure."""
        bybit_cfg = self.config.get("bybit", {})
        api_key = bybit_cfg.get("api_key", "")
        api_secret = bybit_cfg.get("api_secret", "")
        testnet = bybit_cfg.get("testnet", True)
        
        # Data cache (Redis optional, in-memory fallback)
        self.data_cache = DataCache(use_redis=False)
        
        # Indicator engine
        self.indicator_engine = IndicatorEngine(self.data_cache)
        
        # Bybit client
        self.bybit_client = BybitDataClient(api_key, api_secret, testnet=testnet)
        
        # WebSocket feed
        self.websocket_feed = WebSocketFeed(self.bybit_client)
        
        # Historical loader
        self.historical_loader = HistoricalLoader(self.bybit_client)
        
        logger.info("Layer 1 (Data) initialized")

    async def _init_trading_layer(self) -> None:
        """Initialize Layer 3: Trading infrastructure."""
        bybit_cfg = self.config.get("bybit", {})
        api_key = bybit_cfg.get("api_key", "")
        api_secret = bybit_cfg.get("api_secret", "")
        testnet = bybit_cfg.get("testnet", True)
        
        # Execution engine
        self.execution_engine = ExecutionEngine(api_key, api_secret, testnet=testnet)
        
        # Order manager
        self.order_manager = OrderManager(self.execution_engine)
        
        # Position tracker
        self.position_tracker = PositionTracker(db_path="data/trades.db")
        
        # Risk manager
        strategy_cfg = self.config.get("strategy", {})
        self.risk_manager = RiskManager(
            account_balance=1000.0,  # Will be updated from exchange
            risk_per_trade=strategy_cfg.get("risk_per_trade", 0.005),
            max_positions=strategy_cfg.get("max_positions", 5),
            daily_loss_limit=strategy_cfg.get("daily_loss_limit", 0.03),
            weekly_loss_limit=strategy_cfg.get("weekly_loss_limit", 0.07),
            max_consecutive_losses=strategy_cfg.get("max_consecutive_losses", 4),
            max_drawdown=strategy_cfg.get("max_drawdown", 0.05),
        )
        
        logger.info("Layer 3 (Trading) initialized")

    async def _init_strategy(self) -> None:
        """Initialize ICT/SMC strategy components."""
        self.strategy = ICTSMCStrategy(self.data_cache, self.indicator_engine)
        logger.info("Strategy layer initialized (ICT/SMC)")

    async def _init_agent_layer(self) -> None:
        """Initialize Layer 2: Agentic CrewAI system."""
        self.trading_crew = TradingCrew(
            data_cache=self.data_cache,
            indicator_engine=self.indicator_engine,
            strategy=self.strategy,
            risk_manager=self.risk_manager,
            order_manager=self.order_manager,
            position_tracker=self.position_tracker,
        )
        logger.info("Layer 2 (Agents) initialized")

    async def _get_status(self) -> str:
        """Return system status for Telegram /status command."""
        status = "🟢 System Running\n"
        status += f"Trading: {'Enabled' if self._running else 'Paused'}\n"
        if self.news_filter:
            block, reason = self.news_filter.should_block_trading()
            if block:
                status += f"⚠️ News Block: {reason}\n"
        return status

    async def _get_daily_pnl(self) -> Dict[str, Any]:
        """Return daily PnL stats for Telegram /pnl command."""
        if self.position_tracker:
            stats = self.position_tracker.get_stats()
            stats["date"] = "Today"
            return stats
        return {"pnl": 0, "win_rate": 0, "total_trades": 0}

    async def _halt_trading(self) -> None:
        """Halt trading (Telegram /stop command)."""
        self._running = False
        logger.warning("Trading halted by user command")

    async def _resume_trading(self) -> None:
        """Resume trading (Telegram /start command)."""
        self._running = True
        logger.info("Trading resumed by user command")

    async def _check_kill_switches(self) -> tuple[bool, str]:
        """Check all kill switch conditions.

        Returns:
            Tuple of (should_kill, reason).
        """
        # News-based kill switch
        if self.news_filter:
            block, reason = self.news_filter.should_block_trading()
            if block:
                return True, f"News Kill Switch: {reason}"

        # Drawdown-based kill switch
        if self.position_tracker:
            daily_pnl = self.position_tracker.get_daily_pnl()
            total_pnl = self.position_tracker.get_total_pnl()
            # Check daily loss limit
            strategy_cfg = self.config.get("strategy", {})
            daily_limit = strategy_cfg.get("daily_loss_limit", 0.03)
            if daily_pnl < -daily_limit * 1000:  # Assuming 1000 balance for now
                return True, f"Daily Loss Limit Hit: {daily_pnl:.2f}"

        return False, ""

    async def run_trading_loop(self) -> None:
        """Main trading loop with 1-minute signal checks."""
        self._running = True
        logger.info("Trading loop started")

        # Start WebSocket feeds
        symbols = self.config.get("bybit", {}).get("symbols", ["BTC/USDT:USDT", "ETH/USDT:USDT"])
        timeframes = self.config.get("bybit", {}).get("timeframes", ["1m", "5m", "15m", "1h"])
        
        try:
            await self.websocket_feed.start(symbols, timeframes)
            logger.info(f"WebSocket feeds started for {symbols}")
        except Exception as e:
            logger.error(f"Failed to start WebSocket feeds: {e}")
            if self.telegram:
                await self.telegram.send_error_alert(f"WebSocket error: {e}")

        while not _shutdown_event.is_set():
            try:
                # Check kill switches
                should_kill, kill_reason = await self._check_kill_switches()
                if should_kill:
                    logger.error(f"KILL SWITCH: {kill_reason}")
                    if self.telegram:
                        await self.telegram.send_kill_switch_alert(kill_reason)
                    self._running = False
                    await asyncio.sleep(60)
                    continue

                if not self._running:
                    await asyncio.sleep(10)
                    continue

                # Main trading logic
                for symbol in symbols:
                    try:
                        # Run agent pipeline
                        signal = await self.trading_crew.run_signal_pipeline(symbol)
                        
                        if signal and signal.get("consensus") in ["buy", "sell"]:
                            trade = signal.get("trade")
                            if trade:
                                # Execute trade
                                side = "buy" if signal["consensus"] == "buy" else "sell"
                                await self.order_manager.enter_position(
                                    symbol=symbol,
                                    side=side,
                                    entry_price=trade["entry_price"],
                                    stop_loss=trade["stop_loss"],
                                    take_profit_1=trade["take_profit_1"],
                                    take_profit_2=trade["take_profit_2"],
                                    take_profit_3=trade["take_profit_3"],
                                    size=trade["size"],
                                    order_type=trade.get("order_type", "limit"),
                                )
                                
                                # Log to database
                                if self.database:
                                    self.database.save_signal({
                                        "symbol": symbol,
                                        "timeframe": "1m",
                                        "side": side,
                                        "confidence": signal.get("confidence", 0),
                                        "strategy": "ICT/SMC",
                                        "entry_price": trade["entry_price"],
                                        "stop_loss": trade["stop_loss"],
                                        "take_profit": trade["take_profit_1"],
                                    })
                                
                                # Alert
                                if self.telegram:
                                    await self.telegram.send_trade_alert({
                                        "symbol": symbol,
                                        "side": side,
                                        "entry": trade["entry_price"],
                                        "sl": trade["stop_loss"],
                                        "tp1": trade["take_profit_1"],
                                        "size": trade["size"],
                                    })
                                
                                logger.info(f"Trade executed: {symbol} {side}")
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                        if self.database:
                            self.database.log_error("trading_loop", type(e).__name__, str(e))

                # Monitor open positions
                if self.order_manager:
                    await self._monitor_positions()

                await asyncio.sleep(60)

            except asyncio.CancelledError:
                logger.info("Trading loop cancelled")
                break
            except Exception as e:
                logger.exception(f"Error in trading loop: {e}")
                if self.telegram:
                    await self.telegram.send_error_alert(str(e))
                if self.database:
                    self.database.log_error("main", type(e).__name__, str(e))
                await asyncio.sleep(5)

    async def _monitor_positions(self) -> None:
        """Monitor and manage open positions."""
        # Get open positions from position tracker
        open_positions = self.position_tracker.get_open_positions()
        for pos in open_positions:
            try:
                await self.order_manager.manage_partials(pos["symbol"], pos)
            except Exception as e:
                logger.error(f"Error managing position {pos['symbol']}: {e}")

    async def shutdown(self) -> None:
        """Graceful shutdown of all subsystems."""
        logger.info("Shutting down Trading System...")
        self._running = False

        if self.websocket_feed:
            await self.websocket_feed.stop()

        if self.telegram:
            await self.telegram.stop_polling()

        if self.database:
            self.database.disconnect()

        if self.bybit_client:
            await self.bybit_client.close()

        logger.info("Trading System shutdown complete")


def _signal_handler(sig: int, frame: Any) -> None:
    """Handle OS signals for graceful shutdown."""
    logger.info(f"Received signal {sig}, initiating shutdown...")
    _shutdown_event.set()


async def main() -> None:
    """Application entry point."""
    # Setup signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Load configurations
    config_loader = ConfigLoader()
    bybit_config = config_loader.load("config/bybit_config.yaml")
    strategy_config = config_loader.load("config/strategy_config.yaml")
    agent_config = config_loader.load("config/agent_config.yaml")

    merged_config = {
        "bybit": bybit_config.get("bybit", {}),
        "strategy": strategy_config.get("strategy", {}),
        "agents": agent_config.get("agents", {}),
    }
    merged_config = config_loader.merge_env(merged_config)

    # Ensure directories exist
    Path("logs").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)

    # Initialize and run trading system
    system = TradingSystem(merged_config)
    await system.initialize()

    try:
        await system.run_trading_loop()
    finally:
        await system.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
