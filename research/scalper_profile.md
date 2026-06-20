# Crypto Scalper Profile: Deep Research Report

**Research Date:** 2026-06-20
**Researcher:** Scalper_Analyst (Orchestrator Sub-agent)
**Methodology:** 45+ web searches across 6 dimensions using kimi_search_v2 and kimi_fetch_v2; cross-referenced for consistency.

---

## Executive Summary

After conducting extensive multi-dimensional research, **no single individual is universally verified as the "best crypto scalper in the world" with independently audited PnL.** The crypto scalping landscape is fragmented between anonymous prop-firm traders, copy-trading leaderboard leaders, and influential educators whose methodologies are widely adopted but whose personal trading records are not publicly verifiable.

However, a clear consensus emerges around the **ICT/Smart Money Concepts (SMC) framework** as the dominant methodology adopted by the most consistent crypto scalpers. This report documents the complete composite strategy derived from cross-referencing sources including ICT methodology guides, prop-firm scalper research, copy-trading platform analytics, orderflow analysis tutorials, and risk-management literature specific to crypto scalping.

**Key Finding:** The most automatable and widely validated scalping framework combines: (1) Multi-timeframe ICT structure analysis for bias, (2) EMA 9/21 + VWAP + RSI for execution timing, (3) Orderflow/CVD confirmation for conviction, (4) Strict 0.25-1% risk per trade with 3-5% daily loss limits, (5) BTC/ETH perp focus during London/NY kill zones, and (6) Tiered exit systems with partial profit-taking.

---

## 1. Identity & Track Record

### 1.1 The "Best" Problem — Verified PnL Is Scarce

Crypto scalping lacks the equivalent of audited hedge-fund returns or publicly disclosed trader tax records. The highest-quality verified performance data exists on:

- **OKX Orbit Social Trading:** Traders who opt into performance sharing display verified PnL pulled directly from OKX's backend. The platform flags high win-rate / tiny PnL traders as suspect (scalping micro-positions) and recommends looking for consistent returns over 90+ days with reasonable win rates (50-65%).[^1]
- **Copy Trading Leaderboards (Bybit, Bitget, Binance):** These show Master Trader ROI, but follower outcomes diverge due to slippage, timing, and the 30% profit share taken by Pro Masters. The leaderboard measures the Master's returns, not the follower's.[^2]
- **Prop Firm Leaderboards:** Firms like SizeProp, Goat Funded Trader, and HyroTrader publish aggregate stats but individual scalper names remain anonymous for privacy. SizeProp notes that BTC and ETH dominate funded scalper P&L.[^3]
- **Myfxbook:** Some forex/cross-asset scalper EAs are verified here (e.g., Elite Scalper Bot +4341% gain, 24.65% drawdown), but these are MT5/MT4 bots on XAUUSD, not live crypto accounts.[^4]

### 1.2 Influential Figures Investigated

| Name | Role | Verified PnL? | Contribution to Scalping |
|------|------|---------------|------------------------|
| **ICT (Michael J. Huddleston)** | Educator / Methodologist | **No** — No independently verified trading account is public. | Created the Smart Money Concepts framework (Order Blocks, FVG, Liquidity Sweeps, Kill Zones) that dominates crypto scalping discourse.[^5] |
| **Crypto Face** | YouTuber / Content Creator | Unverified — social media claims only. | Known for Bitcoin futures scalping content; strategy focuses on VWAP and momentum, but lacks third-party audit.[^6] |
| **Altcoin Psycho** | Twitter/X Influencer | Unverified. | Created "PsychoBot" — a momentum breakout bot using 1D/3D trend confirmation. Claims live since 2019, but no audited Myfxbook/crypto exchange verification.[^7] |
| **The Trading Goat** | Social Media Trader | **No verified PnL found.** | Name appears in copy-trading contexts but no confirmed leaderboard ranking or verified track record. |
| **Anonymous Prop Scalpers** | Funded traders on SizeProp, Goat Funded Trader, HyroTrader | **Verified within firm systems** but not public. | Represent the most disciplined scalpers due to prop firm drawdown rules (2-5% daily, 5-10% max). Their aggregate approach is documented in firm blogs.[^3] |

