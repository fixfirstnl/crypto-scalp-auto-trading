# Crypto Scalp Auto Trading System — Architecture Design

**Date:** 2026-06-20
**Exchange:** Bybit (API v5)
**Strategy:** ICT/SMC Hybrid Scalping (Automated)

---

## System Overview

A 3-layer automated crypto scalping system that replicates the world's best scalping strategy (ICT/Smart Money Concepts hybrid) on Bybit. The system is designed for sub-5-minute scalps on BTC/USDT and ETH/USDT perpetual contracts.

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 2: AGENTIC LAYER (Decision Intelligence)                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │  BiasAgent │  │ SignalAgent│  │  RiskAgent │  │  ExecAgent │    │
│  │ (HTF Bias) │  │ (Entry/Exit│  │ (Position  │  │ (Order     │    │
│  │            │  │  Signal)   │  │  Sizing)   │  │  Mgmt)     │    │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘    │
│        │               │               │               │            │
│        └───────────────┴───────────────┴───────────────┘            │
│                        │                                            │
│                        ▼                                            │
│              ┌─────────────────┐                                    │
│              │  ConsensusEngine │  ← CrewAI Orchestration           │
│              │  (Buy/Sell/Hold)│                                    │
│              └─────────────────┘                                    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 3: TRADING LAYER (Execution Engine)                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │  OrderMgr  │  │  Position  │  │  PnLTrack  │  │  KillSwitch│    │
│  │  (Entry)   │  │  (Tracker) │  │  (Real-time)│  │  (Circuit) │    │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘    │
│        │               │               │               │            │
│        └───────────────┴───────────────┴───────────────┘            │
│                        │                                            │
│                        ▼                                            │
│              ┌─────────────────┐                                    │
│              │  Bybit API v5   │  ← CCXT + Freqtrade Pattern      │
│              │  (REST + WS)    │                                    │
│              └─────────────────┘                                    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1: DATA LAYER (Market Data Infrastructure)                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │  CCXT Pro  │  │ Cryptofeed │  │  Redis     │  │  VectorBT  │    │
│  │  (OHLCV)   │  │  (L2 Books)│  │  (Cache)   │  │(Backtest)  │    │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘    │
│        │               │               │               │            │
│        └───────────────┴───────────────┴───────────────┘            │
│                        │                                            │
│                        ▼                                            │
│              ┌─────────────────┐                                    │
│              │  Bybit Exchange │  ← Source of Truth                  │
│              │  (Spot + Perp)  │                                    │
│              └─────────────────┘                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Data Layer

### Purpose
Real-time and historical market data ingestion, normalization, caching, and storage for the trading system.

### Components

| Component | Technology | Role |
|-----------|-----------|------|
| **Market Data Feed** | CCXT Pro (WebSocket) | Real-time OHLCV, trades, tickers from Bybit |
| **Order Book Stream** | Cryptofeed (WebSocket) | L2 order book snapshots, bid/ask spread monitoring |
| **Data Cache** | Redis | Sub-second data caching for agent access |
| **Time-Series DB** | PostgreSQL + TimescaleDB | Historical data, trade logs, PnL tracking |
| **Indicators** | pandas-ta + TA-Lib | EMA 9/21, VWAP, RSI(14), ATR(14), Volume Profile |
| **Backtesting** | VectorBT | Strategy validation, parameter optimization |

### Data Flow
1. CCXT Pro connects to Bybit WebSocket → streams 1m/5m/15m/1H OHLCV
2. Cryptofeed streams L2 order book → calculates real-time spread, depth
3. Redis caches last 100 candles per timeframe + current order book
4. PostgreSQL persists all historical data + trade execution logs
5. pandas-ta calculates indicators on cached data every candle close

### Key Design Decisions
- **OpenBB is NOT used** — it lacks real-time Bybit crypto data. CCXT is the primary data source.
- **Dual WebSocket** — CCXT Pro for OHLCV, Cryptofeed for L2 books (redundancy + specialization)
- **Redis for hot data** — sub-millisecond access for agents checking current market state
- **TimescaleDB for history** — efficient time-series queries for backtesting and analytics

---

## Layer 2: Agentic Layer

### Purpose
Multi-agent AI decision engine that replicates the ICT/SMC scalping methodology through specialized roles.

### Architecture Pattern: TradingAgents + CrewAI

Inspired by Tauric Research TradingAgents but optimized for speed (sub-second decisions, not 60-180s deliberation).

### Agents (CrewAI Roles)

