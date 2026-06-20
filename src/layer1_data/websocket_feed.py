"""
WebSocket Feed Manager
=====================
Manages concurrent WebSocket streams for multiple symbols and timeframes.

Features
--------
- One asyncio task per symbol+timeframe OHLCV stream
- One asyncio task per symbol order book stream
- Auto-reconnect with exponential backoff (max 60 s)
- Event emission via ``asyncio.Queue`` for downstream consumers
- Graceful stop with task cancellation

Architecture
------------
    ┌──────────────┐      ┌──────────────┐
    │ Bybit WS     │ ──▶  │ _on_ohlcv   │ ──▶  asyncio.Queue("candles")
    │ (CCXT Pro)   │      │ callback     │
    └──────────────┘      └──────────────┘

    ┌──────────────┐      ┌──────────────┐
    │ Bybit WS     │ ──▶  │ _on_orderbook│ ──▶  asyncio.Queue("orderbook")
    │ (CCXT Pro)   │      │ callback     │
    └──────────────┘      └──────────────┘

Example
-------
    client = BybitDataClient(api_key, api_secret, testnet=True)
    feed = WebSocketFeed(client)
    await feed.start(
        symbols=["BTC/USDT:USDT", "ETH/USDT:USDT"],
        timeframes=["1m", "5m", "15m", "1h"]
    )
    # ... consume from feed.candle_queue, feed.orderbook_queue
    await feed.stop()
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set

from .bybit_client import BybitDataClient

logger = logging.getLogger(__name__)


class WebSocketFeed:
    """
    Async WebSocket feed manager for Bybit multi-symbol / multi-timeframe streaming.

    Parameters
    ----------
    bybit_client : BybitDataClient
        Initialized CCXT Pro wrapper.
    reconnect_base_delay : float, default 1.0
        Initial seconds to wait before reconnecting (doubles each retry).
    reconnect_max_delay : float, default 60.0
        Cap on reconnect backoff.
    reconnect_max_attempts : int, default 10
        Max reconnect attempts per stream before giving up.
    """

    def __init__(
        self,
        bybit_client: BybitDataClient,
        reconnect_base_delay: float = 1.0,
        reconnect_max_delay: float = 60.0,
        reconnect_max_attempts: int = 10,
    ) -> None:
        self.client: BybitDataClient = bybit_client

        self.reconnect_base_delay: float = reconnect_base_delay
        self.reconnect_max_delay: float = reconnect_max_delay
        self.reconnect_max_attempts: int = reconnect_max_attempts

        # Active tasks
        self._tasks: Set[asyncio.Task] = set()
        self._running: bool = False

        # Event queues for consumers (Layer 2 agents)
        self.candle_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self.orderbook_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self.ticker_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=500)

        # Internal bookkeeping
        self._symbols: List[str] = []
        self._timeframes: List[str] = []

        logger.info(
            "WebSocketFeed initialized | base_delay=%.1fs max_delay=%.1fs max_attempts=%d",
            reconnect_base_delay,
            reconnect_max_delay,
            reconnect_max_attempts,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(
        self,
        symbols: List[str],
        timeframes: List[str],
        watch_tickers: bool = True,
    ) -> None:
        """
        Start all WebSocket streams.

        Spawns one task per (symbol, timeframe) for OHLCV and one task per
        symbol for order books. Optionally watches tickers too.

        Parameters
        ----------
        symbols : List[str]
            E.g. ``["BTC/USDT:USDT", "ETH/USDT:USDT"]``.
        timeframes : List[str]
            E.g. ``["1m", "5m", "15m", "1h"]``.
        watch_tickers : bool, default True
            Also start ticker streams for each symbol.
        """
        self._symbols = symbols
        self._timeframes = timeframes
        self._running = True

        # OHLCV streams
        for symbol in symbols:
            for tf in timeframes:
                task = asyncio.create_task(
                    self._stream_ohlcv(symbol, tf),
                    name=f"ohlcv_{symbol}_{tf}",
                )
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
                logger.info("Started OHLCV stream | symbol=%s timeframe=%s", symbol, tf)

        # Order book streams
        for symbol in symbols:
            task = asyncio.create_task(
                self._stream_orderbook(symbol),
                name=f"orderbook_{symbol}",
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            logger.info("Started orderbook stream | symbol=%s", symbol)

        # Ticker streams
        if watch_tickers:
            for symbol in symbols:
                task = asyncio.create_task(
                    self._stream_ticker(symbol),
                    name=f"ticker_{symbol}",
                )
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
                logger.info("Started ticker stream | symbol=%s", symbol)

    async def stop(self) -> None:
        """
        Gracefully stop all WebSocket streams.

        Cancels tasks, waits for completion, then closes the underlying
        CCXT Pro exchange connections.
        """
        self._running = False
        logger.info("WebSocketFeed stopping... tasks=%d", len(self._tasks))

        if self._tasks:
            for task in list(self._tasks):
                task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        await self.client.close()
        logger.info("WebSocketFeed stopped")

    # ------------------------------------------------------------------
    # Internal streams
    # ------------------------------------------------------------------

    async def _stream_ohlcv(self, symbol: str, timeframe: str) -> None:
        """Background task: watch OHLCV with exponential backoff reconnect."""
        attempt = 0
        while self._running:
            try:
                # CCXT Pro watch_ohlcv blocks until a new candle arrives
                candles = await self.client.watch_ohlcv(symbol, timeframe)
                attempt = 0  # Reset on success
                await self._on_ohlcv(symbol, timeframe, candles)
            except asyncio.CancelledError:
                logger.debug("OHLCV stream cancelled | %s %s", symbol, timeframe)
                raise
            except Exception as exc:
                attempt += 1
                if attempt > self.reconnect_max_attempts:
                    logger.error(
                        "OHLCV stream max reconnects reached | %s %s. Giving up.",
                        symbol,
                        timeframe,
                    )
                    break
                delay = min(
                    self.reconnect_base_delay * (2 ** (attempt - 1)),
                    self.reconnect_max_delay,
                )
                logger.warning(
                    "OHLCV stream error | %s %s (attempt %d/%d): %s. Reconnecting in %.1fs",
                    symbol,
                    timeframe,
                    attempt,
                    self.reconnect_max_attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

    async def _stream_orderbook(self, symbol: str) -> None:
        """Background task: watch L2 order book with reconnect."""
        attempt = 0
        while self._running:
            try:
                ob = await self.client.watch_order_book(symbol)
                attempt = 0
                await self._on_orderbook(symbol, ob)
            except asyncio.CancelledError:
                logger.debug("Orderbook stream cancelled | %s", symbol)
                raise
            except Exception as exc:
                attempt += 1
                if attempt > self.reconnect_max_attempts:
                    logger.error(
                        "Orderbook stream max reconnects reached | %s. Giving up.", symbol
                    )
                    break
                delay = min(
                    self.reconnect_base_delay * (2 ** (attempt - 1)),
                    self.reconnect_max_delay,
                )
                logger.warning(
                    "Orderbook stream error | %s (attempt %d/%d): %s. Reconnecting in %.1fs",
                    symbol,
                    attempt,
                    self.reconnect_max_attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

    async def _stream_ticker(self, symbol: str) -> None:
        """Background task: watch ticker with reconnect."""
        attempt = 0
        while self._running:
            try:
                ticker = await self.client.watch_ticker(symbol)
                attempt = 0
                await self._on_ticker(symbol, ticker)
            except asyncio.CancelledError:
                logger.debug("Ticker stream cancelled | %s", symbol)
                raise
            except Exception as exc:
                attempt += 1
                if attempt > self.reconnect_max_attempts:
                    logger.error(
                        "Ticker stream max reconnects reached | %s. Giving up.", symbol
                    )
                    break
                delay = min(
                    self.reconnect_base_delay * (2 ** (attempt - 1)),
                    self.reconnect_max_delay,
                )
                logger.warning(
                    "Ticker stream error | %s (attempt %d/%d): %s. Reconnecting in %.1fs",
                    symbol,
                    attempt,
                    self.reconnect_max_attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

    # ------------------------------------------------------------------
    # Callbacks (emit to queues)
    # ------------------------------------------------------------------

    async def _on_ohlcv(
        self, symbol: str, timeframe: str, candles: List[List[float]]
    ) -> None:
        """
        Handle incoming OHLCV update.

        Emits a dict to ``self.candle_queue``. The last candle in the batch
        is the most recent (possibly still open).
        """
        if not candles:
            return

        event = {
            "event": "ohlcv",
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": time.time_ns() // 1_000_000,  # ms
            "candles": candles,  # [[ts, o, h, l, c, v], ...]
            "latest": candles[-1],  # most recent candle
        }
        try:
            self.candle_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("candle_queue full — dropping oldest")
            try:
                self.candle_queue.get_nowait()
                self.candle_queue.put_nowait(event)
            except asyncio.QueueEmpty:
                pass

    async def _on_orderbook(self, symbol: str, orderbook: Dict[str, Any]) -> None:
        """Handle incoming L2 order book update."""
        event = {
            "event": "orderbook",
            "symbol": symbol,
            "timestamp": time.time_ns() // 1_000_000,
            "bids": orderbook.get("bids", []),
            "asks": orderbook.get("asks", []),
            "nonce": orderbook.get("nonce"),
            "datetime": orderbook.get("datetime"),
        }
        try:
            self.orderbook_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("orderbook_queue full — dropping oldest")
            try:
                self.orderbook_queue.get_nowait()
                self.orderbook_queue.put_nowait(event)
            except asyncio.QueueEmpty:
                pass

    async def _on_ticker(self, symbol: str, ticker: Dict[str, Any]) -> None:
        """Handle incoming ticker update."""
        event = {
            "event": "ticker",
            "symbol": symbol,
            "timestamp": time.time_ns() // 1_000_000,
            "last": ticker.get("last"),
            "bid": ticker.get("bid"),
            "ask": ticker.get("ask"),
            "volume": ticker.get("volume"),
            "change": ticker.get("change"),
            "percentage": ticker.get("percentage"),
        }
        try:
            self.ticker_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("ticker_queue full — dropping oldest")
            try:
                self.ticker_queue.get_nowait()
                self.ticker_queue.put_nowait(event)
            except asyncio.QueueEmpty:
                pass
