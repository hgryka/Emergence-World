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

> All pinned wheels are sourced from PyPI and are at older to ensure stability/ time for virus ID in new packages.

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
│   ├── config.py        # All tuneable parameters
│   ├── world.py         # WorldState, Landmark definitions, dataclasses
│   ├── tools.py         # ~22 agent tool functions
│   ├── agent.py         # Agent class, system prompt builder, turn logic
│   ├── main.py          # Simulation loop and CLI entry point
│   ├── state.json       # Persisted world state (auto-generated)
│   └── logs/            # Events, snapshots, summary (auto-generated)
├── agent_profiles/      # 16 MBTI agent profile markdown files
├── data/
│   ├── constitution.md  # Starting world constitution
│   └── agent_manifesto.md  # Survival rules injected into every agent prompt
├── landmarks/           # 33 landmark markdown files + README
├── pyproject.toml
├── .env                 # Your secrets (not committed)
├── .env.example         # Template
└── SETUP.md             # This file
```