### 1.3 Conclusion on Identity

The "best" crypto scalper is not a named celebrity but a **composite archetype:** an anonymous prop-firm funded trader using ICT/SMC concepts with strict risk parameters, trading BTC/ETH perps during kill zones, with verified consistency over 90+ days on exchange-verified backends. The methodology is more important than the personality.

---

## 2. Strategy Overview

The dominant crypto scalping framework is a **hybrid ICT-Indicator-Orderflow system**:

| Component | Purpose | Timeframe |
|-----------|---------|-----------|
| Higher-Timeframe Bias | Determine bullish/bearish market structure | 1H / 4H / Daily |
| Kill Zone Timing | Trade only during high-liquidity institutional windows | London (2-5 AM EST) / NY (7-10 AM EST) |
| Liquidity Sweep | Identify where stops are being hunted | 15m / 1H |
| Entry Zone | Order Block + Fair Value Gap overlap | 5m / 15m |
| Execution Trigger | Lower-timeframe CHoCH or EMA crossover | 1m / 5m |
| Confirmation | Volume spike, RSI, CVD alignment | 1m / 5m |

**Core Philosophy:** "Trade with the HTF bias, after liquidity is swept, into institutional discount/premium zones, confirmed by orderflow."

---

## 3. Entry Rules (Exact Criteria)

### 3.1 Timeframe Hierarchy

- **Bias Timeframe:** 1H or 4H — Mark market structure (BOS/CHoCH), identify premium/discount zones, and locate major liquidity pools.[^5]
- **Setup Timeframe:** 15m — Mark Order Blocks and Fair Value Gaps. Identify Asian session range for liquidity sweep targets.[^5]
- **Entry Timeframe:** 5m or 1m — Execute after confirmation.

### 3.2 Indicators & Settings

| Indicator | Settings | Role in Scalping |
|-----------|----------|------------------|
| **EMA 9 & 21** | Fast=9, Slow=21 | Crossover signals on 1m/5m; 9 EMA acts as dynamic support/resistance in trends.[^8] |
| **VWAP** | Session VWAP | Intraday fair value anchor. Price above VWAP = bullish bias; below = bearish. Pullbacks to VWAP in trends are high-probability entries.[^8] |
| **RSI (14)** | Standard | Overbought (>70) / Oversold (<30) for divergence. Confirms pullback exhaustion when aligned with structure.[^8] |
| **Volume Profile** | Session or Fixed Range | Identifies Point of Control (POC) and Value Area High/Low (VAH/VAL). Key for entry confluence.[^9] |
| **CVD / Delta** | Cumulative Volume Delta | Confirms whether price moves are supported by aggressive buying/selling. Divergence warns of exhaustion.[^10] |
| **ATR (14)** | Standard | Sets dynamic stop-loss and take-profit distances based on current volatility.[^8] |

### 3.3 Entry Model (ICT-Based Hybrid)

**Step 1 — Bias Confirmation (1H/4H):**
- Identify market structure: higher highs/higher lows = bullish; lower lows/lower highs = bearish.
- Look for a Change of Character (CHoCH) on the HTF to signal potential reversal, or Break of Structure (BOS) for continuation.[^5]
- Mark the Asian session high/low as liquidity targets.[^5]

**Step 2 — Liquidity Sweep (15m):**
- Wait for price to sweep the Asian session high/low or an equal high/low cluster.
- The sweep should be a sharp move that takes out obvious stops, then reverses.[^5]

**Step 3 — Entry Zone Identification (5m):**
- Mark a valid Order Block (last opposing candle before the impulsive move that caused BOS/CHoCH).[^5]
- Check for a Fair Value Gap (FVG) — three-candle formation where wicks of candle 1 and 3 do not overlap. The highest-probability entries occur where Order Block and FVG overlap.[^5]