| Agent | Role | Responsibility | Input | Output |
|-------|------|---------------|-------|--------|
| **BiasAgent** | Higher-Timeframe Analyst | Determines HTF market structure (bullish/bearish/neutral) | 1H/4H OHLCV + BOS/CHoCH detection | `bias: long/short/neutral` + confidence score |
| **SignalAgent** | Entry Signal Generator | Scans for liquidity sweeps + OB/FVG + EMA cross + RSI | 5m/15m OHLCV + indicators | `signal: long/short/none` + entry zone + stop/target |
| **RiskAgent** | Risk Manager | Position sizing, correlation check, daily loss guard | Account state + open positions + signal | `size: contracts` + `risk_score: 0-100` + `approve: yes/no` |
| **ExecAgent** | Execution Optimizer | Order type selection, slippage guard, partial fills | Signal + risk approval + order book | `order_type: limit/market` + `partials: [tp1, tp2, tp3]` |

### Consensus Engine
- CrewAI task flow: BiasAgent → SignalAgent → RiskAgent → ExecAgent
- Each agent can VETO the trade (RiskAgent has final say)
- Consensus requires: bias_aligned + signal_confident + risk_approved
- Execution only proceeds if ALL agents agree

### Speed Optimization
- Use lightweight LLM (GPT-4o-mini or local Phi-4) for fast inference
- Agents use rule-based logic primarily; LLM only for ambiguous cases
- Target: <500ms from signal detection to order submission

---

## Layer 3: Trading Layer

### Purpose
Order execution, position management, PnL tracking, and kill switches.

### Components

| Component | Technology | Role |
|-----------|-----------|------|
| **Execution Engine** | Custom Python (CCXT) | Direct Bybit API v5 order placement |
| **Position Manager** | Custom Python | Track open positions, partial fills, PnL |
| **Order Manager** | Custom Python | OCO brackets (SL + TP1 + TP2 + TP3) |
| **Kill Switch** | Custom Python | Circuit breaker on daily loss, drawdown, consecutive losses |
| **Monitoring** | Telegram Bot + SQLite | Real-time alerts, daily reports, error logging |

### Execution Flow
1. Agentic Layer sends approved signal to Trading Layer
2. Order Manager calculates optimal order type (limit vs market) based on spread
3. Execution Engine places bracket order: Entry + SL + TP1 + TP2 (TP3 = trailing)
4. Position Manager tracks fills and updates internal state
5. If TP1 hits → close 33% of position, move SL to breakeven
6. If TP2 hits → close 33% of position, activate trailing stop on remainder
7. Kill Switch monitors: daily loss > 3% → HALT; 4 consecutive losses → PAUSE; drawdown > 5% → REVIEW

---

## Strategy Implementation (ICT/SMC Hybrid)

### Automated Entry Rules

```python
# Pseudocode for SignalAgent
if htf_bias == "bullish":
    if liquidity_sweep_down(15m) and price_in_ob_fvg_zone(5m):
        if ltf_chooch_or_ema_cross(1m) and rsi > 40 and volume > 1.5x_avg:
            if cvd_turning_up and spread < 2x_avg:
                return Signal.LONG(entry_zone, sl_below_ob, tp1=1R, tp2=2R, tp3=3R)

elif htf_bias == "bearish":
    if liquidity_sweep_up(15m) and price_in_ob_fvg_zone(5m):
        if ltf_chooch_or_ema_cross(1m) and rsi < 60 and volume > 1.5x_avg:
            if cvd_turning_down and spread < 2x_avg:
                return Signal.SHORT(entry_zone, sl_above_ob, tp1=1R, tp2=2R, tp3=3R)
```

### Risk Parameters (Hard-Coded)

| Parameter | Value |
|-----------|-------|
| Risk per trade | 0.5% of account |
| Max open positions | 5 |
| Daily loss limit | 3% (hard halt) |
| Weekly loss limit | 7% (review required) |
| Max correlated pairs | 2 per base currency |
| Kill zone trading | London (2-5 AM EST) + NY (7-10 AM EST) |
| ATR filter | Only trade when 1x < ATR < 2x 20-day average |
| Spread guard | Skip if spread > 2x average |
| News filter | No entries ±15 min around red-folder events |

### Timeframe Configuration

| Timeframe | Purpose | Indicator Set |
|-----------|---------|---------------|
| 1H / 4H | Bias (HTF) | BOS/CHoCH, EMA slope, market structure |
| 15m | Setup | Liquidity sweep, Asian range, Order Blocks |
| 5m | Entry Zone | FVG identification, OB quality check |
| 1m | Execution | EMA 9/21 cross, RSI, volume spike, CVD |

---

## File Structure

