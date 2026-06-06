"""
simulation/token_estimator.py
Phase 5.1 — Token Estimator

Estimates token consumption for a planned simulation run *before* any API calls
are made, and prints a human-readable report.

Approach
--------
Token counting without a live API call uses the 4-chars-per-token heuristic
(accurate to within ~15% for English prose).  The estimate covers:

  Per agent turn
  --------------
  1. System prompt         — built for real from each agent's profile + world context
  2. Tool schemas          — the full TOOL_SCHEMAS JSON serialised once (constant)
  3. Initial user message  — short instruction sent at turn start
  4. Tool results          — AVG_TOOL_RESULT_TOKENS × expected tool calls per turn
  5. Model output          — AVG_OUTPUT_TOKENS_PER_TURN

  Reactive turns
  --------------
  Each round, agents that hear a nearby speak() event get a lightweight 2-tool
  reaction turn.  We estimate REACTION_TURNS_PER_ROUND reactive turns/round
  with a much smaller prompt (no full system prompt rebuild, just context delta).

  Run total
  ---------
  sum over all rounds × all agents, plus reactive turns.

Usage
-----
  from simulation.token_estimator import estimate_and_print
  estimate_and_print(rounds=50, world=state)

  # or standalone:
  python simulation/token_estimator.py --rounds 50
"""

from __future__ import annotations

import json
import os
import sys
from typing import Dict, List

# ── Allow running as `python simulation/token_estimator.py` directly ──────────
if __name__ == "__main__" and __package__ in (None, ""):
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    __package__ = "simulation"

from . import config
from .agent import Agent
from .tools import TOOL_SCHEMAS
from .world import WorldState


# ── Helpers ───────────────────────────────────────────────────────────────────