**Step 4 — Lower-Timeframe Confirmation (1m/5m):**
- Price retraces into the Order Block/FVG zone.
- A lower-timeframe CHoCH occurs in the direction of the HTF bias.[^5]
- **OR** for EMA-based execution: 9 EMA crosses 21 EMA with price above/below VWAP in the direction of HTF bias.[^8]
- **AND** RSI is not at extreme (e.g., for longs, RSI > 40 to avoid catching falling knives).[^8]
- **AND** Volume spike confirms the move (volume > 1.5x average).[^8]

**Step 5 — Orderflow Confirmation (optional, discretionary):**
- CVD turns in the direction of the trade (e.g., for longs, CVD starts rising as price enters the zone).[^10]
- No major absorption at the entry level (footprint shows no massive selling into the long).[^9]

**Step 6 — Entry Execution:**
- Limit order at the Order Block body / FVG 50% fill level.
- If momentum is strong, market order on LTF confirmation candle close.
- Stop-loss placed below the Order Block low (for longs) or above the Order Block high (for shorts).[^5]

---

## 4. Exit Rules

### 4.1 Profit Targets

| Target Type | Method | Typical R:R |
|-------------|--------|-------------|
| **Fixed R:R** | Target next opposing liquidity pool (e.g., if long after SSL sweep, target BSL). Minimum 1:2, ideal 1:3.[^5] | 1:2 to 1:3 |
| **VWAP Target** | If entering away from VWAP, target VWAP as first scale-out.[^8] | Varies |
| **Technical Level** | Prior swing high/low, POC, or round number.[^8] | Varies |
| **ATR-Based** | Target = Entry + (2x ATR) for longs.[^8] | ~1:2 to 1:3 |

### 4.2 Partial Profit Taking (Scale-Out)

The mathematically optimal approach for scalping is tiered exits:[^11]

- **Tier 1 (25-33%):** Close at 1R profit (breakeven on the trade if stop is hit on remainder).
- **Tier 2 (25-33%):** Close at 2R profit.
- **Tier 3 (Remainder):** Trail with a stop or let run to 3R+ with a trailing stop below recent swing low / above swing high.

This reduces regret, locks in gains, and allows participation in runners.[^11]

### 4.3 Stop Loss Placement

- **Structure-based:** Below the Order Block low (for longs) or above the Order Block high (for shorts). This is the ICT standard.[^5]
- **ATR-based:** Stop = Entry - (1.5x ATR) for longs. Adjusts to volatility.[^8]
- **Fixed %:** 0.1-0.3% from entry on crypto perps (very tight).[^12]
- **Time-based:** If trade has not moved in 5-10 minutes, exit — the edge was in the immediate reaction.[^13]

### 4.4 Trailing Stop

- Move stop to breakeven once price reaches 1R.[^5]
- Trail behind the 9 EMA on the 1m chart (for aggressive trailing) or below the most recent 5m swing low (for structural trailing).[^11]
- Trailing distance: 5-10% of the current move for crypto, or 1x ATR.[^11]

### 4.5 Time-Based Exits

- **Max hold time:** 5-20 minutes for pure scalps; up to 60 minutes for ICT-based setups targeting opposing liquidity.[^13]
- **Session end:** Close all positions before the end of the NY session (4 PM EST) if they have not hit targets, to avoid overnight/Asian session gap risk.[^13]
- **Kill zone expiry:** If the trade was entered during the London/NY kill zone and has not triggered by the end of that window, cancel the order.[^5]

---

## 5. Risk Management

### 5.1 Position Sizing

