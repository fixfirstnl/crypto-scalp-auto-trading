"""Strategy Module: ICT/SMC Hybrid Scalping Strategy

Implements the Inner Circle Trader (ICT) / Smart Money Concepts (SMC) methodology
for scalping crypto futures. The strategy focuses on:

1. Market Structure (BOS/CHoCH) — Higher-timeframe directional bias
2. Order Blocks (OB) — Key supply/demand zones for entry
3. Fair Value Gaps (FVG) — Price inefficiency zones for confluence
4. Liquidity Sweeps — Asian range / equal highs/lows for entry triggers

The strategy uses a multi-timeframe approach:
- 1H/4H: Bias determination (MarketStructure)
- 15m: Setup scan (OrderBlocks + FVG + LiquiditySweep)
- 5m: Entry zone refinement
- 1m: LTF entry confirmation (EMA + RSI + Volume)

Usage:
    from src.strategy import ICTSMCStrategy
    strategy = ICTSMCStrategy(data_cache, indicator_engine)
    setup = strategy.scan_for_setup(symbol, bias, setup_candles, entry_candles)
    if setup['signal'] != 'none':
        entry = strategy.confirm_entry(setup, ltf_candles, indicators)
"""

from __future__ import annotations

from .market_structure import MarketStructure
from .order_blocks import OrderBlocks
from .fair_value_gaps import FairValueGaps
from .liquidity_sweep import LiquiditySweep
from .ict_smc_strategy import ICTSMCStrategy

__all__ = [
    'MarketStructure',
    'OrderBlocks',
    'FairValueGaps',
    'LiquiditySweep',
    'ICTSMCStrategy',
]
