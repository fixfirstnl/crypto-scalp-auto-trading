# GitHub Repository Research: 3-Layer Crypto Scalping Trading System for Bybit

**Research Date:** 2026-07-10
**Research Specialist:** Repo_Analyst
**Target Exchange:** Bybit (API v5)
**System Architecture:** Data Layer → Agentic Layer → Trading Layer

---

## Executive Summary

This report analyzes the best open-source GitHub repositories to build a **3-layer crypto scalping trading system** on Bybit. After researching **50+ repositories** across data infrastructure, multi-agent AI frameworks, and trading execution engines, we identified optimal combinations for each layer and cross-layer integration opportunities.

**Key Finding:** There is no single repository that perfectly combines all three layers. The optimal approach is to **integrate CCXT + Cryptofeed (Data), CrewAI or TradingAgents (Agentic), and Freqtrade or Jesse (Trading)** with custom Bybit v5 connectors.

---

## Layer 1: Data Layer — Market Data Infrastructure

### 1.1 OpenBB Platform Assessment

**Repository:** [OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB)

| Metric | Value |
|--------|-------|
| Stars | ~20,000+ |
| License | AGPL-3.0 |
| Language | Python |
| Last Update | Active (2026) |

**Analysis:**
- OpenBB is a powerful **Open Data Platform (ODP)** for financial data integration
- Provides a unified REST API and Python SDK for accessing multiple data providers
- **Crypto Support:** Limited direct crypto real-time exchange connectivity
- **Bybit API:** Not natively supported as a first-class data provider
- Data providers include: yfinance, Polygon, FRED, Alpha Vantage, Deribit (crypto options), but **no direct Bybit spot/perpetual data**
- Best suited for: **fundamental data, macro indicators, equity analysis**
- **Verdict for Scalping:** ❌ **Insufficient** — OpenBB lacks real-time crypto order book, tick, and L2 data needed for sub-second scalping

### 1.2 Recommended Data Layer Repositories (Top 5)

