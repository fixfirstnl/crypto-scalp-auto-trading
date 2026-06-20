"""crew_setup.py — CrewAI Trading Crew Configuration.

Wraps the four rule-based agents (Bias, Signal, Risk, Exec) inside
CrewAI ``Agent`` / ``Task`` / ``Crew`` constructs.  The **fast path**
(:meth:`TradingCrew.run_signal_pipeline`) bypasses LLM reasoning entirely
and calls the tool functions directly for <2-second latency.

The **slow path** (:meth:`TradingCrew.run_single_agent`) uses CrewAI's
native LLM-powered task execution for debugging, ambiguous cases, or
human-in-the-loop review.

Dependencies
------------
- ``crewai`` (pip install crewai)
- Python 3.11+

Usage
-----
    crew = TradingCrew(
        data_cache, indicator_engine, strategy,
        risk_manager, order_manager, position_tracker,
        llm_model="gpt-4o-mini",
    )
    result = await crew.run_signal_pipeline("BTC/USDT:USDT")
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from crewai import Agent, Task, Crew, Process

    CREWAI_AVAILABLE = True
except ImportError as exc:  # pragma: no cover
    CREWAI_AVAILABLE = False
    Agent = None  # type: ignore
    Task = None  # type: ignore
    Crew = None  # type: ignore
    Process = None  # type: ignore
    logging.getLogger(__name__).warning(
        "crewai not installed (%s). CrewAI features unavailable. Fast path still works.",
        exc,
    )

from src.layer1_data import DataCache, IndicatorEngine
from src.layer3_trading import OrderManager, PositionTracker, RiskManager
from src.strategy import ICTSMCStrategy

from .bias_agent import BiasAgent
from .signal_agent import SignalAgent
from .risk_agent import RiskAgent
from .exec_agent import ExecAgent
from .consensus import ConsensusEngine

logger = logging.getLogger(__name__)


class TradingCrew:
    """CrewAI-orchestrated trading crew with 4 specialist agents + consensus.

    Parameters
    ----------
    data_cache : DataCache
    indicator_engine : IndicatorEngine
    strategy : ICTSMCStrategy
    risk_manager : RiskManager
    order_manager : OrderManager
    position_tracker : PositionTracker
    llm_model : str, default "gpt-4o-mini"
        LiteLLM-compatible model string for CrewAI agents.
    """

    def __init__(
        self,
        data_cache: DataCache,
        indicator_engine: IndicatorEngine,
        strategy: ICTSMCStrategy,
        risk_manager: RiskManager,
        order_manager: OrderManager,
        position_tracker: PositionTracker,
        llm_model: str = "gpt-4o-mini",
    ) -> None:
        self.data_cache = data_cache
        self.indicator_engine = indicator_engine
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.order_manager = order_manager
        self.position_tracker = position_tracker
        self.llm_model = llm_model

        # Rule-based tool instances (fast path)
        self.bias_tool = BiasAgent(data_cache, indicator_engine)
        self.signal_tool = SignalAgent(data_cache, indicator_engine, strategy)
        self.risk_tool = RiskAgent(risk_manager, position_tracker, data_cache)
        self.exec_tool = ExecAgent(order_manager, data_cache)
        self.consensus = ConsensusEngine()

        # Lazy-initialized CrewAI wrappers
        self._bias_agent: Optional[Agent] = None  # type: ignore
        self._signal_agent: Optional[Agent] = None  # type: ignore
        self._risk_agent: Optional[Agent] = None  # type: ignore
        self._exec_agent: Optional[Agent] = None  # type: ignore

        logger.info("TradingCrew initialized | LLM=%s", llm_model)

    # ------------------------------------------------------------------ #
    #  CrewAI Agent Factories
    # ------------------------------------------------------------------ #

    def create_bias_agent(self) -> Agent:  # type: ignore
        """Create the CrewAI Higher-Timeframe Analyst agent."""
        if not CREWAI_AVAILABLE:
            raise ImportError("crewai is required for CrewAI agents.")
        if self._bias_agent is None:
            self._bias_agent = Agent(
                role="Higher-Timeframe Analyst",
                goal=(
                    "Determine bullish/bearish/neutral bias on 1H/4H timeframes "
                    "using ICT market structure analysis (BOS/CHoCH)."
                ),
                backstory=(
                    "You are an expert ICT market structure analyst with 15+ years of experience. "
                    "You identify Breaks of Structure (BOS) and Changes of Character (CHoCH) "
                    "on higher timeframes to determine directional bias. You never guess — "
                    "you only report what the structure objectively shows."
                ),
                tools=[self._analyze_bias_tool],
                llm=self.llm_model,
                verbose=False,
                allow_delegation=False,
                max_iter=1,
            )
        return self._bias_agent

    def create_signal_agent(self) -> Agent:  # type: ignore
        """Create the CrewAI Entry Signal Generator agent."""
        if not CREWAI_AVAILABLE:
            raise ImportError("crewai is required for CrewAI agents.")
        if self._signal_agent is None:
            self._signal_agent = Agent(
                role="Entry Signal Generator",
                goal=(
                    "Find liquidity sweeps + OB/FVG confluence + EMA cross + RSI setups "
                    "for high-probability scalp entries."
                ),
                backstory=(
                    "You are a master ICT scalping specialist who identifies A+ entry setups. "
                    "You scan for liquidity sweeps, order block + fair value gap confluence, "
                    "and confirm entries with EMA crossovers and RSI readings. You only "
                    "report setups with clear entry, stop-loss, and take-profit levels."
                ),
                tools=[self._generate_signal_tool],
                llm=self.llm_model,
                verbose=False,
                allow_delegation=False,
                max_iter=1,
            )
        return self._signal_agent

    def create_risk_agent(self) -> Agent:  # type: ignore
        """Create the CrewAI Risk Manager agent."""
        if not CREWAI_AVAILABLE:
            raise ImportError("crewai is required for CrewAI agents.")
        if self._risk_agent is None:
            self._risk_agent = Agent(
                role="Risk Manager",
                goal=(
                    "Size positions, check daily/weekly limits, enforce spread/ATR guards, "
                    "and approve or veto every trade with prop-firm discipline."
                ),
                backstory=(
                    "You are a prop-firm risk manager with strict discipline. You enforce "
                    "daily loss limits, max position counts, spread guards, ATR filters, and "
                    "correlation limits. You have the power to VETO any trade that doesn't "
                    "meet risk criteria. Your decisions are final and based purely on the "
                    "risk framework."
                ),
                tools=[self._evaluate_risk_tool],
                llm=self.llm_model,
                verbose=False,
                allow_delegation=False,
                max_iter=1,
            )
        return self._risk_agent

    def create_exec_agent(self) -> Agent:  # type: ignore
        """Create the CrewAI Execution Optimizer agent."""
        if not CREWAI_AVAILABLE:
            raise ImportError("crewai is required for CrewAI agents.")
        if self._exec_agent is None:
            self._exec_agent = Agent(
                role="Execution Optimizer",
                goal=(
                    "Choose optimal order type (limit vs market), manage partial fills, "
                    "and optimize execution quality for scalp trades."
                ),
                backstory=(
                    "You are a low-latency execution specialist who minimizes slippage and "
                    "maximizes fill rates. You decide between limit and market orders based "
                    "on spread and momentum. You structure partial profit-taking (33/33/34) "
                    "and trailing stop activation after TP2."
                ),
                tools=[self._optimize_exec_tool],
                llm=self.llm_model,
                verbose=False,
                allow_delegation=False,
                max_iter=1,
            )
        return self._exec_agent

    # ------------------------------------------------------------------ #
    #  Tool Wrappers (sync, bound as CrewAI tools)
    # ------------------------------------------------------------------ #

    def _analyze_bias_tool(self, symbol: str) -> str:
        """Analyze HTF market bias for the given symbol.

        Args:
            symbol: Trading pair (e.g. 'BTC/USDT:USDT')

        Returns:
            JSON string with bias, confidence, structure details.
        """
        try:
            result = self._run_sync(self.bias_tool.analyze(symbol))
            return json.dumps(result, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc), "bias": "neutral", "confidence": 0.0})

    def _generate_signal_tool(self, input_json: str) -> str:
        """Generate entry signal given HTF bias.

        Args:
            input_json: JSON string with keys 'symbol' and 'bias'.

        Returns:
            JSON string with signal details, or 'none' if no valid setup.
        """
        try:
            data = json.loads(input_json)
            symbol = data.get("symbol", "")
            bias = data.get("bias", {})
            result = self._run_sync(self.signal_tool.generate(symbol, bias))
            if result is None:
                return json.dumps({"signal": "none"})
            return json.dumps(result, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc), "signal": "none"})

    def _evaluate_risk_tool(self, input_json: str) -> str:
        """Evaluate risk for a proposed trade signal.

        Args:
            input_json: JSON string with keys 'signal' and 'symbol'.

        Returns:
            JSON string with approved, size, risk_score, reason.
        """
        try:
            data = json.loads(input_json)
            signal = data.get("signal", {})
            symbol = data.get("symbol", "")
            result = self._run_sync(self.risk_tool.evaluate(signal, symbol))
            return json.dumps(result, default=str)
        except Exception as exc:
            return json.dumps({"approved": False, "reason": str(exc)})

    def _optimize_exec_tool(self, input_json: str) -> str:
        """Optimize execution plan for an approved trade.

        Args:
            input_json: JSON string with keys 'signal' and 'risk_decision'.

        Returns:
            JSON string with order_type, entry_price, partials, sl_order.
        """
        try:
            data = json.loads(input_json)
            signal = data.get("signal", {})
            risk_decision = data.get("risk_decision", {})
            result = self._run_sync(self.exec_tool.optimize(signal, risk_decision))
            return json.dumps(result, default=str)
        except Exception as exc:
            return json.dumps({"order_type": "none", "reason": str(exc)})

    # ------------------------------------------------------------------ #
    #  Fast Pipeline — Direct async (no LLM, target <2s)
    # ------------------------------------------------------------------ #

    async def run_signal_pipeline(self, symbol: str) -> Dict[str, Any]:
        """Execute the full signal pipeline: Bias → Signal → Risk → Exec → Consensus.

        This is the **FAST PATH**.  It bypasses CrewAI LLM reasoning and calls the
        rule-based tools directly via ``async/await``, achieving sub-second latency
        per stage.

        Pipeline flow
        ------------
        1. **BiasAgent** — HTF structure analysis (1H/4H).
        2. **SignalAgent** — Setup scan + entry confirmation (15m/5m/1m).
        3. **RiskAgent** — Risk gates + position sizing.
        4. **ExecAgent** — Order type + partials + SL config.
        5. **ConsensusEngine** — Final buy/sell/hold vote.

        Parameters
        ----------
        symbol : str
            CCXT unified symbol (e.g. ``'BTC/USDT:USDT'``).

        Returns
        -------
        dict
            ``consensus`` (``'buy'`` | ``'sell'`` | ``'hold'``),
            ``confidence`` (float), ``details`` (diagnostics), ``trade`` (dict or None).
        """
        start_time = datetime.now(timezone.utc)

        # Stage 1 — Bias
        bias = await self.bias_tool.analyze(symbol)
        if bias.get("bias") == "neutral":
            result = self.consensus.evaluate(bias, None, None, None)
            self._log_pipeline_duration(start_time, symbol, result)
            return result

        # Stage 2 — Signal
        signal = await self.signal_tool.generate(symbol, bias)
        if signal is None or signal.get("signal", "none") == "none":
            result = self.consensus.evaluate(bias, signal, None, None)
            self._log_pipeline_duration(start_time, symbol, result)
            return result

        # Stage 3 — Risk
        risk = await self.risk_tool.evaluate(signal, symbol)
        if not risk.get("approved", False):
            result = self.consensus.evaluate(bias, signal, risk, None)
            self._log_pipeline_duration(start_time, symbol, result)
            return result

        # Stage 4 — Execution
        exec_plan = await self.exec_tool.optimize(signal, risk)

        # Stage 5 — Consensus
        result = self.consensus.evaluate(bias, signal, risk, exec_plan)
        self._log_pipeline_duration(start_time, symbol, result)
        return result

    # ------------------------------------------------------------------ #
    #  Single Agent — CrewAI-powered (slow path, for debugging / review)
    # ------------------------------------------------------------------ #

    async def run_single_agent(
        self, agent_name: str, task_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run a single CrewAI agent for a specific task.

        This is the **SLOW PATH** that uses CrewAI's LLM for interpretation.
        Useful for debugging, ambiguous cases, or human-in-the-loop review.

        Parameters
        ----------
        agent_name : str
            One of ``'bias'``, ``'signal'``, ``'risk'``, ``'exec'``.
        task_input : dict
            Parameters for the agent's tool (e.g. ``{'symbol': 'BTC/USDT:USDT'}``).

        Returns
        -------
        dict
            ``agent``, ``output``, and optional ``error``.
        """
        if not CREWAI_AVAILABLE:
            return {
                "error": "crewai not installed — cannot run single-agent mode",
                "agent": agent_name,
                "output": None,
            }

        try:
            if agent_name == "bias":
                agent = self.create_bias_agent()
                task = Task(
                    description=(
                        f"Analyze the higher-timeframe market bias for "
                        f"{task_input.get('symbol', 'unknown')} using the analyze_bias tool."
                    ),
                    expected_output="JSON with bias, confidence, and structure details",
                    agent=agent,
                )
                crew = Crew(
                    agents=[agent], tasks=[task], process=Process.sequential, verbose=False
                )
                raw = await asyncio.to_thread(crew.kickoff)
                return self._format_output(agent_name, raw)

            elif agent_name == "signal":
                agent = self.create_signal_agent()
                payload = json.dumps(
                    {
                        "symbol": task_input.get("symbol", ""),
                        "bias": task_input.get("bias", {}),
                    }
                )
                task = Task(
                    description=(
                        f"Generate an entry signal using the generate_signal tool with this input: {payload}"
                    ),
                    expected_output="JSON with signal, entry, stop, targets, and confidence",
                    agent=agent,
                )
                crew = Crew(
                    agents=[agent], tasks=[task], process=Process.sequential, verbose=False
                )
                raw = await asyncio.to_thread(crew.kickoff)
                return self._format_output(agent_name, raw)

            elif agent_name == "risk":
                agent = self.create_risk_agent()
                payload = json.dumps(
                    {
                        "signal": task_input.get("signal", {}),
                        "symbol": task_input.get("symbol", ""),
                    }
                )
                task = Task(
                    description=(
                        f"Evaluate risk for this trade using the evaluate_risk tool: {payload}"
                    ),
                    expected_output="JSON with approved, size, risk_score, and reason",
                    agent=agent,
                )
                crew = Crew(
                    agents=[agent], tasks=[task], process=Process.sequential, verbose=False
                )
                raw = await asyncio.to_thread(crew.kickoff)
                return self._format_output(agent_name, raw)

            elif agent_name == "exec":
                agent = self.create_exec_agent()
                payload = json.dumps(
                    {
                        "signal": task_input.get("signal", {}),
                        "risk_decision": task_input.get("risk_decision", {}),
                    }
                )
                task = Task(
                    description=(
                        f"Optimize execution plan using the optimize_exec tool: {payload}"
                    ),
                    expected_output="JSON with order_type, entry_price, partials, sl_order",
                    agent=agent,
                )
                crew = Crew(
                    agents=[agent], tasks=[task], process=Process.sequential, verbose=False
                )
                raw = await asyncio.to_thread(crew.kickoff)
                return self._format_output(agent_name, raw)

            else:
                return {"error": f"Unknown agent: {agent_name}", "agent": agent_name}

        except Exception as exc:
            logger.error("run_single_agent failed for %s: %s", agent_name, exc)
            return {"error": str(exc), "agent": agent_name, "output": None}

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _run_sync(coro) -> Any:
        """Execute an async coroutine in a fresh event loop (CrewAI tool bridge)."""
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    @staticmethod
    def _format_output(agent_name: str, raw: Any) -> Dict[str, Any]:
        """Normalise CrewAI kickoff output into a plain dict."""
        output = getattr(raw, "raw", str(raw)) if raw is not None else ""
        return {"agent": agent_name, "output": output}

    @staticmethod
    def _log_pipeline_duration(
        start_time: datetime, symbol: str, result: Dict[str, Any]
    ) -> None:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        consensus = result.get("consensus", "hold")
        trade = result.get("trade")
        if trade:
            logger.info(
                "Pipeline: %s | consensus=%s | entry=%.2f | size=%.4f | duration=%.3fs",
                symbol,
                consensus,
                trade.get("entry_price", 0.0),
                trade.get("size", 0.0),
                duration,
            )
        else:
            logger.info(
                "Pipeline: %s | consensus=%s | duration=%.3fs",
                symbol,
                consensus,
                duration,
            )
