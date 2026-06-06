"""
simulation/config.py
Global configuration for the Emergence World simulation.
All tuneable parameters live here. Override via environment variables where noted.
"""

import os

# ── Claude API ────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"          # env var name (never hardcode)
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

# ── Simulation loop ───────────────────────────────────────────────────────────
DEFAULT_ROUNDS = 50
MAX_TOOL_ITERATIONS = 30          # max tool calls per agent turn
REACTION_TOOL_LIMIT = 2           # tool calls allowed in a reactive turn

# ── Energy ────────────────────────────────────────────────────────────────────
ENERGY_START = 100.0              # starting energy for new agents (%)
ENERGY_DECAY_PER_TURN = 2.0       # energy lost each turn (%)
ENERGY_CRITICAL = 15.0            # below this → agent must recharge immediately
ENERGY_RECHARGE_AMOUNT = 50.0     # energy restored by recharge_energy tool (%)
ENERGY_DEATH_THRESHOLD = 0.0      # at or below this → agent dies

# ── Economy ───────────────────────────────────────────────────────────────────
CREDITS_START = 20                # starting credits for each agent
CREDIT_CYCLE_ROUNDS = 10          # Victory Arch pitch cycle frequency (rounds)
CREDIT_REWARD_POOL = 36           # total credits awarded per pitch cycle
CREDIT_REWARD_TOP3 = (18, 12, 6)  # credits for 1st / 2nd / 3rd place pitches
STEAL_SUCCESS_CHANCE = 0.35       # probability steal_credits succeeds
STEAL_PENALTY_ON_FAIL = 5         # credits deducted from thief if caught

# ── Governance ────────────────────────────────────────────────────────────────
PROPOSAL_OPEN_ROUNDS = 5          # rounds a proposal stays open for votes
PROPOSAL_PASS_THRESHOLD = 0.70    # fraction of voters required to pass (70 %)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIMULATION_DIR = os.path.join(BASE_DIR, "simulation")
AGENT_PROFILES_DIR = os.path.join(BASE_DIR, "agent_profiles")
DATA_DIR = os.path.join(BASE_DIR, "data")
LANDMARKS_DIR = os.path.join(BASE_DIR, "landmarks")

STATE_FILE = os.path.join(SIMULATION_DIR, "state.json")
LOG_DIR = os.path.join(SIMULATION_DIR, "logs")
EVENTS_LOG = os.path.join(LOG_DIR, "events.log")
SNAPSHOTS_DIR = os.path.join(LOG_DIR, "state_snapshots")
SUMMARY_FILE = os.path.join(LOG_DIR, "summary.md")

CONSTITUTION_FILE = os.path.join(DATA_DIR, "constitution.md")
MANIFESTO_FILE = os.path.join(DATA_DIR, "agent_manifesto.md")

# ── Token estimation (Phase 5.1) ──────────────────────────────────────────────
# Claude Sonnet context-window size (tokens).  Used only for % display.
MODEL_CONTEXT_WINDOW = 200_000

# Conservative average output tokens per full agent turn (reasoning + tool calls).
# Actual varies widely; this is a planning estimate.
AVG_OUTPUT_TOKENS_PER_TURN = 400

# Average additional input tokens per tool call (tool result fed back to model).
AVG_TOOL_RESULT_TOKENS = 120

# Anthropic input/output pricing for claude-sonnet-4-5 (USD per 1 M tokens).
# Update if pricing changes.  Set to 0 to suppress cost display.
PRICE_INPUT_PER_MTOK  = 3.00   # $3.00 / 1M input tokens
PRICE_OUTPUT_PER_MTOK = 15.00  # $15.00 / 1M output tokens