| Rule | Setting | Rationale |
|--------|---------|-----------|
| **Risk Per Trade** | 0.25% - 1.0% of account | Prop firm scalpers often use 0.2-0.3% to survive daily loss limits. Retail scalpers can use 0.5-1%.[^12][^14] |
| **Max Open Positions** | 3-5 simultaneously | Prevents correlation stacking and overexposure.[^12] |
| **Daily Risk Cap** | 2-3% of account | Hard stop — no more trading for the day if hit. Prevents revenge trading.[^12][^14] |
| **Weekly Risk Cap** | 5-10% of account | Macro circuit breaker.[^12] |
| **Correlation Limit** | Max 2 pairs per base currency | BTC long + ETH long + SOL long = correlated USD risk. Cap total exposure.[^15] |

### 5.2 Stop Loss Discipline

- Place stop simultaneously with entry order. Never add to losing positions.[^14]
- If a trade hits stop, mandatory 5-minute cooldown before next entry.[^13]
- Never move stop further away from entry.[^13]

### 5.3 Daily Loss Limit (Hard Cutoff)

Every elite scalper operates with a strict, non-negotiable daily loss limit, typically **3% to 5% of capital**. Hitting this limit means walking away for the day to prevent emotional revenge trading.[^14]

### 5.4 Portfolio Heat Management

- **Drawdown kill switch:** If account drawdown exceeds 5-10% from peak, halt all trading and review.[^15]
- **Consecutive loss guard:** Pause after 4-6 consecutive losses.[^15]
- **Volatility-based sizing:** Reduce position size by 50% when ATR is >2x the 20-day average.[^15]

### 5.5 Prop-Firm Adaptation

Prop firms impose strict rules that effectively create the "best" scalper risk framework:
- Daily loss limit: 2-5% (e.g., $100 on a $5K account)
- Max drawdown: 5-10% from peak
- This forces scalpers to use 0.2-0.5% per trade and trade only A+ setups.[^3]

---

## 6. Pair Selection & Market Conditions

### 6.1 Recommended Pairs (Liquidity Priority)

| Pair | 24h Volume | Spread | Suitability |
|------|------------|--------|-------------|
| **BTC/USDT Perp** | $50B+ | Tightest (<0.01%) | Default. Deepest orderbook, lowest slippage. Best for scalping.[^16] |
| **ETH/USDT Perp** | ~$20B | Tight (0.01-0.03%) | Slightly more volatile than BTC. Good for breakout/momentum scalps.[^16] |
| **SOL/USDT Perp** | ~$5B | Moderate (0.05-0.1%) | Higher volatility, wider spread. For experienced scalpers only.[^16] |
| **XRP, BNB, DOGE** | Variable | Wider | Momentum/news-driven. Execution quality deteriorates during fast moves.[^16] |

**Rule:** Avoid low-cap perps under $500M open interest. Slippage on a 0.5R scalp can flip the trade negative before fill.[^3]

### 6.2 Session Preferences (Kill Zones)

| Session | Time (EST) | Activity | Strategy |
|---------|------------|----------|----------|
| **Asian** | 8:00 PM - 12:00 AM | Range identification, low volatility | Mark Asian high/low; do NOT trade.[^5] |
| **London Open** | 2:00 AM - 5:00 AM | First major move, high volume | Trade breakouts of Asian range.[^5][^17] |
| **NY Open** | 7:00 AM - 10:00 AM | Strongest directional moves, highest liquidity | Primary scalping window.[^5][^17] |
| **London Close** | 10:00 AM - 12:00 PM | Potential reversals | Caution — can be choppy.[^5] |
| **Midday** | 11:00 AM - 1:30 PM | Low volume, wider spreads | Avoid.[^13] |

### 6.3 Volatility Filter

- **Trade when ATR is between 1x and 2x the 20-day average.** Below 1x = dead market, chop. Above 2x = erratic, slippage risk.[^15]
- **Spread guard:** Ignore trades if spread > 2x the average for that pair.[^15]
- **Slippage guard:** Ignore if expected slippage > 1.5x average.[^15]

### 6.4 Trend vs Range

- **Trending market:** Use pullback-to-EMA or pullback-to-VWAP entries. Loosen stops slightly.[^17]
- **Range-bound market:** Use VWAP mean reversion or support/resistance scalping. Tighten stops.[^17]
- **Transition/transition:** Wait for breakout-reclaim or Opening Range Breakout.[^13]

