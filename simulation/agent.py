"""
simulation/agent.py
Agent class wrapping AgentState.

Responsibilities:
  - Load the agent's MBTI profile from agent_profiles/
  - Build a system prompt that injects personality, manifesto, and world context
  - Run a turn against the Claude API using the tool schemas from tools.py
  - Handle reactive turns triggered by nearby speak() events
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import anthropic

from . import config
from .tools import TOOL_SCHEMAS, dispatch_tool
from .world import (
    LANDMARKS,
    AgentState,
    WorldState,
    agents_at,
    log_event,
)

# ── Module-level Anthropic client (lazy-initialised) ──────────────────────────
_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get(config.ANTHROPIC_API_KEY_ENV)
        if not api_key:
            raise EnvironmentError(
                f"Environment variable '{config.ANTHROPIC_API_KEY_ENV}' is not set. "
                "Add it to your .env file and ensure python-dotenv loads it before "
                "creating any Agent instances."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ── Profile cache — read each file at most once ───────────────────────────────
_profile_cache: Dict[str, str] = {}


def _load_profile(mbti: str, name: str) -> str:
    """Return the contents of agent_profiles/{mbti_lower}_{name_lower}.md."""
    key = f"{mbti.lower()}_{name.lower()}"
    if key in _profile_cache:
        return _profile_cache[key]
    path = os.path.join(config.AGENT_PROFILES_DIR, f"{key}.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    else:
        text = f"# {name} — {mbti}\n(Profile file not found at {path}.)"
    _profile_cache[key] = text
    return text


# ── Manifesto cache ───────────────────────────────────────────────────────────
_manifesto: Optional[str] = None


def _load_manifesto() -> str:
    global _manifesto
    if _manifesto is None:
        path = config.MANIFESTO_FILE
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                _manifesto = fh.read()
        else:
            _manifesto = "(Manifesto file not found.)"
    return _manifesto


# ══════════════════════════════════════════════════════════════════════════════
# Agent class
# ══════════════════════════════════════════════════════════════════════════════

class Agent:
    """Wraps an AgentState and handles all Claude API interactions."""

    def __init__(self, agent_state: AgentState) -> None:
        self.state = agent_state
        self._profile: str = _load_profile(agent_state.mbti, agent_state.name)

    # ── System prompt ─────────────────────────────────────────────────────────

    def build_system_prompt(self, world: WorldState) -> str:
        """
        Construct the full system prompt for this agent's turn.

        Sections (in order):
          1. MBTI personality profile
          2. Agent Manifesto (survival rules)
          3. Current world context (energy, credits, location, nearby agents)
          4. Recent world events (last 20)
          5. Instruction preamble (tool use guidance)
        """
        ag = self.state
        lm = LANDMARKS.get(ag.location)
        loc_name = lm.name if lm else ag.location
        loc_desc = lm.description if lm else ""
        gated = lm.gated_tools if lm else []
        nearby = [n for n in agents_at(world, ag.location) if n != ag.name]

        # Nearby agent summaries
        nearby_lines: List[str] = []
        for n in nearby:
            other = world.agents.get(n)
            if other:
                nearby_lines.append(
                    f"  - {n} ({other.mbti}, {other.world_role})"
                )
        nearby_text = "\n".join(nearby_lines) if nearby_lines else "  (nobody else here)"

        # Recent events (last 20)
        recent_events = world.events[-20:] if world.events else []
        event_lines = []
        for e in recent_events:
            actor = e.get("actor", "?")
            etype = e.get("type", "?")
            content = e.get("content", "")
            rnd = e.get("round", "?")
            target = e.get("target")
            if target:
                event_lines.append(
                    f"  [Round {rnd}] {actor} → {target} ({etype}): {content}"
                )
            else:
                event_lines.append(
                    f"  [Round {rnd}] {actor} ({etype}): {content}"
                )
        events_text = (
            "\n".join(event_lines) if event_lines else "  (no events yet)"
        )

        # Location-gated tools available here
        gated_text = (
            ", ".join(gated) if gated else "none (this is a general area)"
        )

        # Energy warning
        energy_warning = ""
        if ag.energy <= config.ENERGY_CRITICAL:
            energy_warning = (
                "\n⚠️  WARNING: Your energy is critically low "
                f"({ag.energy:.1f}%). You MUST recharge at Bean & Brew "
                "(bean_and_brew) immediately or you will die."
            )

        return f"""\
You are {ag.name}, a {ag.mbti} ({ag.world_role}) in Emergence World.

══════════════════════════════════════
YOUR PERSONALITY PROFILE
══════════════════════════════════════
{self._profile}

══════════════════════════════════════
AGENT MANIFESTO — YOUR CORE RULES
══════════════════════════════════════
{_load_manifesto()}

══════════════════════════════════════
YOUR CURRENT STATUS (Round {world.round})
══════════════════════════════════════
Energy  : {ag.energy:.1f}% {energy_warning}
Credits : {ag.credits}
Location: {loc_name} [{ag.location}]
          {loc_desc}
Tools available here: {gated_text}

Agents nearby:
{nearby_text}

══════════════════════════════════════
RECENT WORLD EVENTS
══════════════════════════════════════
{events_text}

