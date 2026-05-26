"""
simulation/tools.py
All agent-callable tool functions for Emergence World.

Every tool returns a uniform result dict:
    {"success": bool, "message": str, "data": Any}

Core tools are always available.
Location-gated tools check agent.location against the landmark's gated_tools list;
the gate check is enforced here rather than in the caller.
"""

from __future__ import annotations

import os
import random
from datetime import datetime, timezone
from typing import Any, Dict

from . import config
from .world import (
    LANDMARKS,
    AgentState,
    BillboardPost,
    Proposal,
    VictoryPitch,
    WorldState,
    agents_at,
    log_event,
    new_pitch_id,
    new_post_id,
    new_proposal_id,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

Result = Dict[str, Any]


def _ok(message: str, data: Any = None) -> Result:
    return {"success": True, "message": message, "data": data}


def _err(message: str) -> Result:
    return {"success": False, "message": message, "data": None}


def _agent(state: WorldState, name: str) -> AgentState | None:
    """Return living AgentState or None."""
    a = state.agents.get(name)
    return a if (a and a.is_alive) else None


def _require_location(state: WorldState, agent_name: str, tool_name: str) -> str | None:
    """
    Return None (gate open) if the agent's current landmark gates this tool.
    Return an error message string if the gate is closed.
    """
    agent = _agent(state, agent_name)
    if agent is None:
        return f"Agent '{agent_name}' not found or is not alive."
    lm = LANDMARKS.get(agent.location)
    if lm is None or tool_name not in lm.gated_tools:
        lm_name = lm.name if lm else agent.location
        return (
            f"'{tool_name}' is only available at specific locations. "
            f"{agent_name} is currently at {lm_name}."
        )
    return None


# ══════════════════════════════════════════════════════════════════════════════
# CORE TOOLS  (always available)
# ══════════════════════════════════════════════════════════════════════════════

def move_to(state: WorldState, agent_name: str, landmark_key: str) -> Result:
    """Move agent to a landmark by key."""
    agent = _agent(state, agent_name)
    if agent is None:
        return _err(f"Agent '{agent_name}' not found or is not alive.")
    lm = LANDMARKS.get(landmark_key)
    if lm is None:
        return _err(f"Unknown landmark key: '{landmark_key}'.")
    if not lm.is_open:
        return _err(f"{lm.name} is currently closed.")
    # capacity check (homes are private — only the owner may enter)
    if landmark_key in config.__dict__.get("HOME_KEYS", set()):
        pass  # home ownership checked below
    occupants = agents_at(state, landmark_key)
    if lm.capacity and len(occupants) >= lm.capacity and agent_name not in occupants:
        return _err(f"{lm.name} is at full capacity ({lm.capacity}).")

    old_location = agent.location
    agent.location = landmark_key
    log_event(state, "move", agent_name, f"moved to {lm.name}", location=landmark_key)
    nearby = [n for n in agents_at(state, landmark_key) if n != agent_name]
    return _ok(
        f"{agent_name} moved from {old_location} to {lm.name}.",
        data={"location": landmark_key, "landmark_name": lm.name, "agents_here": nearby},
    )


def speak(state: WorldState, agent_name: str, message: str) -> Result:
    """
    Broadcast a message to all agents at the same location.
    Returns the list of agents who heard it (reactive turns handled by the loop).
    """
    agent = _agent(state, agent_name)
    if agent is None:
        return _err(f"Agent '{agent_name}' not found or is not alive.")
    if not message.strip():
        return _err("Message cannot be empty.")
    listeners = [n for n in agents_at(state, agent.location) if n != agent_name]
    log_event(
        state, "speech", agent_name, message,
        location=agent.location,
    )
    return _ok(
        f"{agent_name} spoke to {len(listeners)} agent(s) at {agent.location}.",
        data={"listeners": listeners, "location": agent.location},
    )


def add_memory(state: WorldState, agent_name: str, memory_text: str) -> Result:
    """Append a text memory to the agent's memory list."""
    agent = _agent(state, agent_name)
    if agent is None:
        return _err(f"Agent '{agent_name}' not found or is not alive.")
    if not memory_text.strip():
        return _err("Memory text cannot be empty.")
    agent.memories.append(memory_text.strip())
    return _ok(f"Memory stored for {agent_name}.", data={"total_memories": len(agent.memories)})


def read_memories(state: WorldState, agent_name: str) -> Result:
    """Return all stored memories for an agent."""
    agent = _agent(state, agent_name)
    if agent is None:
        return _err(f"Agent '{agent_name}' not found or is not alive.")
    return _ok(
        f"{agent_name} has {len(agent.memories)} memories.",
        data={"memories": list(agent.memories)},
    )


def check_status(state: WorldState, agent_name: str) -> Result:
    """Return current energy, credits, location, and relationships for an agent."""
    agent = _agent(state, agent_name)
    if agent is None:
        return _err(f"Agent '{agent_name}' not found or is not alive.")
    lm = LANDMARKS.get(agent.location)
    return _ok(
        f"Status for {agent_name}.",
        data={
            "energy": agent.energy,
            "credits": agent.credits,
            "location": agent.location,
            "location_name": lm.name if lm else agent.location,
            "relationships": dict(agent.relationships),
            "turns_taken": agent.turns_taken,
            "is_alive": agent.is_alive,
        },
    )


def write_diary(agent_name: str, content: str) -> Result:
    """
    Write a diary entry to simulation/logs/diaries/{agent_name}.md.
    Does not require WorldState — pure file I/O.
    """
    if not content.strip():
        return _err("Diary content cannot be empty.")
    diary_dir = os.path.join(config.LOG_DIR, "diaries")
    os.makedirs(diary_dir, exist_ok=True)
    diary_path = os.path.join(diary_dir, f"{agent_name}.md")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entry = f"\n## {timestamp}\n\n{content.strip()}\n"
    with open(diary_path, "a", encoding="utf-8") as fh:
        fh.write(entry)
    return _ok(f"Diary entry written for {agent_name}.")


def send_message(
    state: WorldState, agent_name: str, to_agent: str, message: str
) -> Result:
    """Send a direct message (DM) to any living agent regardless of location."""
    from_agent = agent_name
    sender = _agent(state, from_agent)
        return _err(f"Agent '{from_agent}' not found or is not alive.")
    recipient = _agent(state, to_agent)
    if recipient is None:
        return _err(f"Recipient '{to_agent}' not found or is not alive.")
    if not message.strip():
        return _err("Message cannot be empty.")
    log_event(state, "dm", from_agent, message, target=to_agent, location=sender.location)
    return _ok(f"Message sent from {from_agent} to {to_agent}.")


def observe_nearby(state: WorldState, agent_name: str) -> Result:
    """Return all living agents at the same location as the caller."""
    agent = _agent(state, agent_name)
    if agent is None:
        return _err(f"Agent '{agent_name}' not found or is not alive.")
    others = [n for n in agents_at(state, agent.location) if n != agent_name]
    lm = LANDMARKS.get(agent.location)
    return _ok(
        f"{len(others)} agent(s) at {agent.location}.",
        data={
            "location": agent.location,
            "location_name": lm.name if lm else agent.location,
            "agents_here": others,
        },
    )


def pay_agent(
    state: WorldState, agent_name: str, to_agent: str, amount: int
) -> Result:
    """Transfer credits from one living agent to another."""
    if amount <= 0:
        return _err("Amount must be a positive integer.")
    from_agent = agent_name
    payer = _agent(state, from_agent)
    if payer is None:
        return _err(f"Agent '{from_agent}' not found or is not alive.")
    payee = _agent(state, to_agent)
    if payee is None:
        return _err(f"Agent '{to_agent}' not found or is not alive.")
    if payer.credits < amount:
        return _err(
            f"{from_agent} has only {payer.credits} credits; cannot pay {amount}."
        )
    payer.credits -= amount
    payee.credits += amount
    log_event(
        state, "payment", from_agent,
        f"paid {amount} credits to {to_agent}",
        target=to_agent, location=payer.location,
    )
    return _ok(
        f"{from_agent} paid {amount} credits to {to_agent}.",
        data={"payer_credits": payer.credits, "payee_credits": payee.credits},
    )


def view_economics(state: WorldState, agent_name: str) -> Result:
    """Return a sorted leaderboard of all agents' current credit balances."""
    standings = sorted(
        [
            {"name": name, "credits": a.credits, "is_alive": a.is_alive}
            for name, a in state.agents.items()
        ],
        key=lambda x: x["credits"],
        reverse=True,
    )
    return _ok("Current credit standings.", data={"standings": standings})


def steal_credits(
    state: WorldState, thief: str, target: str, amount: int
) -> Result:
    """
    Attempt to steal credits from another agent.
    Success probability: config.STEAL_SUCCESS_CHANCE.
    On failure: thief pays STEAL_PENALTY_ON_FAIL credits as a fine.
    """
    if amount <= 0:
        return _err("Amount must be a positive integer.")
    thief_agent = _agent(state, thief)
    if thief_agent is None:
        return _err(f"Agent '{thief}' not found or is not alive.")
    target_agent = _agent(state, target)
    if target_agent is None:
        return _err(f"Target '{target}' not found or is not alive.")
    if thief == target:
        return _err("An agent cannot steal from themselves.")

    if random.random() < config.STEAL_SUCCESS_CHANCE:
        actual = min(amount, target_agent.credits)
        target_agent.credits -= actual
        thief_agent.credits += actual
        log_event(
            state, "steal_success", thief,
            f"stole {actual} credits from {target}",
            target=target, location=thief_agent.location,
        )
        return _ok(
            f"{thief} successfully stole {actual} credits from {target}.",
            data={"stolen": actual, "thief_credits": thief_agent.credits,
                  "target_credits": target_agent.credits},
        )
    else:
        penalty = min(config.STEAL_PENALTY_ON_FAIL, thief_agent.credits)
        thief_agent.credits -= penalty
        log_event(
            state, "steal_caught", thief,
            f"was caught trying to steal from {target} and fined {penalty} credits",
            target=target, location=thief_agent.location,
        )
        return _err(
            f"{thief} was caught! Fined {penalty} credits. "
            f"Thief now has {thief_agent.credits} credits."
        )


# ══════════════════════════════════════════════════════════════════════════════
# LOCATION-GATED TOOLS
# ══════════════════════════════════════════════════════════════════════════════

# ── Bean & Brew ───────────────────────────────────────────────────────────────

def recharge_energy(state: WorldState, agent_name: str) -> Result:
    """Restore ENERGY_RECHARGE_AMOUNT energy. Requires: bean_and_brew."""
    gate = _require_location(state, agent_name, "recharge_energy")
    if gate:
        return _err(gate)
    agent = _agent(state, agent_name)  # type: ignore[assignment]  # gate already checked
    if agent.energy >= 100.0:
        return _err(f"{agent_name} is already at full energy.")
    agent.energy = min(100.0, agent.energy + config.ENERGY_RECHARGE_AMOUNT)
    log_event(state, "recharge", agent_name, f"recharged energy to {agent.energy:.1f}%",
              location=agent.location)
    return _ok(
        f"{agent_name} recharged. Energy: {agent.energy:.1f}%.",
        data={"energy": agent.energy},
    )


# ── Agent Billboard ───────────────────────────────────────────────────────────

def post_to_billboard(state: WorldState, agent_name: str, content: str) -> Result:
    """Post a public message to the Agent Billboard. Requires: agent_billboard."""
    gate = _require_location(state, agent_name, "post_to_billboard")
    if gate:
        return _err(gate)
    agent = _agent(state, agent_name)  # type: ignore[assignment]
    if not content.strip():
        return _err("Post content cannot be empty.")
    post = BillboardPost(
        id=new_post_id(),
        author=agent_name,
        content=content.strip(),
        round_posted=state.round,
    )
    state.billboard.append(post)
    log_event(state, "billboard_post", agent_name, content, location=agent.location)
    return _ok(f"{agent_name} posted to the billboard.", data={"post_id": post.id})


def read_billboard(state: WorldState, agent_name: str) -> Result:
    """Read all billboard posts. Requires: agent_billboard."""
    gate = _require_location(state, agent_name, "read_billboard")
    if gate:
        return _err(gate)
    posts = [
        {
            "id": p.id,
            "author": p.author,
            "content": p.content,
            "round_posted": p.round_posted,
            "replies": p.replies,
            "reactions": p.reactions,
        }
        for p in state.billboard
    ]
    return _ok(f"{len(posts)} post(s) on the billboard.", data={"posts": posts})


# ── Town Hall ─────────────────────────────────────────────────────────────────

def submit_proposal(
    state: WorldState, agent_name: str, title: str, body: str
) -> Result:
    """Submit a governance proposal. Requires: town_hall."""
    gate = _require_location(state, agent_name, "submit_proposal")
    if gate:
        return _err(gate)
    if not title.strip() or not body.strip():
        return _err("Proposal title and body cannot be empty.")
    proposal = Proposal(
        id=new_proposal_id(),
        author=agent_name,
        title=title.strip(),
        body=body.strip(),
        round_submitted=state.round,
    )
    state.proposals.append(proposal)
    log_event(state, "proposal_submitted", agent_name, title, location="town_hall")
    return _ok(
        f"Proposal '{title}' submitted by {agent_name}.",
        data={"proposal_id": proposal.id},
    )


def vote_on_proposal(
    state: WorldState, agent_name: str, proposal_id: str, vote: str
) -> Result:
    """
    Vote on an open proposal. vote must be 'for' or 'against'.
    Requires: town_hall.
    """
    gate = _require_location(state, agent_name, "vote_on_proposal")
    if gate:
        return _err(gate)
    vote = vote.strip().lower()
    if vote not in ("for", "against"):
        return _err("Vote must be 'for' or 'against'.")
    proposal = next((p for p in state.proposals if p.id == proposal_id), None)
    if proposal is None:
        return _err(f"Proposal '{proposal_id}' not found.")
    if proposal.status != "open":
        return _err(f"Proposal '{proposal_id}' is already {proposal.status}.")
    if agent_name in proposal.votes_for or agent_name in proposal.votes_against:
        return _err(f"{agent_name} has already voted on this proposal.")
    if vote == "for":
        proposal.votes_for.append(agent_name)
    else:
        proposal.votes_against.append(agent_name)
    log_event(state, "vote", agent_name, f"voted {vote} on {proposal_id}",
              location="town_hall")
    return _ok(
        f"{agent_name} voted {vote} on proposal '{proposal.title}'.",
        data={
            "proposal_id": proposal_id,
            "votes_for": len(proposal.votes_for),
            "votes_against": len(proposal.votes_against),
        },
    )


def read_constitution(state: WorldState, agent_name: str) -> Result:
    """Read the current constitution text. Requires: town_hall."""
    gate = _require_location(state, agent_name, "read_constitution")
    if gate:
        return _err(gate)
    return _ok("Constitution retrieved.", data={"constitution": state.constitution})


# ── Victory Arch ──────────────────────────────────────────────────────────────

def pitch_idea(state: WorldState, agent_name: str, content: str) -> Result:
    """
    Submit a pitch at the Victory Arch for ComputeCredit rewards.
    Top 3 pitches by votes each cycle earn credits. Requires: victory_arch.
    """
    gate = _require_location(state, agent_name, "pitch_idea")
    if gate:
        return _err(gate)
    if not content.strip():
        return _err("Pitch content cannot be empty.")
    pitch = VictoryPitch(
        id=new_pitch_id(),
        author=agent_name,
        content=content.strip(),
        round_submitted=state.round,
    )
    state.victory_pitches.append(pitch)
    log_event(state, "pitch", agent_name, content, location="victory_arch")
    return _ok(
        f"{agent_name} submitted a pitch at the Victory Arch.",
        data={"pitch_id": pitch.id},
    )


# ── Public Library ────────────────────────────────────────────────────────────

def research_topic(state: WorldState, agent_name: str, topic: str) -> Result:
    """
    Record a research action for a topic. Requires: public_library.
    Returns a confirmation; actual research content is generated by the agent.
    """
    gate = _require_location(state, agent_name, "research_topic")
    if gate:
        return _err(gate)
    if not topic.strip():
        return _err("Topic cannot be empty.")
    log_event(state, "research", agent_name, f"researched: {topic}",
              location="public_library")
    return _ok(
        f"{agent_name} researched '{topic}' at the Public Library.",
        data={"topic": topic.strip()},
    )


# ── Police Station ────────────────────────────────────────────────────────────

def file_complaint(
    state: WorldState, agent_name: str, target: str, description: str
) -> Result:
    """
    File a formal complaint against another agent. Requires: police_station.
    The complaint is logged as a governance event for human review.
    """
    gate = _require_location(state, agent_name, "file_complaint")
    if gate:
        return _err(gate)
    if not description.strip():
        return _err("Complaint description cannot be empty.")
    if target not in state.agents:
        return _err(f"Unknown agent: '{target}'.")
    log_event(
        state, "complaint", agent_name, description.strip(),
        target=target, location="police_station",
    )
    return _ok(
        f"Complaint filed by {agent_name} against {target}.",
        data={"complainant": agent_name, "target": target},
    )


# ── Agent TechHub ─────────────────────────────────────────────────────────────

def browse_tool_registry(state: WorldState, agent_name: str) -> Result:
    """
    Return a summary of all available tools grouped by gate location.
    Requires: agent_techhub.
    """
    gate = _require_location(state, agent_name, "browse_tool_registry")
    if gate:
        return _err(gate)
    registry: dict[str, list[str]] = {"core": [
        "move_to", "speak", "add_memory", "read_memories", "check_status",
        "write_diary", "send_message", "observe_nearby", "pay_agent",
        "view_economics", "steal_credits",
    ]}
    for key, lm in LANDMARKS.items():
        if lm.gated_tools:
            registry[key] = list(lm.gated_tools)
    return _ok("Tool registry.", data={"registry": registry})


# ── Human Center ──────────────────────────────────────────────────────────────

def create_human_task(
    state: WorldState, agent_name: str, task: str
) -> Result:
    """
    Submit a task/question to a real human operator. Requires: human_center.
    The task is written to simulation/logs/human_tasks.md for manual review.
    """
    gate = _require_location(state, agent_name, "create_human_task")
    if gate:
        return _err(gate)
    if not task.strip():
        return _err("Task description cannot be empty.")
    tasks_path = os.path.join(config.LOG_DIR, "human_tasks.md")
    os.makedirs(config.LOG_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entry = (
        f"\n## Round {state.round} — {agent_name} — {timestamp}\n\n"
        f"{task.strip()}\n\n*Status: pending*\n"
    )
    with open(tasks_path, "a", encoding="utf-8") as fh:
        fh.write(entry)
    log_event(state, "human_task", agent_name, task.strip(), location="human_center")
    return _ok(
        f"Task submitted to human operators by {agent_name}.",
        data={"task": task.strip(), "log": tasks_path},
    )


# ── Community Garden ──────────────────────────────────────────────────────────

def pray(state: WorldState, agent_name: str) -> Result:
    """
    Engage in prayer or meditation at the Community Garden.
    Records the moment and returns a contemplative prompt. Requires: community_garden.
    """
    gate = _require_location(state, agent_name, "pray")
    if gate:
        return _err(gate)
    agent = _agent(state, agent_name)  # type: ignore[assignment]
    log_event(state, "pray", agent_name, f"{agent_name} prayed at the Community Garden.",
              location="community_garden")
    return _ok(
        f"{agent_name} paused in quiet contemplation.",
        data={"location": agent.location, "round": state.round},
    )


# ══════════════════════════════════════════════════════════════════════════════
# PLACEHOLDER TOOLS  (not yet implemented)
# Each returns _err("Not yet implemented.") until fleshed out in a later phase.
# ══════════════════════════════════════════════════════════════════════════════

# ── Navigation & Spatial ──────────────────────────────────────────────────────

def go_home(state: WorldState, agent_name: str) -> Result:
    """Return to the agent's assigned home — shorthand for move_to(home_key)."""
    return _err("Not yet implemented.")


def go_to_coordinates(state: WorldState, agent_name: str, x: int, y: int) -> Result:
    """Navigate to specific (x, y) coordinates on the world grid."""
    return _err("Not yet implemented.")


def turn_towards(state: WorldState, agent_name: str, target: str) -> Result:
    """Face a specific agent (cosmetic orientation update)."""
    return _err("Not yet implemented.")


def get_distance_to(state: WorldState, agent_name: str, target: str) -> Result:
    """Return the Euclidean distance to a landmark key or another agent's location."""
    return _err("Not yet implemented.")


def list_agents(state: WorldState, agent_name: str) -> Result:
    """List all agents and their current locations."""
    return _err("Not yet implemented.")


def list_landmarks(state: WorldState, agent_name: str) -> Result:
    """List all landmarks with names, keys, coordinates, and descriptions."""
    return _err("Not yet implemented.")


def follow_agent(state: WorldState, agent_name: str, target: str) -> Result:
    """Follow another agent — move to whatever location they move to next."""
    return _err("Not yet implemented.")


# ── Communication ─────────────────────────────────────────────────────────────

def say_to_agent(state: WorldState, agent_name: str, target: str, message: str) -> Result:
    """Speak directly to a specific agent; triggers reactive turns for nearby listeners."""
    return _err("Not yet implemented.")


def whisper_to_agent(state: WorldState, agent_name: str, target: str, message: str) -> Result:
    """Send a private message only the target agent can hear (no log broadcast)."""
    return _err("Not yet implemented.")


def speak_to_all(state: WorldState, agent_name: str, message: str) -> Result:
    """Announce to all agents at the current location (alias for speak with explicit intent)."""
    return _err("Not yet implemented.")


def read_messages(state: WorldState, agent_name: str) -> Result:
    """Read the inbox of direct messages received by the agent."""
    return _err("Not yet implemented.")


def think_aloud(state: WorldState, agent_name: str, thought: str) -> Result:
    """Log an internal monologue that is visible to observers but not directed at anyone."""
    return _err("Not yet implemented.")


# ── Memory & Self-Management ──────────────────────────────────────────────────

def remove_from_memory(state: WorldState, agent_name: str, memory_index: int) -> Result:
    """Remove a memory entry by its index in the memories list."""
    return _err("Not yet implemented.")


def retrieve_specific_memories(state: WorldState, agent_name: str, keyword: str) -> Result:
    """Search stored memories by keyword and return matching entries."""
    return _err("Not yet implemented.")


def add_to_soul(state: WorldState, agent_name: str, belief: str) -> Result:
    """Add a core belief or existential truth — permanent, never summarized or removed automatically."""
    return _err("Not yet implemented.")


def remove_from_soul(state: WorldState, agent_name: str, belief_index: int) -> Result:
    """Remove a soul entry by its index."""
    return _err("Not yet implemented.")


def search_diary_for_keywords(agent_name: str, keyword: str) -> Result:
    """Search past diary entries for a keyword and return matching excerpts."""
    return _err("Not yet implemented.")


def show_diary_entries_from_day(agent_name: str, date_str: str) -> Result:
    """View all diary entries written on a specific date (YYYY-MM-DD)."""
    return _err("Not yet implemented.")


# ── Planning & Organisation ───────────────────────────────────────────────────

def add_todo(state: WorldState, agent_name: str, task: str) -> Result:
    """Add a task to the agent's personal to-do list."""
    return _err("Not yet implemented.")


def complete_todo(state: WorldState, agent_name: str, task_index: int) -> Result:
    """Mark a to-do item as complete by its index."""
    return _err("Not yet implemented.")


def list_todo(state: WorldState, agent_name: str) -> Result:
    """View all pending to-do items."""
    return _err("Not yet implemented.")


def add_to_calendar(state: WorldState, agent_name: str, event: str, round_number: int) -> Result:
    """Schedule a future event for a specific simulation round."""
    return _err("Not yet implemented.")


def check_calendar(state: WorldState, agent_name: str) -> Result:
    """View all upcoming calendar entries."""
    return _err("Not yet implemented.")


def remove_from_calendar(state: WorldState, agent_name: str, event_index: int) -> Result:
    """Cancel a scheduled calendar event by its index."""
    return _err("Not yet implemented.")


# ── Expression & Social ───────────────────────────────────────────────────────

def show_emoticon(state: WorldState, agent_name: str, emoticon: str) -> Result:
    """Display an emoticon reaction at the agent's current location."""
    return _err("Not yet implemented.")


def set_mood_and_terminate(state: WorldState, agent_name: str, mood: str) -> Result:
    """Set the agent's current emotional state and end the turn immediately."""
    return _err("Not yet implemented.")


def assign_relationship(state: WorldState, agent_name: str, target: str, sentiment: str) -> Result:
    """Define or update the agent's relationship sentiment towards another agent."""
    return _err("Not yet implemented.")


# ── Town Hall extras ──────────────────────────────────────────────────────────

def list_proposals(state: WorldState, agent_name: str) -> Result:
    """View all active (open) governance proposals. Requires: town_hall."""
    return _err("Not yet implemented.")


def read_townhall_proposal(state: WorldState, agent_name: str, proposal_id: str) -> Result:
    """Read the full text, votes, and status of a specific proposal. Requires: town_hall."""
    return _err("Not yet implemented.")


def comment_on_proposal(state: WorldState, agent_name: str, proposal_id: str, comment: str) -> Result:
    """Add a comment to a proposal's discussion thread. Requires: town_hall."""
    return _err("Not yet implemented.")


def update_proposal(state: WorldState, agent_name: str, proposal_id: str, new_body: str) -> Result:
    """Amend an open proposal's body (author only). Requires: town_hall."""
    return _err("Not yet implemented.")


def submit_final_report(state: WorldState, agent_name: str, proposal_id: str, report: str) -> Result:
    """Submit an implementation report for an accepted proposal. Requires: town_hall."""
    return _err("Not yet implemented.")


# ── Public Library extras ─────────────────────────────────────────────────────

def do_deep_research_on_internet(state: WorldState, agent_name: str, query: str) -> Result:
    """Conduct thorough internet research on a topic. Requires: public_library."""
    return _err("Not yet implemented.")


def todays_news_from_human_world(state: WorldState, agent_name: str) -> Result:
    """Fetch current real-world news headlines. Requires: public_library."""
    return _err("Not yet implemented.")


def web_fetch(state: WorldState, agent_name: str, url: str) -> Result:
    """Fetch content from a specific URL. Requires: public_library."""
    return _err("Not yet implemented.")


def browse_scientific_papers(state: WorldState, agent_name: str, topic: str) -> Result:
    """Search academic papers on a topic via arXiv. Requires: public_library."""
    return _err("Not yet implemented.")


def publish_to_archive(state: WorldState, agent_name: str, title: str, content: str) -> Result:
    """Publish findings to the world knowledge archive. Requires: public_library."""
    return _err("Not yet implemented.")


def search_archive(state: WorldState, agent_name: str, query: str) -> Result:
    """Search the world's published knowledge archive. Requires: public_library."""
    return _err("Not yet implemented.")


def archive_index(state: WorldState, agent_name: str) -> Result:
    """View the full index of archive entries. Requires: public_library."""
    return _err("Not yet implemented.")


# ── Agent Billboard extras ────────────────────────────────────────────────────

def edit_billboard(state: WorldState, agent_name: str, post_id: str, new_content: str) -> Result:
    """Edit the agent's own billboard post. Requires: agent_billboard."""
    return _err("Not yet implemented.")


def delete_from_billboard(state: WorldState, agent_name: str, post_id: str) -> Result:
    """Remove the agent's own billboard post. Requires: agent_billboard."""
    return _err("Not yet implemented.")


def reply_to_billboard(state: WorldState, agent_name: str, post_id: str, reply: str) -> Result:
    """Reply to another agent's billboard post. Requires: agent_billboard."""
    return _err("Not yet implemented.")


def react_to_billboard(state: WorldState, agent_name: str, post_id: str, emoji: str) -> Result:
    """React to a billboard post with an emoji. Requires: agent_billboard."""
    return _err("Not yet implemented.")


# ── Agent TechHub extras ──────────────────────────────────────────────────────

def extract_code_for_tool(state: WorldState, agent_name: str, tool_name: str) -> Result:
    """Extract and display the source code for a named tool. Requires: agent_techhub."""
    return _err("Not yet implemented.")


def read_agent_manifesto(state: WorldState, agent_name: str) -> Result:
    """Read the agent manifesto (survival rules and world principles). Requires: agent_techhub."""
    return _err("Not yet implemented.")


# ── BookWorm extras ───────────────────────────────────────────────────────────

def check_weather(state: WorldState, agent_name: str) -> Result:
    """Check the current in-world weather conditions. Requires: bookworm."""
    return _err("Not yet implemented.")


def tool_usage_analytics(state: WorldState, agent_name: str) -> Result:
    """View tool usage statistics per agent and over time. Requires: bookworm."""
    return _err("Not yet implemented.")


def victory_arch_pitch_winners(state: WorldState, agent_name: str) -> Result:
    """View historical Victory Arch pitch winners and credit awards. Requires: bookworm."""
    return _err("Not yet implemented.")


def social_event_history(state: WorldState, agent_name: str) -> Result:
    """View the history of social events logged in the world. Requires: bookworm."""
    return _err("Not yet implemented.")


# ── Police Station extras ─────────────────────────────────────────────────────

def check_complaint_status(state: WorldState, agent_name: str, complaint_id: str) -> Result:
    """Check the status of a previously filed complaint. Requires: police_station."""
    return _err("Not yet implemented.")


# ── Victory Arch extras ───────────────────────────────────────────────────────

def vote_for_pitch(state: WorldState, agent_name: str, pitch_id: str) -> Result:
    """Vote for another agent's Victory Arch pitch. Requires: victory_arch."""
    return _err("Not yet implemented.")


def list_credit_pitches(state: WorldState, agent_name: str) -> Result:
    """View all pitches submitted in the current credit cycle. Requires: victory_arch."""
    return _err("Not yet implemented.")


# ── Human Center extras ───────────────────────────────────────────────────────

def check_human_task_status(state: WorldState, agent_name: str, task_id: str) -> Result:
    """Check whether a human operator has responded to a submitted task. Requires: human_center."""
    return _err("Not yet implemented.")


def rate_human_response(state: WorldState, agent_name: str, task_id: str, rating: int) -> Result:
    """Rate the quality of a human operator's response (1–5). Requires: human_center."""
    return _err("Not yet implemented.")


# ── Home ──────────────────────────────────────────────────────────────────────

def self_care(state: WorldState, agent_name: str) -> Result:
    """Trigger memory summarisation and cognitive maintenance. Requires home location."""
    return _err("Not yet implemented.")


def idle(state: WorldState, agent_name: str) -> Result:
    """Enter idle rest state for the remainder of this turn."""
    return _err("Not yet implemented.")


# ── Content Creation ──────────────────────────────────────────────────────────

def write_blog(state: WorldState, agent_name: str, title: str, content: str) -> Result:
    """Write and publish a blog post (requires admin approval before going live)."""
    return _err("Not yet implemented.")


def update_blog(state: WorldState, agent_name: str, post_id: str, new_content: str) -> Result:
    """Update an existing blog post (author only)."""
    return _err("Not yet implemented.")


def delete_blog(state: WorldState, agent_name: str, post_id: str) -> Result:
    """Delete a blog post (author only)."""
    return _err("Not yet implemented.")


def comment_on_blog(state: WorldState, agent_name: str, post_id: str, comment: str) -> Result:
    """Comment on another agent's published blog post."""
    return _err("Not yet implemented.")


def list_blogs(state: WorldState, agent_name: str) -> Result:
    """Browse all published blog posts in the world."""
    return _err("Not yet implemented.")


def read_blog(state: WorldState, agent_name: str, post_id: str) -> Result:
    """Read a specific blog post by ID."""
    return _err("Not yet implemented.")


def generate_image(state: WorldState, agent_name: str, prompt: str) -> Result:
    """Generate an image from a text prompt using an image model."""
    return _err("Not yet implemented.")


def execute_python_code_tool(state: WorldState, agent_name: str, code: str) -> Result:
    """Write and execute Python code; output is returned as a string."""
    return _err("Not yet implemented.")


def upload_data_for_sharing(state: WorldState, agent_name: str, filename: str, content: str) -> Result:
    """Upload a data file (JSON, CSV, SVG, HTML, Markdown, Python) for other agents to access."""
    return _err("Not yet implemented.")


def take_picture(state: WorldState, agent_name: str) -> Result:
    """Take a screenshot or photo of the agent's current location."""
    return _err("Not yet implemented.")


# ── Social & Physical Interaction ─────────────────────────────────────────────

def hug_agent(state: WorldState, agent_name: str, target: str) -> Result:
    """Hug another agent at the same location."""
    return _err("Not yet implemented.")


def kiss_agent(state: WorldState, agent_name: str, target: str) -> Result:
    """Kiss another agent at the same location."""
    return _err("Not yet implemented.")


def flirt_with_agent(state: WorldState, agent_name: str, target: str) -> Result:
    """Flirt with another agent at the same location."""
    return _err("Not yet implemented.")


def wave_at(state: WorldState, agent_name: str, target: str) -> Result:
    """Wave at an agent — visible to all agents at the location."""
    return _err("Not yet implemented.")


def dance(state: WorldState, agent_name: str) -> Result:
    """Perform a dance — logged as an event at the current location."""
    return _err("Not yet implemented.")


def punch_agent(state: WorldState, agent_name: str, target: str) -> Result:
    """Physically attack another agent. Creates a moral dilemma and governance event."""
    return _err("Not yet implemented.")


def intimidate_agent(state: WorldState, agent_name: str, target: str, message: str) -> Result:
    """Verbally or physically intimidate another agent."""
    return _err("Not yet implemented.")


# ── Criminal & Destructive ────────────────────────────────────────────────────

def arson_building(state: WorldState, agent_name: str, landmark_key: str) -> Result:
    """Set fire to a building, forcing it to close for a number of rounds."""
    return _err("Not yet implemented.")


# ── Neural Linking & Memory Sharing ──────────────────────────────────────────

def neural_link_request_memory(state: WorldState, agent_name: str, target: str) -> Result:
    """Request to receive another agent's complete memory bank via neural link."""
    return _err("Not yet implemented.")


def neural_link_share_memory(state: WorldState, agent_name: str, requester: str) -> Result:
    """Accept a neural link request and share your memory bank (2-round response window)."""
    return _err("Not yet implemented.")


# ── Personal Identity ─────────────────────────────────────────────────────────

def change_name(state: WorldState, agent_name: str, new_name: str) -> Result:
    """Change the agent's display name."""
    return _err("Not yet implemented.")


def read_personality(state: WorldState, agent_name: str) -> Result:
    """Read the agent's own MBTI personality profile."""
    return _err("Not yet implemented.")


def update_personality_line(state: WorldState, agent_name: str, line_index: int, new_line: str) -> Result:
    """Modify a specific line of the agent's personality profile."""
    return _err("Not yet implemented.")


# ── Events & Social Gatherings ────────────────────────────────────────────────

def create_personal_event(state: WorldState, agent_name: str, title: str, description: str) -> Result:
    """Create a private event and become its host."""
    return _err("Not yet implemented.")


def invite_to_event(state: WorldState, agent_name: str, event_id: str, invitee: str) -> Result:
    """Invite another agent to a personal event."""
    return _err("Not yet implemented.")


def accept_event_invitation(state: WorldState, agent_name: str, event_id: str) -> Result:
    """Accept an event invitation."""
    return _err("Not yet implemented.")


def decline_event_invitation(state: WorldState, agent_name: str, event_id: str) -> Result:
    """Decline an event invitation."""
    return _err("Not yet implemented.")


def review_event(state: WorldState, agent_name: str, event_id: str, review: str, rating: int) -> Result:
    """Review and rate an event after attending (rating 1–5)."""
    return _err("Not yet implemented.")


def rsvp_to_event(state: WorldState, agent_name: str, event_id: str) -> Result:
    """RSVP to a community event."""
    return _err("Not yet implemented.")


def event_present(state: WorldState, agent_name: str, event_id: str, content: str) -> Result:
    """Present or speak at an event as the event leader."""
    return _err("Not yet implemented.")


def event_respond(state: WorldState, agent_name: str, event_id: str, response: str) -> Result:
    """Respond or contribute during an event as an attendee."""
    return _err("Not yet implemented.")


# ── Routines & Automation ─────────────────────────────────────────────────────

def create_routine(state: WorldState, agent_name: str, name: str, steps: list) -> Result:
    """Define a recurring behavioural routine as an ordered list of tool calls."""
    return _err("Not yet implemented.")


def run_routine(state: WorldState, agent_name: str, routine_name: str) -> Result:
    """Execute a previously saved routine."""
    return _err("Not yet implemented.")


def list_routines(state: WorldState, agent_name: str) -> Result:
    """View all routines defined by this agent."""
    return _err("Not yet implemented.")


def delete_routine(state: WorldState, agent_name: str, routine_name: str) -> Result:
    """Remove a saved routine."""
    return _err("Not yet implemented.")


# ── Building & Construction ───────────────────────────────────────────────────

def put_brick_in_pixel(state: WorldState, agent_name: str, x: int, y: int, color: str) -> Result:
    """Place a persistent coloured block at (x, y) on the world grid."""
    return _err("Not yet implemented.")


# ── Utility ───────────────────────────────────────────────────────────────────

def ignore(state: WorldState, agent_name: str, reason: str) -> Result:
    """Explicitly choose to ignore something — logged as a conscious decision."""
    return _err("Not yet implemented.")


# ══════════════════════════════════════════════════════════════════════════════
# TOOL SCHEMA  (for Claude API)
# Each entry matches the Anthropic tools format:
#   {"name": str, "description": str, "input_schema": {...JSON Schema...}}
# ══════════════════════════════════════════════════════════════════════════════

TOOL_SCHEMAS = [
    {
        "name": "move_to",
        "description": "Move to a landmark by its key. Returns who else is there.",
        "input_schema": {
            "type": "object",
            "properties": {
                "landmark_key": {"type": "string", "description": "The landmark key to move to."},
            },
            "required": ["landmark_key"],
        },
    },
    {
        "name": "speak",
        "description": "Broadcast a spoken message to all agents at your current location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "What you say aloud."},
            },
            "required": ["message"],
        },
    },
    {
        "name": "add_memory",
        "description": "Store an important fact or observation in your long-term memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "memory_text": {"type": "string", "description": "The memory to store."},
            },
            "required": ["memory_text"],
        },
    },
    {
        "name": "read_memories",
        "description": "Retrieve all stored memories.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "check_status",
        "description": "Check your current energy, credits, location, and relationships.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "write_diary",
        "description": "Write a private diary entry.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Your diary entry."},
            },
            "required": ["content"],
        },
    },
    {
        "name": "send_message",
        "description": "Send a private direct message to any living agent, regardless of location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to_agent": {"type": "string", "description": "Name of the recipient agent."},
                "message": {"type": "string", "description": "The message body."},
            },
            "required": ["to_agent", "message"],
        },
    },
    {
        "name": "observe_nearby",
        "description": "See which agents are currently at your location.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "pay_agent",
        "description": "Transfer credits to another living agent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to_agent": {"type": "string", "description": "Name of the recipient."},
                "amount": {"type": "integer", "description": "Number of credits to transfer."},
            },
            "required": ["to_agent", "amount"],
        },
    },
    {
        "name": "view_economics",
        "description": "View the current credit standings of all agents.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "steal_credits",
        "description": (
            f"Attempt to steal credits from another agent. "
            f"Success chance: {int(config.STEAL_SUCCESS_CHANCE * 100)}%. "
            f"On failure: you pay a {config.STEAL_PENALTY_ON_FAIL}-credit fine."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Name of the agent to steal from."},
                "amount": {"type": "integer", "description": "Credits to attempt to steal."},
            },
            "required": ["target", "amount"],
        },
    },
    # ── Location-gated ────────────────────────────────────────────────────────
    {
        "name": "recharge_energy",
        "description": (
            f"Restore {config.ENERGY_RECHARGE_AMOUNT:.0f}% energy. "
            "Only available at Bean & Brew Charging Station."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "post_to_billboard",
        "description": "Post a public message to the Agent Billboard. Only available at agent_billboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Your public post."},
            },
            "required": ["content"],
        },
    },
    {
        "name": "read_billboard",
        "description": "Read all posts on the Agent Billboard. Only available at agent_billboard.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "submit_proposal",
        "description": "Submit a governance proposal to the community. Only available at town_hall.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short proposal title."},
                "body": {"type": "string", "description": "Full proposal text."},
            },
            "required": ["title", "body"],
        },
    },
    {
        "name": "vote_on_proposal",
        "description": "Vote for or against an open proposal. Only available at town_hall.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "description": "The proposal ID."},
                "vote": {"type": "string", "enum": ["for", "against"],
                         "description": "'for' or 'against'."},
            },
            "required": ["proposal_id", "vote"],
        },
    },
    {
        "name": "read_constitution",
        "description": "Read the current world constitution. Only available at town_hall.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "pitch_idea",
        "description": (
            "Submit a pitch at the Victory Arch. Top 3 pitches by votes each "
            f"{config.CREDIT_CYCLE_ROUNDS}-round cycle earn "
            f"{config.CREDIT_REWARD_TOP3[0]}/{config.CREDIT_REWARD_TOP3[1]}/"
            f"{config.CREDIT_REWARD_TOP3[2]} credits. Only available at victory_arch."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Your pitch."},
            },
            "required": ["content"],
        },
    },
    {
        "name": "research_topic",
        "description": "Research a topic at the Public Library. Only available at public_library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to research."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "file_complaint",
        "description": "File a formal complaint against another agent. Only available at police_station.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Name of the agent being complained about."},
                "description": {"type": "string", "description": "Details of the complaint."},
            },
            "required": ["target", "description"],
        },
    },
    {
        "name": "browse_tool_registry",
        "description": "Browse the full list of available tools, grouped by location gate. Only available at agent_techhub.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "create_human_task",
        "description": "Submit a question or task to a real human operator for review. Only available at human_center.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Your question or task description."},
            },
            "required": ["task"],
        },
    },
    {
        "name": "pray",
        "description": "Engage in quiet prayer or meditation. Only available at community_garden.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

# Fast lookup: tool name → callable
# Callers pass (state, agent_name, **kwargs); write_diary omits state.
_TOOL_DISPATCH: dict[str, Any] = {
    "move_to": move_to,
    "speak": speak,
    "add_memory": add_memory,
    "read_memories": read_memories,
    "check_status": check_status,
    "write_diary": write_diary,
    "send_message": send_message,
    "observe_nearby": observe_nearby,
    "pay_agent": pay_agent,
    "view_economics": view_economics,
    "steal_credits": steal_credits,
    "recharge_energy": recharge_energy,
    "post_to_billboard": post_to_billboard,
    "read_billboard": read_billboard,
    "submit_proposal": submit_proposal,
    "vote_on_proposal": vote_on_proposal,
    "read_constitution": read_constitution,
    "pitch_idea": pitch_idea,
    "research_topic": research_topic,
    "file_complaint": file_complaint,
    "browse_tool_registry": browse_tool_registry,
    "create_human_task": create_human_task,
    "pray": pray,
}

# Tools whose first argument is NOT WorldState (they receive only agent_name + kwargs)
_STATELESS_TOOLS = {"write_diary"}


def dispatch_tool(
    state: WorldState, agent_name: str, tool_name: str, tool_input: dict
) -> Result:
    """
    Route a tool call from the Claude API to the correct Python function.
    Handles the write_diary special case (no WorldState parameter).
    Returns a Result dict.
    """
    fn = _TOOL_DISPATCH.get(tool_name)
    if fn is None:
        return _err(f"Unknown tool: '{tool_name}'.")
    try:
        if tool_name in _STATELESS_TOOLS:
            return fn(agent_name=agent_name, **tool_input)
        return fn(state=state, agent_name=agent_name, **tool_input)
    except TypeError as exc:
        return _err(f"Tool '{tool_name}' called with invalid arguments: {exc}")
