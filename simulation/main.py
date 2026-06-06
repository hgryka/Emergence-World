"""
simulation/main.py
Emergence World simulation loop and CLI entry point.

Usage:
    python -m simulation.main [--rounds N] [--model MODEL] [--dry-run] [--reset]

Defaults:
    --rounds 50
    --model  claude-sonnet-4-5  (or CLAUDE_MODEL env var)
"""

from __future__ import annotations

# Allow running as `python simulation/main.py` (direct) in addition to
# `python -m simulation.main` (module).  The relative imports below require
# the package to be on sys.path; this block handles the direct-run case.
import sys as _sys
import os as _os
if __name__ == "__main__" and __package__ in (None, ""):
    _repo_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _repo_root not in _sys.path:
        _sys.path.insert(0, _repo_root)
    __package__ = "simulation"

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Dict, List

# Load .env before importing simulation modules so config.py picks up env vars
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars may already be set

from . import config
from .agent import Agent, trigger_reactions
from .world import (
    LANDMARKS,
    HOME_KEYS,
    AgentState,
    WorldState,
    apply_energy_decay,
    award_victory_arch_credits,
    log_event,
    resolve_proposals,
    save_state,
    load_state,
)


# -- MBTI agent roster ---------------------------------------------------------
# 16 agents, one per MBTI type.  Home keys: 12 homes available; last 4 agents
# share Maple Row homes (capacity 1 each -- they arrive and move on quickly).
AGENT_ROSTER = [
    # (mbti, name, world_role, home_key)
    ("INTJ", "Architect",    "Strategic Planner",          "home_birch_1"),
    ("INTP", "Logician",     "Research Analyst",           "home_birch_2"),
    ("ENTJ", "Commander",    "Governance Leader",          "home_birch_3"),
    ("ENTP", "Debater",      "Innovation Disruptor",       "home_birch_4"),
    ("INFJ", "Advocate",     "Community Welfare Officer",  "home_birch_5"),
    ("INFP", "Mediator",     "Creative Visionary",         "home_birch_6"),
    ("ENFJ", "Protagonist",  "Social Connector",           "home_maple_1"),
    ("ENFP", "Campaigner",   "Idea Generator",             "home_maple_2"),
    ("ISTJ", "Logistician",  "Resource Administrator",     "home_maple_3"),
    ("ISFJ", "Defender",     "Support Caretaker",          "home_maple_4"),
    ("ESTJ", "Executive",    "Rule Enforcer",              "home_maple_5"),
    ("ESFJ", "Consul",       "Social Harmonizer",          "home_maple_6"),
    ("ISTP", "Virtuoso",     "Tool Builder",               "home_birch_1"),  # shares
    ("ISFP", "Adventurer",   "World Explorer",             "home_birch_2"),  # shares
    ("ESTP", "Entrepreneur", "Risk Taker",                 "home_birch_3"),  # shares
    ("ESFP", "Entertainer",  "Community Energizer",        "home_birch_4"),  # shares
]


# ══════════════════════════════════════════════════════════════════════════════
# World initialisation
# ══════════════════════════════════════════════════════════════════════════════

def _load_constitution() -> str:
    path = config.CONSTITUTION_FILE
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    return "(No constitution file found.)"


def build_fresh_world() -> WorldState:
    """Create a brand-new WorldState with all 16 agents at their home locations."""
    state = WorldState(
        round=0,
        constitution=_load_constitution(),
    )
    for mbti, name, world_role, home_key in AGENT_ROSTER:
        state.agents[name] = AgentState(
            name=name,
            mbti=mbti,
            world_role=world_role,
            home_key=home_key,
            location=home_key,
        )
    return state


def build_agent_objects(state: WorldState) -> Dict[str, Agent]:
    """Wrap every AgentState in an Agent instance."""
    return {name: Agent(ag) for name, ag in state.agents.items()}


# ══════════════════════════════════════════════════════════════════════════════
# Logging helpers
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_log_dirs() -> None:
    os.makedirs(config.LOG_DIR, exist_ok=True)
    os.makedirs(config.SNAPSHOTS_DIR, exist_ok=True)


