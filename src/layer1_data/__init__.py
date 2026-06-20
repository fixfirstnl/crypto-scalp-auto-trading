"""
Layer 1: Data Layer
===================
Crypto scalping trading system — market data ingestion, caching, and indicators.

This module provides all data infrastructure components for the ICT/SMC hybrid
scalping strategy on Bybit. It handles real-time WebSocket feeds, REST API
queries, technical indicator calculations, and data caching (Redis + in-memory fallback).

Components
----------
- BybitDataClient : CCXT Pro wrapper for Bybit v5 (REST + WebSocket)
- WebSocketFeed   : Async WebSocket connection manager with auto-reconnect
- IndicatorEngine : EMA 9/21, VWAP, RSI(14), ATR(14), Volume Profile
- DataCache       : Redis cache wrapper with thread-safe in-memory fallback
- HistoricalLoader: Historical OHLCV backfill with CSV persistence

Usage
-----
    from src.layer1_data import BybitDataClient, IndicatorEngine, DataCache
    client = BybitDataClient(api_key, api_secret, testnet=True)
    cache = DataCache(use_redis=True)
    engine = IndicatorEngine(cache)

    # Fetch candles
    candles = await client.fetch_ohlcv("BTC/USDT:USDT", "1m", limit=100)
    cache.set_candles("BTCUSDT", "1m", candles)

    # Calculate indicators
    indicators = engine.calculate_all(candles)

Author: Data_Layer_Dev
Version: 1.0.0
"""

from .bybit_client import BybitDataClient
from .websocket_feed import WebSocketFeed
from .indicator_engine import IndicatorEngine
from .data_cache import DataCache
from .historical_loader import HistoricalLoader

__all__ = [
    "BybitDataClient",
    "WebSocketFeed",
    "IndicatorEngine",
    "DataCache",
    "HistoricalLoader",
]

__version__ = "1.0.0"
