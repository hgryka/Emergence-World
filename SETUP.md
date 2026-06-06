# Emergence World — Setup Guide

## Prerequisites

- [Python 3.11+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — fast Python package and project manager

---

## 1. Create the Virtual Environment

From the repo root:

```bash
uv venv
```

This creates a `.venv/` directory. Activate it:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

---

## 2. Install Dependencies

A `pyproject.toml` is included at the repo root. Install all packages with:

```bash
uv sync
```

> All pinned wheels are sourced from PyPI. We intentionally use older pinned versions to improve stability, reduce supply-chain risk, and allow time for vulnerability scanning of newly released packages.

---

## 3. Configure Environment Variables

Create a `.env` file in the repo root (it is already in `.gitignore`):

```bash
cp .env.example .env
```

Then edit `.env` with your values:

```dotenv
# ── Required ────────────────────────────────────────────────────────────────
# Your Anthropic API key — https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY=sk-ant-...

# ── Optional overrides (defaults shown) ────────────────────────────────────
# Claude model to use for all agent turns
CLAUDE_MODEL=claude-sonnet-4-5
```

> `simulation/config.py` reads these variables at runtime via `os.getenv()`. Never hardcode secrets.

---

## 4. Run the Simulation

```bash
# Default: 50 rounds, resumes from simulation/state.json if it exists
python simulation/main.py
# or equivalently:
python -m simulation.main

# Custom round count
python simulation/main.py --rounds 100

# Specify a different model
python simulation/main.py --model claude-opus-4-5

# Dry run — no API calls, simulated agent responses (useful for testing setup)
python simulation/main.py --dry-run

# Reset and start fresh (deletes existing state.json)
python simulation/main.py --reset
```

### Output locations

| File | Contents |
|------|----------|
| `simulation/state.json` | Live world state — auto-saved each round |
| `simulation/logs/events.log` | Human-readable event log |
| `simulation/logs/state_snapshots/round_N.json` | Full world snapshot per round |
| `simulation/logs/summary.md` | Post-run leaderboard, proposals passed, survivors |

---

## Project Layout

```
Emergence-World/
├── simulation/
│   ├── __init__.py          # Package marker
│   ├── config.py            # All tuneable parameters (model, rounds, energy, economy)
│   ├── world.py             # WorldState, Landmark, AgentState dataclasses + persistence
│   ├── tools.py             # 23 agent-callable tool functions + Anthropic API schemas
│   ├── agent.py             # Agent class: system prompt builder + Claude API turn loop
│   └── main.py              # Simulation loop CLI
├── agent_profiles/          # 16 MBTI profile markdown files
├── landmarks/               # 38+ landmark markdown files + README
├── tools/                   # Tool catalog README
├── data/
│   ├── agent_manifesto.md   # Injected into every agent system prompt
│   └── constitution.md      # Starting world constitution
├── pyproject.toml           # uv project definition with pinned dependencies
├── .env.example             # API key template
└── SETUP.md                 # This file
```

---

## Build Status

| Phase | Component | Status |
|-------|-----------|--------|
| 1 | 16 MBTI agent profile files | ✅ Complete |
| 2 | `simulation/config.py`, `simulation/world.py`, all landmark files | ✅ Complete |
| 3 | `simulation/tools.py` — 44 tool schemas + `dispatch_tool()` | ✅ Complete |
| 4 | `simulation/agent.py` — `Agent` class, `build_system_prompt()`, `take_turn()`, reactive turns | ✅ Complete |
| 5 | `simulation/main.py` — simulation loop, CLI | ✅ Complete |
| 6 | Logs, `summary.md` | ✅ Complete |
| 6 | `requirements.txt` | ⬜ Pending |

---

## Key Configuration

All tuneable parameters live in `simulation/config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MODEL` | `claude-sonnet-4-5` | Claude model (override with `CLAUDE_MODEL` env var) |
| `DEFAULT_ROUNDS` | `50` | Rounds per simulation run |
| `MAX_TOOL_ITERATIONS` | `30` | Max tool calls per agent turn |
| `REACTION_TOOL_LIMIT` | `2` | Tool calls allowed in a reactive (speak-triggered) turn |
| `ENERGY_DECAY_PER_TURN` | `2.0` | Energy lost each round (%) |
| `ENERGY_CRITICAL` | `15.0` | Energy level that triggers urgent recharge warning |
| `CREDITS_START` | `20` | Starting ComputeCredits per agent |
| `CREDIT_CYCLE_ROUNDS` | `10` | Victory Arch pitch cycle frequency |
| `PROPOSAL_PASS_THRESHOLD` | `0.70` | Fraction of votes needed to pass a proposal |