```
crypto_scalp_auto_trading/
├── config/
│   ├── bybit_config.yaml       # API keys, testnet/live toggle
│   ├── strategy_config.yaml    # Risk params, indicator settings
│   └── agent_config.yaml       # CrewAI agent roles, LLM settings
├── src/
│   ├── layer1_data/
│   │   ├── __init__.py
│   │   ├── bybit_client.py     # CCXT Pro wrapper for Bybit
│   │   ├── websocket_feed.py   # WebSocket connection manager
│   │   ├── indicator_engine.py # EMA, VWAP, RSI, ATR, Volume Profile
│   │   ├── data_cache.py       # Redis cache wrapper
│   │   └── historical_loader.py# Backfill historical data
│   ├── layer2_agents/
│   │   ├── __init__.py
│   │   ├── crew_setup.py       # CrewAI crew configuration
│   │   ├── bias_agent.py       # HTF bias detection agent
│   │   ├── signal_agent.py     # Entry signal generation agent
│   │   ├── risk_agent.py       # Risk management agent
│   │   ├── exec_agent.py       # Execution optimization agent
│   │   └── consensus.py        # Consensus engine / voting logic
│   ├── layer3_trading/
│   │   ├── __init__.py
│   │   ├── order_manager.py    # Order placement, OCO brackets
│   │   ├── position_tracker.py # Position state, PnL calculation
│   │   ├── risk_manager.py     # Kill switches, circuit breakers
│   │   └── execution_engine.py # Direct Bybit API execution
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── ict_smc_strategy.py # Main ICT/SMC strategy implementation
│   │   ├── market_structure.py  # BOS/CHoCH detection
│   │   ├── order_blocks.py    # Order Block identification
│   │   ├── fair_value_gaps.py # FVG detection
│   │   └── liquidity_sweep.py # Liquidity sweep detection
│   └── utils/
│       ├── __init__.py
│       ├── logger.py          # Structured logging
│       ├── telegram_bot.py    # Telegram alerts
│       ├── news_filter.py     # Economic calendar filter
│       └── database.py        # PostgreSQL/TimescaleDB wrapper
├── tests/
│   ├── test_data_layer.py
│   ├── test_agents.py
│   ├── test_strategy.py
│   └── test_execution.py
├── backtest/
│   └── vectorbt_backtest.py   # VectorBT backtesting script
├── docs/
│   ├── setup.md               # Installation guide
│   └── strategy_guide.md      # Strategy documentation
├── requirements.txt
├── .env.example               # API key template
├── docker-compose.yml         # Redis + PostgreSQL + App
└── main.py                    # Entry point
```

---

## Technology Stack Summary

| Layer | Primary | Secondary | Supporting |
|-------|---------|-----------|------------|
| **Data** | CCXT Pro | Cryptofeed | Redis, pandas-ta, TA-Lib |
| **Agentic** | CrewAI | TradingAgents pattern | LangGraph (optional) |
| **Trading** | Custom CCXT execution | Freqtrade pattern | SQLite, Telegram |
| **Infra** | Docker + Docker Compose | AWS/DigitalOcean VPS | GitHub Actions |
| **Backtest** | VectorBT | Jesse (optional) | — |

---

## Implementation Phases

### Phase 1: Layer 1 (Data)
- CCXT Pro connection to Bybit testnet
- WebSocket OHLCV streaming (1m, 5m, 15m, 1H)
- Indicator calculation (EMA 9/21, VWAP, RSI, ATR, Volume)
- Redis caching layer
- Historical data backfill

### Phase 2: Layer 3 (Trading) — Build before Layer 2
- Bybit API v5 order placement (testnet)
- OCO bracket order support
- Position tracking
- Kill switch implementation
- Telegram monitoring bot

### Phase 3: Layer 2 (Agents)
- CrewAI crew setup with 4 agents
- BiasAgent: HTF structure detection
- SignalAgent: Entry signal rules (ICT/SMC)
- RiskAgent: Position sizing + daily limits
- ExecAgent: Order type + partial management
- Consensus engine

### Phase 4: Strategy + Integration
- Full ICT/SMC strategy implementation
- Market structure (BOS/CHoCH)
- Order Block + FVG detection
- Liquidity sweep logic
- End-to-end testing on testnet

### Phase 5: Backtest + Optimization
- VectorBT backtesting framework
- Walk-forward optimization
- Parameter sensitivity analysis
- Monte Carlo validation (optional Jesse)

### Phase 6: Production
- Deploy to VPS with <20ms latency to Bybit
- Switch from testnet to live (small capital)
- Paper trade for 2 weeks
- Gradual capital increase with performance gates

---

## Risk Management (System-Level)

| Layer | Risk Control |
|-------|-------------|
| **Data** | Dual WebSocket (fallback), stale data detection, reconnect logic |
| **Agentic** | Agent timeout (max 2s), rule-based override, human veto option |
| **Trading** | Daily loss halt, drawdown halt, max positions, spread guard, slippage guard |
| **Infrastructure** | Docker health checks, restart on failure, Telegram error alerts |
| **Operational** | Testnet first, small capital, gradual scaling, 24/7 monitoring |

---

*This architecture document is the blueprint for the implementation. All subsequent code must follow this design.*
