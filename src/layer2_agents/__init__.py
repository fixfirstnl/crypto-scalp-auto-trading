"""Layer 2: Agentic Layer — Multi-agent AI decision engine for ICT/SMC scalping.

Exports the CrewAI-orchestrated trading crew and individual rule-based agents
used for fast-path signal generation.  The fast path bypasses LLM reasoning
and executes rule-based tools directly for <2-second pipeline latency.

Components
----------
- TradingCrew    : CrewAI orchestrator with 4 agents + consensus engine
- BiasAgent      : Higher-timeframe bias detection (rule-based)
- SignalAgent    : Entry signal generation (rule-based)
- RiskAgent      : Risk management with veto power (rule-based)
- ExecAgent      : Execution optimization (rule-based)
- ConsensusEngine: Voting / consensus logic

Usage
-----
    from src.layer2_agents import TradingCrew
    crew = TradingCrew(data_cache, indicator_engine, strategy,
                       risk_manager, order_manager, position_tracker)
    result = await crew.run_signal_pipeline("BTC/USDT:USDT")
    # result["consensus"] is "buy", "sell", or "hold"

Author: Agent_Layer_Dev
Version: 1.0.0
"""

from __future__ import annotations

from .crew_setup import TradingCrew
from .bias_agent import BiasAgent
from .signal_agent import SignalAgent
from .risk_agent import RiskAgent
from .exec_agent import ExecAgent
from .consensus import ConsensusEngine

__all__ = [
    "TradingCrew",
    "BiasAgent",
    "SignalAgent",
    "RiskAgent",
    "ExecAgent",
    "ConsensusEngine",
]

__version__ = "1.0.0"
