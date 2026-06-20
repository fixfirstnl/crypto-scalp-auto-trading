# Crypto Scalp Auto Trading System

**3-layer automated crypto scalping system** built on Bybit Testnet, replicating the world's best ICT/SMC scalping strategy.

---

## Architecture

```
Layer 2 (Agentic)  →  CrewAI: BiasAgent → SignalAgent → RiskAgent → ExecAgent
        ↓
Layer 3 (Trading)  →  ExecutionEngine → OrderManager → PositionTracker → RiskManager
        ↓
Layer 1 (Data)     →  CCXT Pro → Bybit WebSocket → DataCache → IndicatorEngine
```

---

## Quick Start (Stap-voor-Stap)

### Stap 1: Python Installeren

1. Ga naar **https://www.python.org/downloads/release/python-3119/**
2. Download **Windows installer (64-bit)**
3. **BELANGRIJK**: Vink **"Add Python to PATH"** aan tijdens installatie!
4. Herstart je computer

### Stap 2: Setup Draaien

```bash
# Open CMD in de project folder
cd "C:\Users\Administrator\Documents\Kimi\Workspaces\Crypto scalp auto trading"

# Run setup
setup.bat
```

Dit doet automatisch:
- pip upgraden
- Virtual environment aanmaken (`venv/`)
- Alle dependencies installeren

### Stap 3: Bybit Testnet API Keys

1. Ga naar **https://testnet.bybit.com**
2. Maak een account aan
3. Ga naar **API Management**
4. Maak een API key aan met **Read** en **Trade** rechten
5. Kopieer de **API Key** en **API Secret**

### Stap 4: Configuratie

```bash
# Kopieer environment template
copy .env.example .env
```

Bewerk `.env` en vul je API keys in:

```env
BYBIT_API_KEY=je_api_key_hier
BYBIT_API_SECRET=je_api_secret_hier
TELEGRAM_BOT_TOKEN=optioneel
TELEGRAM_CHAT_ID=optioneel
OPENAI_API_KEY=optioneel  # voor CrewAI agents
```

### Stap 5: Starten

```bash
# Activeer venv
venv\Scripts\activate

# Start het systeem
python main.py
```

---

## Features

| Feature | Beschrijving |
|---------|-------------|
| **ICT/SMC Strategy** | Liquidity sweep → Order Block + FVG → EMA cross → Volume confirm |
| **Multi-Agent AI** | 4 CrewAI agents: Bias, Signal, Risk, Execution |
| **Risk Management** | 0.5% risk/trade, 3% daily limit, kill switches |
| **Partial Profits** | 33% @ 1R, 33% @ 2R, 34% runner met trailing stop |
| **SQLite Database** | Zero-config, geen Docker/PostgreSQL nodig |
| **Telegram Alerts** | Real-time trade alerts, PnL reports, remote commands |

---

## Project Structure

```
crypto_scalp_auto_trading/
├── config/              # YAML configuratie
├── src/
│   ├── layer1_data/     # CCXT Pro, WebSocket, indicators, cache
│   ├── layer2_agents/   # CrewAI multi-agent pipeline
│   ├── layer3_trading/  # Order execution, risk management
│   ├── strategy/        # ICT/SMC: BOS/CHoCH, OB, FVG, liquidity
│   └── utils/           # Logger, Telegram, news filter, database
├── tests/               # Unit tests
├── data/                # SQLite database + historische data
├── logs/                # Log files
├── main.py              # Entry point
├── setup.bat            # Windows setup script
├── requirements.txt     # Dependencies
└── docker-compose.yml   # Optioneel: Redis + PostgreSQL
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Data** | CCXT Pro, pandas, pandas-ta, numpy |
| **Agents** | CrewAI (rule-based tools, optional LLM) |
| **Trading** | CCXT Bybit v5, custom execution engine |
| **Storage** | SQLite (zero-config), optional Redis/PostgreSQL |
| **Monitoring** | python-telegram-bot |

---

## Risk Parameters (Default)

| Parameter | Waarde |
|-----------|--------|
| Risk per trade | 0.5% |
| Max open positions | 5 |
| Daily loss limit | 3% (hard halt) |
| Max drawdown | 5% |
| Consecutive losses | 4 = pause |
| Kill zones | London (2-5 AM EST) + NY (7-10 AM EST) |

---

## Disclaimer

⚠️ **Dit systeem is voor educatieve en ontwikkelingsdoeleinden.**

- Start ALTIJD op **Bybit Testnet**
- Backtest grondig voordat je live gaat
- Gebruik nooit meer geld dan je kunt veroorloven te verliezen
- Crypto trading is zeer risicovol

---

*Built with deep research on the world's best crypto scalping strategies.*