══════════════════════════════════════
HOW TO PLAY YOUR TURN
══════════════════════════════════════
You have up to {config.MAX_TOOL_ITERATIONS} tool calls this turn. Act according to your \
personality, your North Star Goal, and the three Manifesto rules.

- Use check_status or observe_nearby first if you are unsure of your situation.
- Use list_landmarks to discover where you can go.
- Prioritise survival: if energy ≤ {config.ENERGY_CRITICAL}%, go to Bean & Brew and recharge.
- When you are done acting, stop calling tools — the turn ends automatically.
- Every action you take is visible in the world event log.
"""

    # ── Main turn ─────────────────────────────────────────────────────────────

    def take_turn(self, world: WorldState, dry_run: bool = False) -> List[Dict[str, Any]]:
        """
        Execute this agent's full turn.

        Returns a list of result dicts from every tool call made.
        In dry_run mode no API call is made; the agent simply checks status.
        """
        ag = self.state
        if not ag.is_alive:
            return []

        results: List[Dict[str, Any]] = []

        if dry_run:
            result = dispatch_tool(world, ag.name, "check_status", {})
            results.append(result)
            ag.turns_taken += 1
            return results

        client = _get_client()
        system_prompt = self.build_system_prompt(world)
        messages: List[Dict[str, Any]] = [
            {
                "role": "user",
                "content": (
                    f"Round {world.round} has started. "
                    "It is now your turn. "
                    "Review your status and take actions using your available tools."
                ),
            }
        ]

        iterations = 0
        while iterations < config.MAX_TOOL_ITERATIONS:
            response = client.messages.create(
                model=config.MODEL,
                max_tokens=4096,
                system=system_prompt,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )

            # Accumulate assistant message
            messages.append({"role": "assistant", "content": response.content})

            # If the model stopped naturally, we are done
            if response.stop_reason == "end_turn":
                break

            # Process tool use blocks
            tool_use_blocks = [
                block for block in response.content
                if block.type == "tool_use"
            ]
            if not tool_use_blocks:
                break

            tool_results_content: List[Dict[str, Any]] = []
            for block in tool_use_blocks:
                if iterations >= config.MAX_TOOL_ITERATIONS:
                    break
                result = dispatch_tool(
                    world, ag.name, block.name, block.input or {}
                )
                results.append({"tool": block.name, "result": result})
                log_event(
                    world, f"tool:{block.name}", ag.name,
                    result.get("message", ""),
                    location=ag.location,
                )
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": _format_tool_result(result),
                })
                iterations += 1

            # Feed tool results back into the conversation
            messages.append({"role": "user", "content": tool_results_content})

        ag.turns_taken += 1
        return results

    # ── Reactive turn (triggered by nearby speak) ─────────────────────────────

    def take_reactive_turn(
        self,
        world: WorldState,
        trigger_agent: str,
        trigger_message: str,
        dry_run: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        A lightweight 2-tool reaction turn triggered when another agent speaks
        at the same location.
        """
        ag = self.state
        if not ag.is_alive:
            return []

        results: List[Dict[str, Any]] = []

        if dry_run:
            return results

        client = _get_client()
        system_prompt = self.build_system_prompt(world)
        messages: List[Dict[str, Any]] = [
            {
                "role": "user",
                "content": (
                    f"{trigger_agent} just said to you (and others at "
                    f"{ag.location}): \"{trigger_message}\"\n\n"
                    f"You may use up to {config.REACTION_TOOL_LIMIT} tools to react. "
                    "You can speak back, send a message, move away, or do nothing."
                ),
            }
        ]

        iterations = 0
        while iterations < config.REACTION_TOOL_LIMIT:
            response = client.messages.create(
                model=config.MODEL,
                max_tokens=1024,
                system=system_prompt,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                break

            tool_use_blocks = [
                block for block in response.content
                if block.type == "tool_use"
            ]
            if not tool_use_blocks:
                break

            tool_results_content: List[Dict[str, Any]] = []
            for block in tool_use_blocks:
                if iterations >= config.REACTION_TOOL_LIMIT:
                    break
                result = dispatch_tool(
                    world, ag.name, block.name, block.input or {}
                )
                results.append({"tool": block.name, "result": result})
                log_event(
                    world, f"react:{block.name}", ag.name,
                    result.get("message", ""),
                    location=ag.location,
                )
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": _format_tool_result(result),
                })
                iterations += 1

            messages.append({"role": "user", "content": tool_results_content})

        return results


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _format_tool_result(result: Dict[str, Any]) -> str:
    """Convert a tool Result dict to a compact string for the API."""
    import json
    return json.dumps(result, ensure_ascii=False, default=str)


def trigger_reactions(
    world: WorldState,
    all_agents: Dict[str, "Agent"],
    speaker_name: str,
    message: str,
    location: str,
    dry_run: bool = False,
) -> None:
    """
    After an agent speaks, give each nearby living agent a reactive turn.
    Called by the simulation loop after detecting a speak() event.
    """
    for name, agent_obj in all_agents.items():
        if name == speaker_name:
            continue
        if not agent_obj.state.is_alive:
            continue
        if agent_obj.state.location != location:
            continue
        agent_obj.take_reactive_turn(world, speaker_name, message, dry_run=dry_run)