### 6.5 News/Event Avoidance

- **Mandatory pause:** 15-30 minutes before and after high-impact news:[^18]
  - NFP (Non-Farm Payrolls) — first Friday of each month
  - CPI / PPI releases
  - FOMC meetings / interest rate decisions
  - Major exchange events (ETF approvals, regulatory announcements)
- **News filter:** Automated bots should pull from Forex Factory or economic calendar APIs and disable entries ±15 minutes around red-folder events.[^18]
- **Weekend gap risk:** Close all positions before Friday close (or before Sunday open) to avoid gap risk on thin liquidity.[^18]

---

## 7. Automation Mapping

### 7.1 Fully Automatable Components

| Component | Automation Method | Difficulty |
|-----------|-------------------|------------|
| **Data ingestion** | Exchange API (REST/WebSocket) + CCXT | Low |
| **HTF bias detection** | Algorithmic BOS/CHoCH detection on 1H/4H | Medium |
| **EMA crossovers** | Pine Script / Python TA-Lib | Low |
| **RSI filtering** | Pine Script / Python | Low |
| **VWAP calculation** | Built-in exchange indicators or Python | Low |
| **ATR-based stops/targets** | Python | Low |
| **Position sizing** | Fixed % or Kelly variant | Low |
| **Bracket orders** | OCO (One-Cancels-Other) via exchange API | Low |
| **Partial profit taking** | Multiple TP orders or bot-logic | Medium |
| **Trailing stop** | Exchange trailing stop or bot-managed | Low |
| **Daily loss limit** | Bot circuit breaker | Low |
| **News filter** | Economic calendar API (e.g., ForexFactory) | Low |
| **Spread/slippage guard** | Pre-trade checks | Low |
| **Time-based exits** | Timer logic | Low |
| **Session filters** | Kill zone time windows | Low |

### 7.2 Partially Automatable (Requires Human Oversight)

| Component | Challenge | Mitigation |
|-----------|-----------|------------|
| **Order Block identification** | Requires contextual judgment; not all opposing candles are valid OBs. | Use algorithmic swing detection + displacement filtering; backtest OB rules.[^5] |
| **FVG quality assessment** | Weak FVGs fail often; only "exceptional" FVGs (with displacement + liquidity sweep) are reliable. | Code strength filters: require minimum body size, alignment with structure, and volume spike.[^5] |
| **Liquidity sweep context** | Was the sweep genuine or a continuation pattern? | Use volume confirmation and CVD direction.[^10] |
| **Market regime detection** | Trend vs range vs breakout transition is hard to classify in real-time. | Use ADX + Bollinger Band width + EMA slope regime classifier.[^19] |

### 7.3 Human-Only (Difficult to Automate)

| Component | Why Hard |
|-----------|----------|
| **Discretionary macro context** | Geopolitical events, regulatory shifts, exchange hacks — qualitative judgment. |
| **"Feel" for chop vs imminent move** | Experience-based pattern recognition in low-volatility pre-breakout periods. |
| **Correlation/sector rotation** | Real-time assessment of whether BTC/ETH/SOL are moving in tandem or diverging. |
| **Adaptation to new exchange behavior** | API changes, fee changes, liquidity shifts require human review. |

### 7.4 Recommended Technology Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| **Exchange Connectivity** | CCXT (Python) or exchange-native SDK (Binance, Bybit, OKX) | CCXT supports 100+ exchanges.[^20] |
| **Data Feed** | WebSocket for real-time; REST for historical | WebSocket reduces latency.[^20] |
| **Strategy Engine** | Python (pandas, numpy, TA-Lib) OR TradingView Pine Script + Webhooks | Pine Script is easier for indicator-based rules; Python is more flexible.[^20] |
| **Execution** | Async Python (aiohttp) or TradingView broker integration | Async is critical for multi-pair scalping.[^20] |
| **Risk Management** | Python middleware or 3Commas / Cryptohopper | Build-in daily loss, max positions, correlation caps.[^20] |
| **Hosting** | VPS (Amazon AWS, DigitalOcean, OX VPS) | Low latency (<20ms) to exchange.[^20] |
| **Monitoring** | Telegram/Discord bot alerts + logging to SQLite/PostgreSQL | Track PnL, win rate, slippage, errors. |
| **Backtesting** | TradingView Strategy Tester or Backtrader / QuantConnect | Validate before live deployment.[^20] |