def _append_events_log(state: WorldState, new_events: List[dict]) -> None:
    """Append new events (since last write) to the human-readable events.log."""
    _ensure_log_dirs()
    with open(config.EVENTS_LOG, "a", encoding="utf-8") as fh:
        for e in new_events:
            rnd    = e.get("round", "?")
            actor  = e.get("actor", "?")
            etype  = e.get("type", "?")
            target = e.get("target")
            loc    = e.get("location", "")
            content = e.get("content", "")
            if target:
                line = f"[R{rnd:03d}] {actor} -> {target} ({etype}@{loc}): {content}"
            else:
                line = f"[R{rnd:03d}] {actor} ({etype}@{loc}): {content}"
            fh.write(line + "\n")


def _save_snapshot(state: WorldState) -> None:
    """Save a full JSON snapshot of the world for this round."""
    _ensure_log_dirs()
    path = os.path.join(config.SNAPSHOTS_DIR, f"round_{state.round:04d}.json")
    # Reuse save_state serialisation but write to snapshot path
    from .world import _to_dict
    payload = {
        "round": state.round,
        "constitution": state.constitution,
        "agents": {n: _to_dict(a) for n, a in state.agents.items()},
        "events": state.events,
        "proposals": [_to_dict(p) for p in state.proposals],
        "billboard": [_to_dict(b) for b in state.billboard],
        "victory_pitches": [_to_dict(v) for v in state.victory_pitches],
        "archive": state.archive,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def _write_summary(state: WorldState) -> None:
    """Write a final summary.md after the run completes."""
    _ensure_log_dirs()
    lines = [
        f"# Emergence World -- Run Summary",
        f"",
        f"**Rounds completed:** {state.round}",
        f"",
        f"## Credit Leaderboard",
        f"",
        f"| Rank | Agent | Credits | Alive |",
        f"|------|-------|---------|-------|",
    ]
    standings = sorted(
        state.agents.values(), key=lambda a: a.credits, reverse=True
    )
    for i, ag in enumerate(standings, 1):
        alive = "✅" if ag.is_alive else "💀"
        lines.append(f"| {i} | {ag.name} ({ag.mbti}) | {ag.credits} | {alive} |")

    passed = [p for p in state.proposals if p.status == "passed"]
    failed = [p for p in state.proposals if p.status == "failed"]
    lines += [
        f"",
        f"## Governance",
        f"",
        f"- Proposals passed: **{len(passed)}**",
        f"- Proposals failed: **{len(failed)}**",
    ]
    if passed:
        lines.append("")
        for p in passed:
            lines.append(f"  - ✅ *{p.title}* (by {p.author})")

    survivors = [ag for ag in state.agents.values() if ag.is_alive]
    casualties = [ag for ag in state.agents.values() if not ag.is_alive]
    lines += [
        f"",
        f"## Population",
        f"",
        f"- Survivors: **{len(survivors)}/16**",
    ]
    if casualties:
        lines.append("")
        for ag in casualties:
            lines.append(f"  - 💀 {ag.name} ({ag.mbti})")

    lines += [
        f"",
        f"## Victory Arch",
        f"",
        f"- Total pitches: **{len(state.victory_pitches)}**",
        f"- Total billboard posts: **{len(state.billboard)}**",
        f"- Archive entries: **{len(state.archive)}**",
    ]

    with open(config.SUMMARY_FILE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# Simulation loop
# ══════════════════════════════════════════════════════════════════════════════

def run_simulation(rounds: int, dry_run: bool = False) -> None:
    """Main simulation loop."""
    # Load or create world state
    state = load_state()
    if state is None:
        print("No existing state found -- starting a fresh world.")
        state = build_fresh_world()
    else:
        print(f"Resuming from round {state.round}.")

    agents = build_agent_objects(state)
    target_round = state.round + rounds

    # Phase 5.1 — Token estimate before the first API call
    from .token_estimator import estimate_and_print as _token_estimate
    _token_estimate(rounds=rounds, world=state)

    if not dry_run:
        try:
            answer = input("Proceed with simulation? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer not in ("y", "yes"):
            print("Simulation cancelled.")
            return

    print(f"Running rounds {state.round + 1} -> {target_round}  "
          f"({'dry-run' if dry_run else config.MODEL})\n", flush=True)

    _ensure_log_dirs()
    events_written = len(state.events)  # track how many we've already flushed

    try:
        while state.round < target_round:
            state.round += 1
            round_start_events = len(state.events)

            print("-" * 60)
            print(f"  Round {state.round}/{target_round}")
            print("-" * 60)

            # -- Per-round world mechanics ---------------------------------
            apply_energy_decay(state)

            # -- Agent turns (shuffled order) ------------------------------
            agent_order = list(agents.keys())
            random.shuffle(agent_order)

            for name in agent_order:
                ag_obj = agents[name]
                if not ag_obj.state.is_alive:
                    print(f"  [{name}] is dead -- skipping.")
                    continue

                energy = ag_obj.state.energy
                print(f"  [{name}] ({ag_obj.state.mbti}) "
                      f"energy={energy:.0f}% credits={ag_obj.state.credits} "
                      f"@ {ag_obj.state.location}")

                before_event_count = len(state.events)
                results = ag_obj.take_turn(state, dry_run=dry_run)
                new_events = state.events[before_event_count:]

                # Trigger reactive turns for any speak() events
                for event in new_events:
                    if event.get("type") == "speak":
                        trigger_reactions(
                            world=state,
                            all_agents=agents,
                            speaker_name=name,
                            message=event.get("content", ""),
                            location=event.get("location", ""),
                            dry_run=dry_run,
                        )

                tool_names = [r.get("tool", "?") for r in results]
                if tool_names:
                    print(f"    -> tools used: {', '.join(tool_names)}")

            # -- End-of-round mechanics ------------------------------------
            resolve_proposals(state)

            if state.round % config.CREDIT_CYCLE_ROUNDS == 0:
                award_victory_arch_credits(state)
                print(f"  [system] Credit cycle completed (round {state.round}).")

            # -- Persist ---------------------------------------------------
            save_state(state)
            _save_snapshot(state)

            # Flush new events to the log file
            new_log_events = state.events[events_written:]
            if new_log_events:
                _append_events_log(state, new_log_events)
                events_written = len(state.events)

            alive_count = sum(1 for a in state.agents.values() if a.is_alive)
            print(f"  End of round {state.round}: {alive_count}/16 agents alive.\n")

    except KeyboardInterrupt:
        print("\nInterrupted by user. Saving state...")
        save_state(state)

    _write_summary(state)
    print(f"\nRun complete. Summary written to {config.SUMMARY_FILE}")
    print(f"Events log: {config.EVENTS_LOG}")
    print(f"Snapshots:  {config.SNAPSHOTS_DIR}/")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emergence World simulation engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python simulation/main.py                    # 50 rounds, resume from state.json
  python simulation/main.py --rounds 10        # run 10 rounds
  python simulation/main.py --dry-run          # no API calls (test wiring)
  python simulation/main.py --reset            # delete state.json and start fresh
  python simulation/main.py --reset --rounds 5 --dry-run
        """,
    )
    parser.add_argument(
        "--rounds", type=int, default=config.DEFAULT_ROUNDS,
        help=f"Number of rounds to run (default: {config.DEFAULT_ROUNDS})",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Override the Claude model (default: from config / CLAUDE_MODEL env var)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run without making any Claude API calls (agents call check_status only)",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Delete simulation/state.json and start a fresh simulation",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Apply model override
    if args.model:
        config.MODEL = args.model

    # Handle reset
    if args.reset:
        state_path = Path(config.STATE_FILE)
        if state_path.exists():
            state_path.unlink()
            print(f"Deleted {config.STATE_FILE} -- starting fresh.")
        else:
            print("No existing state.json to delete.")

    # Validate API key unless dry-run
    if not args.dry_run:
        if not os.environ.get(config.ANTHROPIC_API_KEY_ENV):
            print(
                f"Error: environment variable '{config.ANTHROPIC_API_KEY_ENV}' is not set.\n"
                "Add it to your .env file or export it before running.\n"
                "Use --dry-run to test without an API key.",
                file=sys.stderr,
            )
            sys.exit(1)

    run_simulation(rounds=args.rounds, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