#### 1. CCXT ⭐ TOP PICK
**Repository:** [ccxt/ccxt](https://github.com/ccxt/ccxt)

| Metric | Value |
|--------|-------|
| Stars | **43,000** |
| Forks | 8,700 |
| License | MIT |
| Languages | JS/TS, Python, C#, PHP, Go, Java |
| Last Update | June 2026 (v4.5.59) |

**Key Features:**
- **105+ cryptocurrency exchanges supported** including Bybit (certified)
- Unified API for market data, order books, OHLCV, trades, and execution
- **Bybit v5 API fully supported** (spot, perpetual, futures)
- WebSocket support via CCXT Pro for real-time data
- Rate limiting, error handling, authentication built-in
- `bybit` connector is **certified** and actively maintained

**Why for Scalping:**
- Direct Bybit API v5 access for tick data and order book snapshots
- Supports both REST (historical) and WebSocket (real-time) data feeds
- Can fetch 1-minute and sub-minute OHLCV for scalping strategies

**Verdict:** ✅ **PRIMARY DATA INFRASTRUCTURE** — Essential for any Bybit scalping system

---

#### 2. Cryptofeed
**Repository:** [bmoscon/cryptofeed](https://github.com/bmoscon/cryptofeed) *(or active forks like ElixirProtocol/cryptofeed)*

| Metric | Value |
|--------|-------|
| Stars | ~3,000+ (original), forks active |
| License | MIT |
| Language | Python 3.8+ |

**Key Features:**
- **High-performance WebSocket data feed handler** for crypto exchanges
- Supports **Bybit** (REST and WebSocket)
- Normalized L1/L2/L3 order books, trades, tickers, funding, open interest
- **Backends:** Redis, Kafka, PostgreSQL, MongoDB, InfluxDB, ZeroMQ, TCP/UDP sockets
- Extremely low latency — designed for high-frequency data consumption

**Why for Scalping:**
- Sub-second order book updates via WebSocket
- Direct backend writes to Redis/QuestDB for time-series analysis
- Supports multiple simultaneous exchange feeds for arbitrage detection

**Verdict:** ✅ **REAL-TIME DATA STREAMING** — Best for L2 order book data ingestion

---

#### 3. VectorBT
**Repository:** [polakowo/vectorbt](https://github.com/polakowo/vectorbt)

| Metric | Value |
|--------|-------|
| Stars | ~8,000+ |
| License | Apache-2.0 with Commons Clause |
| Language | Python |

**Key Features:**
- **Vectorized backtesting** at speed and scale (NumPy/Numba/Rust accelerated)
- Test thousands of strategy configurations in seconds
- Rich indicator ecosystem (TA-Lib, Pandas TA integration)
- Portfolio analytics with QuantStats integration
- Signal generation, ranking, and distribution analysis
- Built-in data access with preprocessing

**Why for Scalping:**
- Rapid backtesting of scalping strategies across thousands of parameter combinations
- Walk-forward optimization and robustness testing
- ML workflow support for predictive scalping models

**Verdict:** ✅ **BACKTESTING & RESEARCH ENGINE** — Essential for scalping strategy validation

---

#### 4. Pandas-TA + TA-Lib
**Repository:** [twopirllc/pandas-ta](https://github.com/twopirllc/pandas-ta) *(now pandas-ta-classic)*

| Metric | Value |
|--------|-------|
| Stars | ~4,000+ |
| License | MIT |
| Language | Python |

**Key Features:**
- 130+ technical indicators for Pandas DataFrames
- Optimized for financial time series analysis
- Easy integration with CCXT-fetched data

**Verdict:** ✅ **TECHNICAL ANALYSIS LIBRARY** — Core indicator library for signal generation

---

#### 5. pybybit / Bybit Official SDK
**Repository:** Search for `bybit-exchange/bybit-python-api` or community wrappers

**Note:** Bybit provides official Python SDKs. The CCXT library already encapsulates these, but for direct control, the official Bybit API v5 SDK is recommended.

**Verdict:** ⚠️ **OPTIONAL DIRECT SDK** — Use if you need features not exposed via CCXT

---

### 1.3 Data Layer Recommendation

| Component | Recommended Tool | Role |
|-----------|------------------|------|
| Real-time market data | **CCXT Pro + Cryptofeed** | L1/L2 order books, trades, tickers |
| Historical data | **CCXT** | OHLCV, historical order books |
| Backtesting engine | **VectorBT** | Strategy validation and optimization |
| Technical indicators | **pandas-ta + TA-Lib** | Signal generation |
| Data storage | **Redis + PostgreSQL/QuestDB** | Time-series data persistence |
| Data orchestration | **OpenBB (optional)** | Macro data, sentiment, alternative data |

**Primary Stack:** `CCXT` (for unified exchange access) + `Cryptofeed` (for raw WebSocket streams) + `VectorBT` (for backtesting)

---

## Layer 2: Agentic Layer — Multi-Agent AI Framework

### 2.1 "Paperclip" Framework Assessment

**Is "Paperclip" a real open-source multi-agent framework?**

**Yes.** Paperclip is a real, rapidly growing open-source project.

**Repository:** [paperclipai/paperclip](https://github.com/paperclipai/paperclip)

| Metric | Value |
|--------|-------|
| Stars | **38,000+** (as of April 2026) |
| License | MIT |
| Language | Node.js (React UI + API server) |
| Last Update | Active (June 2026) |

**Key Features:**
- **"Bring your own agent" orchestration** — works with Claude Code, Codex, Cursor, OpenClaw, any OpenRouter model
- Org charts, budgets, governance, and goal alignment for AI agent companies
- Heartbeat scheduling, cost tracking, ticket system, approval gates
- Multi-company support with data isolation
- React dashboard for monitoring agent fleets

**Analysis for Trading:**
- Paperclip is **NOT a trading-specific framework** — it's a general-purpose agent company orchestrator
- No native market data connectors, order execution, or risk management
- However, it can **orchestrate trading agents** if you build them as custom agents
- The `paperclip-zero-human-trading-firm` project demonstrates a 6-agent trading firm setup (CEO, Research, Backtest, Risk, Execution, Cost Optimizer)

**Verdict:** ⚠️ **ORCHESTRATION SHELL** — Useful for managing multiple AI agents, but requires custom trading agent development

---

### 2.2 TradingAgents by Tauric Research

**Repository:** [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)

| Metric | Value |
|--------|-------|
| License | Apache-2.0 / MIT |
| Language | Python 3.12 |
| Framework | LangGraph |
| Last Update | v0.2.5 (May 2026) |

**Key Features:**
- **Multi-agent LLM trading framework** that mirrors real trading firms
- **7 specialized agents:**
  - Fundamentals Analyst
  - Sentiment Analyst
  - News Analyst
  - Technical Analyst (MACD, RSI, etc.)
  - Bull Researcher
  - Bear Researcher
  - Trader Agent (synthesizes all reports)
  - Risk Manager + Portfolio Manager (gates execution)
- **Debate-style consensus building** — bullish vs bearish researchers critique analyst outputs
- Multi-provider LLM support: OpenAI, Anthropic, Google, DeepSeek, Qwen, GLM, Ollama, OpenRouter
- Built-in CLI and FastAPI/uvicorn wrapper for REST API deployment
- Persistent decision logs, agent memory, checkpoint resume
- **yfinance** built-in for free data; Alpha Vantage optional
- Supports backtesting with date parameter

**Analysis for Scalping:**
- **Research-grade, not execution-grade** — explicitly designed for research, not live trading
- Agents perform deep deliberation (60–180 seconds per analysis) — **too slow for scalping**
- No Bybit API integration; only Yahoo Finance / Alpha Vantage
- No real-time order execution; simulated exchange only
- **However:** The multi-agent architecture (analyst → researcher → trader → risk) is an excellent **template** for a scalping system

**Verdict:** ⚠️ **ARCHITECTURAL BLUEPRINT** — Excellent for understanding multi-agent trading design, but requires heavy customization for real-time scalping execution

---

### 2.3 Best Multi-Agent Frameworks for Trading (Top 5)

#### 1. CrewAI ⭐ TOP PICK FOR AGENTIC LAYER
**Repository:** [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI)

| Metric | Value |
|--------|-------|
| Stars | **52,800** |
| Monthly Downloads | 5.2M |
| License | MIT |
| Language | Python |

**Key Features:**
- **Standalone framework** (no LangChain dependency)
- Role-based agent teams (Crews) with autonomous collaboration
- Event-driven production workflows (Flows) with precise control
- 100,000+ certified developers
- Simple YAML configuration for agents and tasks
- Supports human-in-the-loop, memory, delegation
- Integrates with any LLM (OpenAI, Anthropic, local models via Ollama)

**Why for Trading:**
- **Fast execution** — 5.76x faster than LangGraph in benchmarks
- Ideal for: signal generation agent, risk management agent, execution agent
- Easy to define trading-specific roles: `TechnicalAnalyst`, `RiskManager`, `ExecutionAgent`
- Can orchestrate a trading "crew" that collaborates on entry/exit decisions

**Verdict:** ✅ **BEST AGENT ORCHESTRATOR** — Fast, flexible, and well-suited for role-based trading teams

---

#### 2. LangGraph
**Repository:** [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)

| Metric | Value |
|--------|-------|
| Stars | **33,900** |
| Monthly Downloads | 34.5M |
| License | MIT |
| Language | Python / JS |

**Key Features:**
- Graph-based stateful agent orchestration
- Durable execution with checkpoints and resume
- Human-in-the-loop workflows
- Used by Klarna, Uber, Cisco, LinkedIn, BlackRock in production
- TradingAgents is built on LangGraph

**Why for Trading:**
- Excellent for complex, stateful decision trees (e.g., market regime → strategy → risk check → execute)
- Time-travel debugging and replay
- More control than CrewAI, but more complex to implement

**Verdict:** ✅ **BEST FOR STATEFUL WORKFLOWS** — Use if you need complex, conditional decision graphs with full state control

---

#### 3. AutoGen (Microsoft) — ⚠️ MAINTENANCE MODE
**Repository:** [microsoft/autogen](https://github.com/microsoft/autogen)

| Metric | Value |
|--------|-------|
| Stars | **58,700** |
| License | MIT |
| Status | **Maintenance Mode** (community-managed) |

**Key Features:**
- Conversational multi-agent patterns
- Event-driven architecture
- AutoGen Studio for no-code GUI

**Warning:** Microsoft has shifted to **Microsoft Agent Framework (MAF)**. AutoGen is no longer actively developed. **Not recommended for new projects.**

**Verdict:** ❌ **NOT RECOMMENDED** — In maintenance mode, migrating to MAF

---

#### 4. MetaGPT
**Repository:** [geekan/MetaGPT](https://github.com/geekan/MetaGPT)

| Metric | Value |
|--------|-------|
| Stars | ~48,000 |
| License | MIT |

**Key Features:**
- Simulates software engineering teams (PM, Architect, Engineer, QA)
- Structured SOPs for multi-agent collaboration

**Verdict:** ❌ **NOT FOR TRADING** — Specialized for software development, not trading workflows

---

#### 5. OpenAgents / OpenClaw
**Repository:** [openagents/openagents](https://github.com/openagents/openagents)

| Metric | Value |
|--------|-------|
| Status | Active, growing |

**Key Features:**
- Native MCP + A2A protocol support
- Persistent agent networks
- Cross-framework interoperability

**Verdict:** ⚠️ **EMERGING** — Interesting for future interoperability, but less mature for trading

---

### 2.4 Agentic Layer Recommendation

| Component | Recommended Tool | Role |
|-----------|------------------|------|
| Agent orchestration | **CrewAI** | Fast, role-based trading agent teams |
| Complex stateful workflows | **LangGraph** (optional) | Market regime detection, conditional execution |
| Trading-specific architecture | **TradingAgents** | Blueprint for analyst/researcher/trader/risk hierarchy |
| Agent management dashboard | **Paperclip** (optional) | Multi-agent fleet management, cost tracking |

**Primary Stack:** `CrewAI` for agent orchestration + `TradingAgents` architecture pattern for trading-specific roles

---

## Layer 3: Trading Layer — Execution Engines

### 3.1 Top Trading Execution Repositories (Top 5)

#### 1. Freqtrade ⭐ TOP PICK FOR TRADING LAYER
**Repository:** [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade)

| Metric | Value |
|--------|-------|
| Stars | **46,500** |
| License | MIT |
| Language | Python 3.11+ |
| Last Update | Active (2026) |

**Key Features:**
- **Free, open-source crypto trading bot**
- **Bybit supported** (both spot and perpetual/futures)
- 113+ exchange connectors (Binance, Bybit, Bitget, Gate.io, Kraken, OKX, Hyperliquid, etc.)
- Dry-run / paper trading mode
- Backtesting with historical data download
- **FreqAI** — machine learning strategy optimization (adaptive prediction modeling)
- Strategy hyperparameter optimization
- Built-in WebUI and Telegram bot
- SQLite persistence, plot dataframes, profit analysis
- Position management, stop-loss, take-profit, trailing stop

**Bybit-Specific:**
- ✅ Bybit spot and futures fully supported
- ✅ API v5 compatible
- Read exchange-specific notes for leverage configuration

**Why for Scalping:**
- **Freqtrade supports 1-minute timeframes** and can be configured for aggressive strategies
- FreqAI can self-train models to adapt to market conditions — critical for scalping
- Built-in risk management (stop-loss, position sizing, max drawdown protection)
- Active community with many strategy examples

**Verdict:** ✅ **BEST EXECUTION ENGINE** — Mature, Bybit-compatible, with ML optimization and comprehensive risk management

---

#### 2. Jesse
**Repository:** [jesse-ai/jesse](https://github.com/jesse-ai/jesse)

| Metric | Value |
|--------|-------|
| Stars | **8,100** |
| Forks | 1,200 |
| License | MIT |
| Language | Python + JavaScript (85% JS) |
| Last Update | Active (2026) |

**Key Features:**
- **Advanced crypto trading framework** for algo traders
- Simple strategy syntax with 300+ indicators
- Smart ordering (market, limit, stop — auto-chooses best)
- Multiple timeframes and symbols simultaneously
- **Monte Carlo analysis** — stress-test strategies with trade-order shuffling
- **Machine learning pipeline** — gather features, train scikit-learn models, deploy in strategies
- Leveraged and short-selling support
- Partial fills, advanced alerts (Telegram, Slack, Discord)
- **JesseGPT** — AI assistant for writing/debugging strategies
- Built-in code editor

**Bybit-Specific:**
- Jesse supports multiple exchanges via CCXT integration
- Can be configured for Bybit spot and futures

**Why for Scalping:**
- Extremely fast backtesting without look-ahead bias
- Monte Carlo analysis guards against overfitting — critical for scalping strategy robustness
- ML pipeline allows predictive scalping models
- Clean, simple Python API for rapid strategy iteration

**Verdict:** ✅ **BEST FOR RESEARCH-HEAVY SCALPING** — Excellent for ML-enhanced scalping strategies with rigorous validation

---

#### 3. Hummingbot
**Repository:** [hummingbot/hummingbot](https://github.com/hummingbot/hummingbot)

| Metric | Value |
|--------|-------|
| Stars | **15,900** |
| License | Apache-2.0 |
| Language | Python + C++ |

**Key Features:**
- **Market making and liquidity mining bot**
- 40+ CEX and DEX connectors
- **Bybit connector** (spot and perpetual) — fee-share partnership with Bybit
- Core strategies: Pure Market Making, Cross-Exchange Market Making, AMM Arbitrage
- Customizable Python scripts for strategies
- Gateway middleware for DEX connectors
- Hummingbot MCP for AI assistant integration

**Bybit-Specific:**
- ✅ Native Bybit spot and perpetual connectors
- ✅ Fee discounts when trading via Hummingbot on Bybit
- Community maintains connector updates

**Why for Scalping:**
- Designed for **high-frequency market making** — very relevant to scalping
- Low-latency order placement and cancellation
- Scripts allow custom scalping logic
- However, primarily focused on market making, not directional scalping

**Verdict:** ✅ **BEST FOR MARKET-MAKING SCALPING** — Ideal if your scalping strategy involves providing liquidity and capturing spreads

---

#### 4. OctoBot
**Repository:** [Drakkar-Software/OctoBot](https://github.com/Drakkar-Software/OctoBot)

| Metric | Value |
|--------|-------|
| Stars | **6,100** |
| Forks | 1,200 |
| License | GPL-3.0 |
| Language | Python |
| Last Update | March 2026 (v2.1.1) |

**Key Features:**
- AI trading bot (ChatGPT / Ollama integration)
- Grid trading, DCA, TradingView strategies
- 15+ exchanges via CCXT (including Binance, Coinbase, MEXC, Hyperliquid)
- **Bybit support:** Note — "Bybit API will soon be available again on OctoBot" (as of March 2026)
- Web UI, Telegram, mobile app
- Backtesting and paper trading
- Low hardware requirements (250MB RAM, 1GB disk)

**Why for Scalping:**
- Grid trading is naturally suited for range-bound scalping
- AI mode can adapt to market conditions
- Very easy to deploy

**Verdict:** ⚠️ **BYBIT STATUS PENDING** — Check Bybit connector status before use; good for grid scalping

---

#### 5. VeighNa (vnpy)
**Repository:** [vnpy/vnpy](https://github.com/vnpy/vnpy)

| Metric | Value |
|--------|-------|
| Stars | ~25,000+ (major Chinese quant project) |
| License | MIT |
| Language | Python |
| Last Update | v4.0 (2026) — AI-powered |

**Key Features:**
- **Comprehensive Chinese quant trading platform**
- v4.0 adds `vnpy.alpha` — multi-factor ML strategy development
- CTA strategy engine, spread trading, option master, algo trading (TWAP, Iceberg, Sniper)
- Multiple data feeds: RQData, TuShare, Wind, iFinD, Polygon
- Risk management module
- Web trader module (REST + WebSocket)
- Databases: SQLite, MySQL, PostgreSQL, QuestDB, MongoDB, TDengine

**Bybit-Specific:**
- Not natively focused on Bybit; more China-centric (CTP, XTP, etc.)
- Can potentially connect via CCXT or custom gateway

**Verdict:** ⚠️ **CHINA-FOCUSED** — Excellent for learning quant architecture, but Bybit integration requires extra work

---

### 3.2 Additional Scalping-Specific Repositories

| Repository | Stars | Description | Bybit |
|------------|-------|-------------|-------|
| [nawwa_scalper_terminal](https://github.com/CryptoNawwa/nawwa_scalper_terminal) | ~100+ | TUI scalping tool for Bybit & Binance | ✅ Yes |
| [crypto_hedge_scalping_bot](https://github.com/nikita-doronin/crypto_hedge_scalping_bot) | ~50+ | Binance hedge scalping with backtest | ❌ Binance only |
| [binance-scalping](https://github.com/marahman30104/binance-scalping) | ~50+ | Binance futures arbitrage scalping | ❌ Binance only |
| [crypto-scalping-bot](https://github.com/crypto-scalping-bot) | ~100+ | GPT-5 powered multi-exchange scalping | ✅ Yes |

---

### 3.3 Trading Layer Recommendation

| Component | Recommended Tool | Role |
|-----------|------------------|------|
| Primary execution engine | **Freqtrade** | Live trading, backtesting, FreqAI ML |
| Strategy research & validation | **Jesse** | Monte Carlo, ML pipeline, rapid prototyping |
| Market-making scalping | **Hummingbot** | Spread capture, liquidity provision |
| Grid/DCA scalping | **OctoBot** | Automated grid strategies |
| Risk management | **Freqtrade built-in** | Stop-loss, position sizing, drawdown limits |

**Primary Stack:** `Freqtrade` (execution + ML) + `Jesse` (research + validation) — both can use CCXT for Bybit connectivity

---

## Cross-Layer Integration: Repositories Spanning Multiple Layers

### 1. DARWIN ⭐ MOST RELEVANT CROSS-LAYER PROJECT
**Repository:** [Wxiaobai123/DARWIN](https://github.com/Wxiaobai123/DARWIN)

| Metric | Value |
|--------|-------|
| Components | OKX Agent Trade Kit + Paperclip AI |
| License | Not specified |
| Language | Chinese / English docs |

**Architecture:**
- **Data Layer:** OKX Agent Trade Kit (ATK) — market data, account info, execution, algo bots
- **Agentic Layer:** Paperclip AI — multi-agent orchestration with org hierarchy, heartbeat, budget control
- **Trading Layer:** OKX exchange execution (Spot Grid, Contract Grid, Martingale, Funding Arb, TWAP, Iceberg)
- **Risk Management:** User-defined risk appetite + coin whitelist; AI handles market identification, strategy governance, execution coordination

**Why Relevant:**
- This is the **closest existing project** to your desired 3-layer architecture
- Proves that **Paperclip + Exchange-specific trading kit + multi-agent governance** is a viable pattern
- However, it's built for **OKX**, not Bybit

**Verdict:** ✅ **ARCHITECTURAL REFERENCE** — Study this project as a blueprint for your Bybit version

---

### 2. AlpacaTradingAgent
**Repository:** [huygiatrng/AlpacaTradingAgent](https://github.com/huygiatrng/AlpacaTradingAgent)

**Architecture:**
- Extends **TradingAgents** (Tauric Research) framework
- Adds real-time **Alpaca** integration for live trading
- Crypto support, automated trading, web interface
- Inspired by TradingAgents but extended with execution

**Verdict:** ⚠️ **INSPIRATION** — Shows how to extend TradingAgents with real broker execution, but Alpaca-focused, not Bybit

---

### 3. Signalcraft Trading Assistant
**Repository:** [AI-crypto-trading-assistant/signalcraft-trading-assistant](https://github.com/AI-crypto-trading-assistant/signalcraft-trading-assistant)

**Architecture:**
- **Data Layer:** DeepSeek V4 with 1M context window (reads price history, news, on-chain data)
- **Agentic Layer:** AI reasoning engine with observer mode
- **Trading Layer:** Execution via CCXT (Binance, Bybit, Hyperliquid, Coinbase, OKX, Kraken)
- **Safety:** Position sizing caps, daily loss limits, kill switch, manual confirmation

**Verdict:** ⚠️ **SIGNAL-SUPPORT TOOL** — Good for AI-powered market analysis, but observer-mode by default, not a full execution framework

---

### 4. Paperclip Zero-Human Trading Firm
**Repository:** [jackson-video-resources/paperclip-zero-human-trading-firm](https://github.com/jackson-video-resources/paperclip-zero-human-trading-firm)

**Architecture:**
- **Agentic Layer:** Paperclip + Claude Code
- **Data Layer:** TradingView MCP (for historical data)
- **Trading Layer:** BitGet (via TradingView webhook)
- 6 agents: CEO, Research, Backtest, Risk, Execution, Cost Optimizer

**Verdict:** ⚠️ **DEMONSTRATION** — Shows how to set up a Paperclip-based trading firm, but uses TradingView/BitGet, not Bybit API

---

### 5. OpenAlice
**Repository:** Referenced in [CiferaTeam/awesome-agents-team](https://github.com/CiferaTeam/awesome-agents-team)

**Architecture:**
- Locally runnable AI trading agent
- Covers equities, crypto, commodities, forex, macro
- Trading-as-Git and guard pipeline
- Self-hosted, AGPL-3.0

**Verdict:** ⚠️ **EMERGING** — Interesting for local-first AI trading, but less documented

---

## Final Recommendation: Optimal 3-Layer Bybit Scalping System

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      AGENTIC LAYER (Layer 2)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Signal Gen  │  │   Consensus  │  │    Risk / Execution      │  │
│  │   Agent      │  │   Agent      │  │      Agent               │  │
│  │ (CrewAI)     │  │ (CrewAI)     │  │   (CrewAI)               │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│         │                │                        │                 │
│         ▼                ▼                        ▼                 │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              TradingAgents Architecture Pattern               │  │
│  │  (Analyst → Researcher → Trader → Risk → Portfolio Manager)   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Paperclip (Optional) — Agent Company Orchestration, Budgets  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    TRADING LAYER (Layer 3)                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Freqtrade (Primary) — Live Execution, FreqAI ML, Risk Mgmt │  │
│  │  OR / OR Combined with:                                     │  │
│  │  Jesse (Research/Backtest) — Monte Carlo, ML Pipeline       │  │
│  │  Hummingbot (Market-Making) — Spread Capture (optional) │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│                              ▼                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Bybit API v5 (CCXT Unified) — Order Entry, Position Mgmt   │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA LAYER (Layer 1)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  CCXT Pro    │  │  Cryptofeed  │  │      VectorBT            │  │
│  │  (REST/WS)   │  │  (WebSocket) │  │   (Backtesting)          │  │
│  │  OHLCV       │  │  L2 Books    │  │   Strategy Research      │  │
│  │  Trades      │  │  Tick Data   │  │   Parameter Optimization │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  pandas-ta   │  │  Redis/      │  │  OpenBB (Optional)       │  │
│  │  (Indicators)│  │  PostgreSQL  │  │  Macro/Sentiment Data    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Recommended Stack

| Layer | Primary Tool | Secondary Tool | Purpose |
|-------|-------------|----------------|---------|
| **Data** | **CCXT** | Cryptofeed | Unified exchange API + real-time WebSocket feeds |
| **Data** | **VectorBT** | — | Backtesting, parameter optimization, strategy validation |
| **Data** | **pandas-ta** | TA-Lib | Technical indicator generation |
| **Data** | **Redis** | PostgreSQL/QuestDB | Real-time data caching + time-series storage |
| **Agentic** | **CrewAI** | LangGraph (optional) | Role-based trading agent teams, consensus building |
| **Agentic** | **TradingAgents** (pattern) | — | Blueprint for analyst→researcher→trader→risk flow |
| **Agentic** | **Paperclip** (optional) | — | Multi-agent fleet management, cost tracking |
| **Trading** | **Freqtrade** | Jesse | Live execution, FreqAI ML, risk management, paper trading |
| **Trading** | **Hummingbot** (optional) | — | Market-making scalping strategies |

### Implementation Priority

1. **Phase 1 (Data):** Set up CCXT + Cryptofeed for Bybit real-time data. Build VectorBT backtesting environment.
2. **Phase 2 (Trading):** Configure Freqtrade with Bybit API v5. Develop basic scalping strategies with stop-loss and position sizing.
3. **Phase 3 (Agentic):** Implement CrewAI agents for signal generation, consensus, and risk gating. Use TradingAgents architecture as reference.
4. **Phase 4 (Integration):** Connect agent decisions to Freqtrade execution. Add Paperclip for multi-agent orchestration if scaling beyond 3-5 agents.
5. **Phase 5 (Optimization):** Integrate FreqAI for adaptive ML models. Add Monte Carlo validation via Jesse.

### Key Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Scalping latency | Use Cryptofeed WebSocket + direct CCXT Pro for sub-second data |
| Agent deliberation too slow | Use lightweight CrewAI agents with fast models (GPT-4o-mini) for quick decisions |
| Overfitting strategies | VectorBT walk-forward + Jesse Monte Carlo validation |
| API rate limits | CCXT built-in rate limiter + rolling window algorithm |
| Runaway AI costs | Paperclip budget controls + CrewAI cost monitoring |
| Exchange risk | Start with Freqtrade dry-run mode; paper trade for weeks |

---

## Repository Quick Reference Table

| Repository | Layer | Stars | Bybit | License | Best For |
|------------|-------|-------|-------|---------|----------|
| [ccxt/ccxt](https://github.com/ccxt/ccxt) | Data | 43k | ✅ | MIT | Unified exchange API |
| [cryptofeed](https://github.com/bmoscon/cryptofeed) | Data | 3k | ✅ | MIT | Real-time WebSocket feeds |
| [vectorbt](https://github.com/polakowo/vectorbt) | Data | 8k | N/A | Apache-2.0 | Backtesting at scale |
| [freqtrade](https://github.com/freqtrade/freqtrade) | Trading | 46.5k | ✅ | MIT | Live execution + FreqAI |
| [jesse-ai/jesse](https://github.com/jesse-ai/jesse) | Trading | 8.1k | ✅ | MIT | ML pipeline + Monte Carlo |
| [hummingbot](https://github.com/hummingbot/hummingbot) | Trading | 15.9k | ✅ | Apache-2.0 | Market-making scalping |
| [OctoBot](https://github.com/Drakkar-Software/OctoBot) | Trading | 6.1k | ⚠️ | GPL-3.0 | Grid/DCA scalping |
| [vnpy](https://github.com/vnpy/vnpy) | Trading | 25k+ | ❌ | MIT | Chinese quant platform |
| [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | Agentic | 52.8k | N/A | MIT | Agent orchestration |
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | Agentic | 33.9k | N/A | MIT | Stateful workflows |
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | Agentic | — | ❌ | Apache-2.0 | Trading architecture pattern |
| [paperclipai/paperclip](https://github.com/paperclipai/paperclip) | Agentic | 38k | N/A | MIT | Agent fleet management |
| [DARWIN](https://github.com/Wxiaobai123/DARWIN) | Cross | — | ❌ | — | 3-layer blueprint (OKX) |
| [Signalcraft](https://github.com/AI-crypto-trading-assistant/signalcraft-trading-assistant) | Cross | — | ✅ | MIT | AI assistant + execution |
| [OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB) | Data | 20k+ | ❌ | AGPL-3.0 | Macro/fundamental data |

---

*Disclaimer: This research is for educational and informational purposes only. Trading cryptocurrencies carries significant risk. Always test strategies in paper trading mode before deploying real capital. The repositories listed are open-source projects with no warranty; review all code before use.*
