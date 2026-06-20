"""
Bybit Data Client (CCXT Pro Wrapper)
=====================================
Async REST API client for Bybit v5 via CCXT Pro.

Handles:
- OHLCV candle fetching with pagination
- Real-time ticker snapshots
- L2 order book snapshots
- Account balance queries
- Rate-limit-aware request throttling (CCXT built-in)
- Testnet / live environment switching

Dependencies
------------
- ccxt[pro] >= 4.0.0 (for CCXT Pro WebSocket support)
- asyncio

Example
-------
    client = BybitDataClient(api_key="...", api_secret="...", testnet=True)
    candles = await client.fetch_ohlcv("BTC/USDT:USDT", "1m", limit=200)
    await client.close()
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import ccxt.pro as ccxt_pro

logger = logging.getLogger(__name__)


class BybitDataClient:
    """
    Async wrapper around CCXT Pro for Bybit v5.

    Parameters
    ----------
    api_key : str
        Bybit API key (read-only recommended for data layer).
    api_secret : str
        Bybit API secret.
    testnet : bool, default True
        Use Bybit testnet (paper trading). Set False for live.
    """

    # CCXT timeframe mapping for Bybit
    TIMEFRAME_MAP: Dict[str, str] = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
    }

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
    ) -> None:
        self.api_key: str = api_key
        self.api_secret: str = api_secret
        self.testnet: bool = testnet

        self.exchange: Optional[ccxt_pro.bybit] = None
        self._initialized: bool = False

        logger.info(
            "BybitDataClient configured | testnet=%s | env=%s",
            testnet,
            "testnet" if testnet else "live",
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _ensure_initialized(self) -> None:
        """Lazy-initialize the CCXT Pro exchange instance."""
        if self._initialized:
            return

        try:
            self.exchange = ccxt_pro.bybit(
                {
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "enableRateLimit": True,          # CCXT built-in rate limiter
                    "options": {
                        "defaultType": "swap",        # USDT perpetual
                        "adjustForTimeDifference": True,
                    },
                }
            )
            if self.testnet:
                self.exchange.set_sandbox_mode(True)

            await self.exchange.load_markets()
            self._initialized = True

            logger.info(
                "CCXT Pro exchange initialized | id=%s | markets=%d",
                self.exchange.id,
                len(self.exchange.markets),
            )
        except Exception as exc:
            logger.error("Failed to initialize CCXT Pro exchange: %s", exc)
            raise

    async def close(self) -> None:
        """Gracefully close all WebSocket connections and release resources."""
        if self.exchange is not None:
            try:
                await self.exchange.close()
                logger.info("CCXT Pro exchange connections closed")
            except Exception as exc:
                logger.warning("Error closing exchange: %s", exc)
            finally:
                self.exchange = None
                self._initialized = False

    # ------------------------------------------------------------------
    # Market data (REST)
    # ------------------------------------------------------------------

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        since: Optional[int] = None,
    ) -> List[List[float]]:
        """
        Fetch OHLCV candles via CCXT Pro REST.

        Parameters
        ----------
        symbol : str
            Trading pair, e.g. ``"BTC/USDT:USDT"`` (swap) or ``"BTC/USDT"`` (spot).
        timeframe : str
            One of ``"1m", "5m", "15m", "1h", "4h", "1d"``.
        limit : int, default 100
            Number of candles to fetch (max 1000 on Bybit).
        since : int, optional
            UTC timestamp in ms. If provided, fetches from that point.

        Returns
        -------
        List[List[float]]
            CCXT OHLCV format: ``[[timestamp, open, high, low, close, volume], ...]``
            sorted ascending by timestamp.

        Raises
        ------
        ValueError
            If the timeframe is not supported.
        ConnectionError
            On network or exchange API errors.
        """
        await self._ensure_initialized()
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        if timeframe not in self.TIMEFRAME_MAP:
            raise ValueError(
                f"Unsupported timeframe: {timeframe}. "
                f"Supported: {list(self.TIMEFRAME_MAP.keys())}"
            )

        ccxt_tf = self.TIMEFRAME_MAP[timeframe]

        try:
            candles: List[List[float]] = await self.exchange.fetch_ohlcv(
                symbol, ccxt_tf, since=since, limit=limit
            )
            logger.debug(
                "fetch_ohlcv | symbol=%s tf=%s limit=%d returned=%d",
                symbol,
                timeframe,
                limit,
                len(candles),
            )
            return candles
        except Exception as exc:
            logger.error(
                "fetch_ohlcv failed | symbol=%s tf=%s: %s", symbol, timeframe, exc
            )
            raise ConnectionError(f"OHLCV fetch failed: {exc}") from exc

    async def fetch_ohlcv_paginated(
        self,
        symbol: str,
        timeframe: str,
        total_limit: int = 1000,
        since: Optional[int] = None,
    ) -> List[List[float]]:
        """
        Paginated OHLCV fetch for large historical backfills.

        Bybit REST limits to ~200 candles per request for some timeframes,
        so this method loops with ``since`` offsets until ``total_limit``
        candles are accumulated.

        Parameters
        ----------
        symbol : str
            Trading pair.
        timeframe : str
            Timeframe string.
        total_limit : int, default 1000
            Total candles to collect across all pages.
        since : int, optional
            Start timestamp in ms.

        Returns
        -------
        List[List[float]]
            Concatenated and deduplicated candles, sorted ascending.
        """
        PAGE_SIZE = 200
        all_candles: List[List[float]] = []
        current_since = since

        while len(all_candles) < total_limit:
            page = await self.fetch_ohlcv(
                symbol, timeframe, limit=min(PAGE_SIZE, total_limit - len(all_candles)), since=current_since
            )
            if not page:
                break

            all_candles.extend(page)

            # Advance `since` to just after the last candle
            last_ts = int(page[-1][0])
            current_since = last_ts + 1

            # Guard against infinite loop on empty / duplicate pages
            if len(page) < PAGE_SIZE:
                break

            await asyncio.sleep(0.2)  # Light throttle between pages

        # Deduplicate by timestamp and sort
        seen: set = set()
        deduped: List[List[float]] = []
        for c in all_candles:
            ts = c[0]
            if ts not in seen:
                seen.add(ts)
                deduped.append(c)
        deduped.sort(key=lambda x: x[0])

        return deduped[:total_limit]

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current 24h ticker stats: last price, bid, ask, volume, change.

        Parameters
        ----------
        symbol : str
            Trading pair.

        Returns
        -------
        dict
            CCXT ticker object with ``last``, ``bid``, ``ask``, ``volume``, etc.
        """
        await self._ensure_initialized()
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            logger.debug("fetch_ticker | symbol=%s last=%s", symbol, ticker.get("last"))
            return ticker
        except Exception as exc:
            logger.error("fetch_ticker failed | symbol=%s: %s", symbol, exc)
            raise ConnectionError(f"Ticker fetch failed: {exc}") from exc

    async def fetch_orderbook(
        self, symbol: str, limit: int = 50
    ) -> Dict[str, Any]:
        """
        Fetch L2 order book snapshot.

        Parameters
        ----------
        symbol : str
            Trading pair.
        limit : int, default 50
            Number of bid/ask levels (max 200 on Bybit).

        Returns
        -------
        dict
            CCXT order book with ``bids``, ``asks``, ``timestamp``, ``nonce``.
        """
        await self._ensure_initialized()
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        try:
            ob = await self.exchange.fetch_order_book(symbol, limit)
            logger.debug(
                "fetch_orderbook | symbol=%s bids=%d asks=%d",
                symbol,
                len(ob.get("bids", [])),
                len(ob.get("asks", [])),
            )
            return ob
        except Exception as exc:
            logger.error("fetch_orderbook failed | symbol=%s: %s", symbol, exc)
            raise ConnectionError(f"Orderbook fetch failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Account (REST) — read-only for data layer
    # ------------------------------------------------------------------

    async def get_balance(self) -> Dict[str, Any]:
        """
        Fetch account wallet balance (USDT + coins).

        Returns
        -------
        dict
            CCXT balance structure with ``total``, ``free``, ``used``.
        """
        await self._ensure_initialized()
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        try:
            balance = await self.exchange.fetch_balance()
            logger.info(
                "get_balance | total_USDT=%s",
                balance.get("USDT", {}).get("total", 0),
            )
            return balance
        except Exception as exc:
            logger.error("get_balance failed: %s", exc)
            raise ConnectionError(f"Balance fetch failed: {exc}") from exc

    # ------------------------------------------------------------------
    # WebSocket helpers (CCXT Pro)
    # ------------------------------------------------------------------

    async def watch_ohlcv(
        self, symbol: str, timeframe: str
    ) -> List[List[float]]:
        """
        Watch a single OHLCV stream via CCXT Pro WebSocket.

        This is a *blocking* call that returns the most recent candle
        batch whenever the exchange pushes an update. Use inside an
        asyncio task loop.

        Parameters
        ----------
        symbol : str
            Trading pair.
        timeframe : str
            Timeframe string.

        Returns
        -------
        List[List[float]]
            Latest candle batch.
        """
        await self._ensure_initialized()
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        ccxt_tf = self.TIMEFRAME_MAP.get(timeframe, timeframe)
        try:
            candles = await self.exchange.watch_ohlcv(symbol, ccxt_tf)
            return candles
        except Exception as exc:
            logger.error("watch_ohlcv error | symbol=%s tf=%s: %s", symbol, timeframe, exc)
            raise

    async def watch_order_book(self, symbol: str) -> Dict[str, Any]:
        """
        Watch L2 order book via CCXT Pro WebSocket.

        Returns
        -------
        dict
            Updated order book structure.
        """
        await self._ensure_initialized()
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        try:
            ob = await self.exchange.watch_order_book(symbol)
            return ob
        except Exception as exc:
            logger.error("watch_order_book error | symbol=%s: %s", symbol, exc)
            raise

    async def watch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Watch ticker updates via CCXT Pro WebSocket.

        Returns
        -------
        dict
            Updated ticker structure.
        """
        await self._ensure_initialized()
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        try:
            ticker = await self.exchange.watch_ticker(symbol)
            return ticker
        except Exception as exc:
            logger.error("watch_ticker error | symbol=%s: %s", symbol, exc)
            raise