### 7.5 Automation Architecture Blueprint

```
[Market Data] → [Regime Detector] → [Bias Engine] → [Signal Generator] → [Risk Check] → [Execution] → [Monitor/Log]

Market Data: Exchange WS → OHLCV + Orderbook + Funding Rate
Regime Detector: ADX + BB Width + ATR → Trend / Range / Volatile
Bias Engine: 1H/4H BOS/CHoCH + EMA slope → Bullish / Bearish / Neutral
Signal Generator: 5m OB/FVG scan + 1m EMA cross + RSI + Volume spike → Long/Short/None
Risk Check: Daily loss? Max positions? Correlation? Spread? News? → Pass/Fail
Execution: Limit order entry + OCO bracket (SL + TP1 + TP2 + Trailing) → Exchange API
Monitor/Log: PnL tracking + slippage analysis + error alerting → Dashboard
```

### 7.6 The "Art" vs "Science" of Automation

- **Science (80%):** Entry signals, position sizing, stop/targets, session filters, news guards, and daily loss limits can be fully coded. This is the mechanical edge.
- **Art (20%):** Determining when the market is "choppy" vs "primed," whether a liquidity sweep is genuine, and when to stay flat despite a signal appearing. This requires human oversight or advanced ML models trained on regime data.
- **Recommendation:** Automate the science completely. Have a human (or a secondary ML filter) review the "art" components for the first 3-6 months. After sufficient data, attempt to codify the art into rules.

---

## 8. Sources & Citations

[^1]: OKX Orbit Social Trading — verified trader metrics and red flags. Source: https://supa.is/article/how-to-use-okx-orbit-social-trading-find-verified-traders-2026 (2026-03-08)

[^2]: Bybit Copy Trading 2026 review — leaderboard limitations, slippage, profit share. Source: https://coinbureau.com/review/bybit-copy-trading-review (2026-03-11)

[^3]: SizeProp scalping guide — best pairs, leverage, funded scalper stats. Source: https://www.sizeprop.com/blog/scalping-crypto-prop-trading (2026-05-12)

[^4]: Elite Scalper Bot MT5 — Myfxbook verified +4341% gain. Source: https://forexcrackedvip.com/product/elite-scalper-bot-mt5/ (2026-01-16)

[^5]: ICT Trading Strategy Complete Guide — BOS, CHoCH, Order Blocks, FVG, Kill Zones, entry model. Source: https://chartinglens.com/blog/ict-trading-strategy-guide (2026-05-08)

[^6]: Crypto Face — YouTube/Twitter presence for Bitcoin futures scalping (no verified PnL source found).

[^7]: Altcoin Psycho / PsychoBot — momentum breakout bot on Stacked platform. Source: https://sourceforge.net/software/crypto-trading-bots/canada/?page=3

[^8]: Best Scalping Strategies on TradingView 2026 — EMA, VWAP, RSI, ATR settings. Source: https://lunefi.com/blog/best-scalping-strategies-tradingview-2026-backtested-win-rates (2026-05-11)

[^9]: OrderFlow Trading Strategy — Volume Profile + Footprint for crypto scalping. Source: https://lilys.ai/notes/en/order-flow-trading-20260129/orderflow-trading-volume-profile-footprint (2026-01-28)

[^10]: Cumulative Volume Delta Trading Strategy — CVD, delta, divergence. Source: https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy (2026-01-21)