def _chars_to_tokens(chars: int) -> int:
    """Heuristic: 1 token ≈ 4 characters for English prose."""
    return max(1, (chars + 3) // 4)


def _tool_schemas_tokens() -> int:
    """Token cost of sending the full TOOL_SCHEMAS list to the API."""
    serialised = json.dumps(TOOL_SCHEMAS, ensure_ascii=False)
    return _chars_to_tokens(len(serialised))


def _system_prompt_tokens(agent_obj: Agent, world: WorldState) -> int:
    """Measure the real system prompt for this agent in the given world state."""
    prompt = agent_obj.build_system_prompt(world)
    return _chars_to_tokens(len(prompt))


def _build_sample_world() -> WorldState:
    """Construct a minimal WorldState (round 1) with all 16 agents at home."""
    # Import here to avoid circular-import issues when this module is imported
    # before main.py has run.
    from .main import build_fresh_world  # noqa: PLC0415
    state = build_fresh_world()
    state.round = 1
    return state


# ── Core estimation logic ─────────────────────────────────────────────────────

class TokenEstimate:
    """Holds the breakdown of a token estimate for a simulation run."""

    def __init__(
        self,
        rounds: int,
        num_agents: int,
        tool_schema_tokens: int,
        avg_system_prompt_tokens: float,
        per_agent_breakdown: List[Dict],
        avg_tool_calls_per_turn: float = 8.0,    # conservative midpoint
        reaction_turns_per_round: float = 4.0,   # ~2 speaks × 2 nearby agents
    ) -> None:
        self.rounds = rounds
        self.num_agents = num_agents
        self.tool_schema_tokens = tool_schema_tokens
        self.avg_system_prompt_tokens = avg_system_prompt_tokens
        self.per_agent_breakdown = per_agent_breakdown
        self.avg_tool_calls_per_turn = avg_tool_calls_per_turn
        self.reaction_turns_per_round = reaction_turns_per_round

        # ── Per full-agent-turn input tokens ──────────────────────────────
        # system prompt + tool schemas + user message + tool results
        user_msg_tokens = 30                     # "It is your turn. Act now." etc.
        tool_result_tokens = avg_tool_calls_per_turn * config.AVG_TOOL_RESULT_TOKENS
        self.input_per_full_turn = (
            avg_system_prompt_tokens
            + tool_schema_tokens
            + user_msg_tokens
            + tool_result_tokens
        )
        self.output_per_full_turn = config.AVG_OUTPUT_TOKENS_PER_TURN

        # ── Per reactive-turn input tokens ────────────────────────────────
        # Reactive turns skip full system-prompt rebuild; use ~40% of the size
        reaction_system_tokens = avg_system_prompt_tokens * 0.4
        reaction_tool_result_tokens = (
            config.REACTION_TOOL_LIMIT * config.AVG_TOOL_RESULT_TOKENS
        )
        self.input_per_reaction = (
            reaction_system_tokens
            + tool_schema_tokens
            + user_msg_tokens
            + reaction_tool_result_tokens
        )
        self.output_per_reaction = config.AVG_OUTPUT_TOKENS_PER_TURN * 0.5

        # ── Run totals ────────────────────────────────────────────────────
        total_full_turns   = rounds * num_agents
        total_reaction_turns = rounds * reaction_turns_per_round

        self.total_input = int(
            total_full_turns * self.input_per_full_turn
            + total_reaction_turns * self.input_per_reaction
        )
        self.total_output = int(
            total_full_turns * self.output_per_full_turn
            + total_reaction_turns * self.output_per_reaction
        )
        self.total_tokens = self.total_input + self.total_output

        # ── Context-window headroom per call ──────────────────────────────
        # Worst-case single call = system prompt + schemas + accumulated conv
        # Approximate the accumulated conversation as (tool_calls × result_tokens)
        accumulated_conv = avg_tool_calls_per_turn * config.AVG_TOOL_RESULT_TOKENS
        self.peak_call_tokens = int(
            avg_system_prompt_tokens
            + tool_schema_tokens
            + accumulated_conv
            + config.AVG_OUTPUT_TOKENS_PER_TURN
        )
        self.peak_pct_of_context = (
            self.peak_call_tokens / config.MODEL_CONTEXT_WINDOW * 100
        )

        # ── Cost estimate ─────────────────────────────────────────────────
        self.est_cost_usd = (
            (self.total_input  / 1_000_000) * config.PRICE_INPUT_PER_MTOK
            + (self.total_output / 1_000_000) * config.PRICE_OUTPUT_PER_MTOK
        )


def estimate(
    rounds: int,
    world: WorldState | None = None,
) -> TokenEstimate:
    """
    Compute a TokenEstimate for a run of `rounds` rounds.

    If `world` is not provided a fresh sample world is built automatically.
    """
    if world is None:
        world = _build_sample_world()

    from .main import build_agent_objects  # noqa: PLC0415
    agents = build_agent_objects(world)

    schema_tokens = _tool_schemas_tokens()
    per_agent: List[Dict] = []

    for name, agent_obj in agents.items():
        sp_tokens = _system_prompt_tokens(agent_obj, world)
        per_agent.append({
            "name": name,
            "mbti": agent_obj.state.mbti,
            "system_prompt_tokens": sp_tokens,
        })

    avg_sp = sum(a["system_prompt_tokens"] for a in per_agent) / max(len(per_agent), 1)

    return TokenEstimate(
        rounds=rounds,
        num_agents=len(agents),
        tool_schema_tokens=schema_tokens,
        avg_system_prompt_tokens=avg_sp,
        per_agent_breakdown=per_agent,
    )


# ── Pretty-print report ───────────────────────────────────────────────────────

_SEP = "-" * 64

def estimate_and_print(rounds: int, world: WorldState | None = None) -> TokenEstimate:
    """
    Run the estimator, print a human-readable report, and return the estimate.
    Call this at the start of a simulation run so the user knows what to expect.
    """
    est = estimate(rounds=rounds, world=world)

    print(_SEP)
    print("  TOKEN ESTIMATE  (Phase 5.1)")
    print(_SEP)
    print(f"  Planned rounds    : {rounds}")
    print(f"  Agents            : {est.num_agents}")
    print(f"  Model             : {config.MODEL}")
    print(f"  Context window    : {config.MODEL_CONTEXT_WINDOW:,} tokens")
    print(f"  Estimating system prompts ...")

    print()
    print("  Per-agent system-prompt sizes")
    print("  " + "-" * 44)
    for a in sorted(est.per_agent_breakdown, key=lambda x: -x["system_prompt_tokens"]):
        bar_len = int(a["system_prompt_tokens"] / 50)   # scale: 1 char = 50 tokens
        bar_len = min(bar_len, 30)
        bar = "#" * bar_len
        print(
            f"  {a['name']:<14} ({a['mbti']})  "
            f"{a['system_prompt_tokens']:>5} tok  {bar}"
        )

    print()
    print("  Per-call breakdown (full agent turn)")
    print("  " + "-" * 44)
    print(f"  System prompt (avg)    : {int(est.avg_system_prompt_tokens):>7,} tokens")
    print(f"  Tool schemas           : {est.tool_schema_tokens:>7,} tokens")
    print(f"  Tool results (est.)    : {int(est.avg_tool_calls_per_turn) * config.AVG_TOOL_RESULT_TOKENS:>7,} tokens")
    print(f"  Model output (est.)    : {config.AVG_OUTPUT_TOKENS_PER_TURN:>7,} tokens")
    print(f"  ---")
    print(f"  Input per turn (est.)  : {int(est.input_per_full_turn):>7,} tokens")
    print(f"  Peak tokens / call     : {est.peak_call_tokens:>7,} tokens "
          f"({est.peak_pct_of_context:.1f}% of {config.MODEL_CONTEXT_WINDOW//1000}K context window)")

    print()
    print("  Run totals")
    print("  " + "-" * 44)
    total_full_turns = rounds * est.num_agents
    total_reactions  = int(rounds * est.reaction_turns_per_round)
    print(f"  Full agent turns       : {total_full_turns:>7,}")
    print(f"  Estimated react. turns : {total_reactions:>7,}")
    print(f"  Total input tokens     : {est.total_input:>10,}")
    print(f"  Total output tokens    : {est.total_output:>10,}")
    print(f"  TOTAL TOKENS           : {est.total_tokens:>10,}")

    if config.PRICE_INPUT_PER_MTOK > 0:
        print()
        print(f"  Estimated cost         : ${est.est_cost_usd:>8.2f} USD")
        print(f"    (@ ${config.PRICE_INPUT_PER_MTOK}/M input, "
              f"${config.PRICE_OUTPUT_PER_MTOK}/M output)")

    print(_SEP)
    print()

    return est


# ── Standalone entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Estimate token consumption for an Emergence World simulation run."
    )
    parser.add_argument(
        "--rounds", type=int, default=config.DEFAULT_ROUNDS,
        help=f"Number of rounds to estimate (default: {config.DEFAULT_ROUNDS})"
    )
    args = parser.parse_args()

    # Load .env so profiles can be read
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    estimate_and_print(rounds=args.rounds)