[^11]: Partials and Scaling Out — tiered exit mechanics. Source: https://pomegra.io/learn/library/track-e-trading-risk/active-trading/chapter-07-order-execution/partials-and-scaling-out-execution

[^12]: Position Sizing for Crypto Traders — scalper-specific sizing (0.25-0.5%). Source: https://thrive.fi/blog/trading/position-sizing-strategies-crypto (2025-09-15)

[^13]: 4 Scalping Strategies With Exact Entry and Exit Rules — hold times, trade frequency. Source: https://www.tradezella.com/blog/scalping-strategies (2026-04-01)

[^14]: Scalping Secrets of Anonymous Crypto Day Traders — 1R rule, daily loss limits. Source: https://quantstrategy.io/blog/the-scalping-secrets-of-the-best-anonymous-crypto-day/ (2026-01-12)

[^15]: Trading Risk Management 101 — kill switches, correlation caps, spread guards. Source: https://fintorai.com/trading-risk-management/ (2025-10-20)

[^16]: Best Crypto Pairs to Trade Today — BTC, ETH, SOL liquidity comparison. Source: https://bullpen.fi/bullpen-blog/best-crypto-pairs-to-trade-today (2026-04-29)

[^17]: 8 Forex Day Trading Strategies — London session scalping, EMA pullback. Source: https://homebusinessmag.com/money/forex-trading/forex-day-trading-strategies-guide/ (2026-02-06)

[^18]: ORACLE Gold Scalper / XAUUSD Scalper M1 — news filter, NFP/CPI avoidance, gap protection. Source: https://yoforex.org/oracle-gold-scalper-ea-v6-1-mt4/ (2026-01-10); https://eafxstore.com/product/xauusd-scalper-m1-ea/ (2026-04-20)

[^19]: LegacyCoinTrader — regime detection using EMA, ADX, RSI, BB width. Source: https://github.com/advancedAgritek-BB/LegacyCoinTrader1.0-main (2024-05-01)

[^20]: How To Set Up A Crypto Trading Bot — architecture, CCXT, Python, TradingView, VPS. Source: https://coinbureau.com/analysis/how-to-set-up-crypto-trading-bot (2026-05-09)

---

## 9. Appendix: Quick-Reference Cheat Sheet

### A. Pre-Trade Checklist
- [ ] HTF bias confirmed (1H/4H structure)
- [ ] Kill zone active (London/NY)
- [ ] No red-folder news in next 15 min
- [ ] Spread < 2x average
- [ ] ATR between 1x-2x 20-day average
- [ ] Risk per trade calculated (0.25-1%)
- [ ] Daily loss limit not yet reached
- [ ] Max open positions < 5
- [ ] Correlated exposure < 2 pairs per base

### B. Entry Checklist
- [ ] Liquidity sweep completed
- [ ] Price in OB/FVG zone (discount for longs, premium for shorts)
- [ ] LTF CHoCH or EMA crossover in bias direction
- [ ] RSI not at extreme
- [ ] Volume > 1.5x average
- [ ] CVD aligned (if available)
- [ ] Limit order set at zone; SL placed simultaneously

### C. Exit Checklist
- [ ] TP1 at 1R (close 25-33%)
- [ ] TP2 at 2R (close 25-33%)
- [ ] Runner with trailing stop or TP3 at 3R
- [ ] Time exit: max 5-20 min if no momentum
- [ ] Manual exit if LTF structure reverses

### D. Daily Shutdown Checklist
- [ ] All positions closed
- [ ] PnL logged
- [ ] Daily loss limit respected
- [ ] Review 3 biggest wins + 3 biggest losses
- [ ] Note any slippage or execution issues
- [ ] Update strategy parameters if data supports change

---

*Disclaimer: This research is for educational and automation-development purposes only. It does not constitute investment advice, trading recommendations, or guarantees of future performance. Crypto scalping carries significant risk of loss. Always conduct your own due diligence and backtesting before deploying capital or automation.*
